"""
Lumitrade Signal Scanner
==========================
Orchestrates signal generation cycle per pair on staggered 15-minute intervals.
EUR/USD at :00, GBP/USD at :05, USD/JPY at :10.
Per BDS Section 5 and SAS Section 3.2.3.
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ..config import LumitradeConfig
from ..core.enums import Action, GenerationMethod, TradeDuration
from ..core.models import SignalProposal
from ..data_engine.engine import DataEngine
from ..infrastructure.db import DatabaseClient
from ..infrastructure.event_publisher import EventPublisher
from ..infrastructure.secure_logger import get_logger
from .chart_generator import ChartGenerator, encode_chart_base64
from .claude_client import ClaudeClient
from .confidence import ConfidenceAdjuster
from .fallback import RuleBasedFallback
from .lesson_filter import LessonFilter
from .prompt_builder import PromptBuilder
from .sentiment_analyzer import SentimentAnalyzer
from .tradingview_signal import TradingViewSignal
from .validator import AIOutputValidator, ValidationResult

logger = get_logger(__name__)

# Stagger offsets in seconds to avoid hitting Claude API simultaneously.
# Spreads 8 pairs across the scan cycle with 30s gaps.
PAIR_OFFSETS = {
    "EUR_USD": 0,
    "GBP_USD": 30,
    "USD_JPY": 60,
    "USD_CHF": 90,
    "AUD_USD": 120,
    "USD_CAD": 150,
    "NZD_USD": 180,
    "XAU_USD": 210,
}


class SignalScanner:
    """Orchestrates signal generation for all configured pairs."""

    def __init__(
        self,
        config: LumitradeConfig,
        data_engine: DataEngine,
        db: DatabaseClient,
        claude: ClaudeClient,
        subagents=None,
        events: EventPublisher | None = None,
    ):
        self.config = config
        self._data = data_engine
        self._db = db
        self._claude = claude
        self._subagents = subagents
        self._events = events
        self._validator = AIOutputValidator()
        self._adjuster = ConfidenceAdjuster()
        self._fallback = RuleBasedFallback()
        self._sentiment = SentimentAnalyzer(config)
        self._prompt_builder = PromptBuilder(db, config.oanda_account_id)
        self._lesson_filter = LessonFilter(db, config)
        self._chart_gen = ChartGenerator()
        self._tv_signal = TradingViewSignal()
        self._pair_locks: dict[str, asyncio.Lock] = {}

    async def scan_loop(self) -> None:
        """Background task: run signal scans on staggered intervals."""
        logger.info("signal_scanner_started", pairs=self.config.pairs)
        try:
            while True:
                for pair in self.config.pairs:
                    asyncio.create_task(
                        self._scan_pair(pair), name=f"scan_{pair}"
                    )
                await asyncio.sleep(self.config.signal_interval_minutes * 60)
        except asyncio.CancelledError:
            logger.info("signal_scanner_cancelled")

    async def _scan_pair(self, pair: str) -> None:
        """Scan a single pair with per-pair locking."""
        # Apply stagger offset (in seconds)
        offset = PAIR_OFFSETS.get(pair, 0)
        if offset > 0:
            await asyncio.sleep(offset)

        # Acquire per-pair lock
        if pair not in self._pair_locks:
            self._pair_locks[pair] = asyncio.Lock()

        if self._pair_locks[pair].locked():
            logger.debug("scan_skipped_lock_held", pair=pair)
            return

        async with self._pair_locks[pair]:
            try:
                await self.execute_scan(pair)
            except Exception as e:
                logger.error("scan_failed", pair=pair, error=str(e))

    async def execute_scan(self, pair: str) -> SignalProposal | None:
        """Execute a full signal scan for one pair."""
        logger.info("signal_scan_started", pair=pair)

        # Publish scan start event
        if self._events:
            self._events.publish(
                "SCANNER", "SCAN_START", f"Scanning {pair}...", pair=pair,
            )

        # 1. Get market snapshot
        snapshot = await self._data.get_snapshot(pair)
        if not snapshot:
            logger.warning("scan_no_snapshot", pair=pair)
            if self._events:
                self._events.publish(
                    "SCANNER", "SIGNAL",
                    f"No trade on {pair} — no market snapshot available",
                    pair=pair, severity="WARNING",
                )
            return None

        if not snapshot.data_quality.is_tradeable:
            dq = snapshot.data_quality
            reason = []
            if not dq.is_fresh: reason.append("stale price")
            if dq.spike_detected: reason.append("spike detected")
            if not dq.spread_acceptable: reason.append(f"spread too wide")
            if not dq.candles_complete: reason.append("candle gaps")
            if not dq.ohlc_valid: reason.append("OHLC invalid")
            reason_str = ", ".join(reason) if reason else "unknown"
            logger.warning("scan_data_not_tradeable", pair=pair, reasons=reason_str)
            if self._events:
                self._events.publish(
                    "SCANNER", "SIGNAL",
                    f"No trade on {pair} — {reason_str}",
                    pair=pair, severity="WARNING",
                )
            return None

        # 1a-ii. Early spread check — skip before burning AI tokens
        from decimal import Decimal as _Dec
        max_spread = _Dec("200") if "XAU" in pair else _Dec("5")
        if snapshot.spread_pips > max_spread:
            logger.info("early_spread_skip", pair=pair, spread=str(snapshot.spread_pips), max=str(max_spread))
            return None

        # 1a-iii. Already-in-position check (FIFO) — skip if we already hold this pair
        try:
            open_trades = await self._db.select("trades", {"status": "OPEN", "pair": pair})
            if open_trades:
                logger.info("already_in_position_skip", pair=pair, open_count=len(open_trades))
                return None
        except Exception:
            pass  # Non-critical — risk engine will catch it later

        # 1b. Lesson filter — check BLOCK/BOOST rules before spending AI tokens
        #     Determine session from snapshot, check both directions.
        #     If BOTH BUY and SELL are blocked, skip the pair entirely.
        session_str = (
            snapshot.session.value
            if hasattr(snapshot.session, "value")
            else str(snapshot.session)
        )
        # Map Session enum values to lesson filter session names
        _session_map = {
            "TOKYO": "ASIAN", "LONDON": "LONDON", "NEW_YORK": "NY",
            "OVERLAP": "LONDON", "OTHER": "OTHER",
        }
        lesson_session = _session_map.get(session_str, "OTHER")

        buy_blocked, buy_boosts = await self._lesson_filter.check(
            pair, "BUY", lesson_session,
        )
        sell_blocked, sell_boosts = await self._lesson_filter.check(
            pair, "SELL", lesson_session,
        )

        if buy_blocked and sell_blocked:
            logger.info(
                "lesson_filter_pair_blocked",
                pair=pair,
                session=lesson_session,
            )
            if self._events:
                self._events.publish(
                    "SCANNER", "LESSON_BLOCK",
                    f"Skipping {pair} — both BUY and SELL blocked by trading memory",
                    pair=pair, severity="WARNING",
                )
            return None

        # Collect boost messages for prompt injection
        boost_context = buy_boosts + sell_boosts

        # 1c. TradingView consensus — 26-indicator second opinion
        tv_data = await self._tv_signal.get_recommendation(pair)
        tv_context = self._tv_signal.format_for_prompt(tv_data)
        if tv_data:
            # If TV strongly disagrees with our only allowed direction (BUY), skip
            if self.config.buy_only_mode and self._tv_signal.conflicts_with_action(tv_data, "BUY"):
                logger.warning(
                    "tradingview_conflict_skip",
                    pair=pair,
                    tv_recommendation=tv_data.get("recommendation", ""),
                )
                if self._events:
                    self._events.publish(
                        "SCANNER", "TV_CONFLICT",
                        f"Skipping {pair} — TradingView says {tv_data['recommendation']} (conflicts with BUY)",
                        pair=pair, severity="WARNING",
                    )
                return None
            boost_context.append(tv_context)

        # 2. Get analyst briefing (SA-01) and attach to snapshot
        analyst_briefing = ""
        if self._subagents:
            try:
                briefing_result = await self._subagents.get_analyst_briefing(
                    snapshot,
                )
                analyst_briefing = briefing_result.get("briefing", "")
                if self._events and analyst_briefing:
                    self._events.publish(
                        "SA-01", "BRIEFING",
                        f"Market briefing for {pair}",
                        detail=analyst_briefing[:500], pair=pair,
                    )
            except Exception as e:
                logger.warning(
                    "analyst_briefing_failed", error=str(e),
                )

        # 2b. Run sentiment analysis on pair currencies
        sentiment_context = ""
        try:
            sentiment = await self._sentiment.analyze(
                pairs=[pair],
                calendar_events=snapshot.news_events,
            )
            if sentiment:
                lines = [f"{c}: {s.value if hasattr(s, 'value') else str(s)}" for c, s in sentiment.items()]
                sentiment_context = "Currency sentiment: " + " | ".join(lines)
                if self._events:
                    self._events.publish(
                        "SENTIMENT", "ANALYSIS",
                        f"Sentiment for {pair}: {sentiment_context}",
                        pair=pair,
                    )
        except Exception as e:
            logger.warning("sentiment_analysis_failed", pair=pair, error=str(e))

        # 3. Generate chart image for visual analysis
        chart_b64 = ""
        try:
            chart_bytes = await self._chart_gen.generate_chart(
                pair=pair,
                candles_h4=snapshot.candles_h4,
                candles_h1=snapshot.candles_h1,
                candles_m15=snapshot.candles_m15,
                indicators=snapshot.indicators,
            )
            chart_b64 = encode_chart_base64(chart_bytes)
            if chart_b64:
                logger.info("chart_ready_for_claude", pair=pair,
                            size_kb=len(chart_bytes) // 1024)
        except Exception as e:
            logger.warning("chart_generation_skipped", pair=pair, error=str(e))

        has_chart = bool(chart_b64)

        # 4. Build prompt (includes analyst briefing + sentiment + lesson boosts + chart flag)
        prompt = await self._prompt_builder.build_prompt(
            snapshot,
            analyst_briefing=analyst_briefing,
            sentiment_context=sentiment_context,
            boost_lessons=boost_context if boost_context else None,
            has_chart=has_chart,
        )
        system = self._prompt_builder.get_system_prompt()
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

        # 5. Call Claude (with retry + fallback; use multimodal if chart available)
        proposal = await self._call_ai_with_retry(
            pair, system, prompt, prompt_hash, snapshot, chart_b64=chart_b64,
        )

        # 5b. Signal alignment check — at least 3 indicators must confirm direction
        if proposal and (proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)) != "HOLD":
            alignment = self._check_signal_alignment(proposal, snapshot)
            if alignment < 3:
                logger.warning(
                    "signal_alignment_insufficient",
                    pair=pair,
                    action=(proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)),
                    alignment_score=alignment,
                    required=3,
                )
                if self._events:
                    self._events.publish(
                        "SCANNER", "ALIGNMENT_FAIL",
                        f"Rejected {pair} — only {alignment}/3 indicators align",
                        pair=pair, severity="WARNING",
                    )
                proposal = None

        # 6. Publish signal result
        if proposal and self._events:
            if (proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)) == "HOLD":
                self._events.publish(
                    "SCANNER", "SIGNAL",
                    f"No trade on {pair} — HOLD signal",
                    pair=pair, severity="WARNING",
                )
            else:
                self._events.publish(
                    "CLAUDE", "SIGNAL",
                    f"{(proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action))} {pair} @ {proposal.entry_price}"
                    f" | Confidence: {proposal.confidence_adjusted}",
                    detail=proposal.summary[:500], pair=pair,
                    severity="SUCCESS",
                    metadata={
                        "confidence": str(proposal.confidence_adjusted),
                        "entry": str(proposal.entry_price),
                    },
                )

        # 7. Write signal record to DB
        if proposal:
            await self._save_signal(proposal)

        return proposal

    async def _call_ai_with_retry(
        self, pair: str, system: str, prompt: str, prompt_hash: str, snapshot,
        chart_b64: str = "",
    ) -> SignalProposal | None:
        """
        3 AI attempts + rule-based fallback.
        Attempt 1: full prompt (with chart if available)
        Attempt 2: simplified prompt (text-only fallback)
        Attempt 3: rule-based fallback
        """
        live_price = snapshot.bid

        for attempt in range(3):
            try:
                # Use multimodal call on first attempt if chart is available
                if chart_b64 and attempt == 0:
                    raw_response = await self._claude.call_with_image(
                        system, prompt, chart_b64,
                    )
                else:
                    raw_response = await self._claude.call(system, prompt)

                # Log AI interaction
                await self._log_ai_interaction(prompt_hash, raw_response, attempt)

                # Validate output
                result = self._validator.validate(raw_response, live_price)
                if result.passed and result.data:
                    # Server-side H4 trend enforcement — AI cannot override
                    trend_block = self._check_h4_trend_alignment(
                        result.data.get("action", "HOLD"), snapshot
                    )
                    if trend_block:
                        logger.warning(
                            "ai_trend_override",
                            pair=pair,
                            attempt=attempt + 1,
                            reason=trend_block,
                            ai_action=result.data["action"],
                        )
                        result = ValidationResult(False, reason=trend_block)
                    else:
                        return self._build_proposal(
                            result.data, snapshot, prompt_hash
                        )
                else:
                    logger.warning(
                        "ai_validation_failed",
                        pair=pair,
                        attempt=attempt + 1,
                        reason=result.reason,
                    )
            except Exception as e:
                logger.error(
                    "ai_call_failed",
                    pair=pair,
                    attempt=attempt + 1,
                    error=str(e),
                )

        # All AI attempts failed — use rule-based fallback
        logger.warning("ai_exhausted_using_fallback", pair=pair)
        return self._fallback.generate(snapshot)

    def _check_signal_alignment(self, proposal, snapshot) -> int:
        """
        Count how many technical indicators confirm the trade direction.
        Requires at least 3 to proceed. Prevents trades on conflicting signals.
        """
        action = proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)
        ind = snapshot.indicators
        is_buy = action == "BUY"
        score = 0

        # 1. EMA alignment (EMA20 vs EMA50)
        ema20 = float(ind.ema_20)
        ema50 = float(ind.ema_50)
        if ema20 and ema50:
            if (is_buy and ema20 > ema50) or (not is_buy and ema20 < ema50):
                score += 1

        # 2. RSI direction (not overbought for BUY, not oversold for SELL)
        rsi = float(ind.rsi_14)
        if rsi:
            if (is_buy and 30 < rsi < 70) or (not is_buy and 30 < rsi < 70):
                score += 1

        # 3. MACD (histogram positive for BUY, negative for SELL)
        macd_hist = float(ind.macd_histogram)
        if (is_buy and macd_hist > 0) or (not is_buy and macd_hist < 0):
            score += 1

        # 4. Price vs Bollinger mid (above for BUY, below for SELL)
        price = float(snapshot.bid)
        bb_mid = float(ind.bb_mid)
        if price and bb_mid:
            if (is_buy and price > bb_mid) or (not is_buy and price < bb_mid):
                score += 1

        # 5. EMA200 trend (price above for BUY, below for SELL)
        ema200 = float(ind.ema_200)
        if price and ema200:
            if (is_buy and price > ema200) or (not is_buy and price < ema200):
                score += 1

        logger.info(
            "signal_alignment_check",
            pair=snapshot.pair,
            action=action,
            score=score,
            ema_ok=bool((is_buy and ema20 > ema50) or (not is_buy and ema20 < ema50)) if ema20 and ema50 else False,
            rsi_ok=bool(30 < rsi < 70) if rsi else False,
            macd_ok=bool((is_buy and macd_hist > 0) or (not is_buy and macd_hist < 0)),
            bb_ok=bool((is_buy and price > bb_mid) or (not is_buy and price < bb_mid)) if price and bb_mid else False,
            ema200_ok=bool((is_buy and price > ema200) or (not is_buy and price < ema200)) if price and ema200 else False,
        )
        return score

    def _check_h4_trend_alignment(self, action: str, snapshot) -> str | None:
        """
        Server-side enforcement: SELL forbidden when H4 EMAs are bullish,
        BUY forbidden when H4 EMAs are bearish.
        Returns blocking reason string, or None if aligned.

        Historical data: 0% SELL win rate when H4 trend was bullish.
        This check prevents the AI from overriding the trend rule.
        """
        if action == "HOLD":
            return None

        # BUY_ONLY_MODE: block all SELL signals (configurable via env)
        if action == "SELL" and self.config.buy_only_mode:
            return "BUY_ONLY_MODE active — SELL signals blocked"

        ind = snapshot.indicators
        ema20 = float(ind.ema_20)
        ema50 = float(ind.ema_50)
        ema200 = float(ind.ema_200)

        # All three must be non-zero (data available)
        if ema20 == 0 or ema50 == 0 or ema200 == 0:
            return None

        # Bullish: EMA20 > EMA50 > EMA200
        bullish = ema20 > ema50 > ema200
        # Bearish: EMA20 < EMA50 < EMA200
        bearish = ema20 < ema50 < ema200

        if action == "SELL" and bullish:
            return (
                f"H4 trend is BULLISH (EMA20 {ema20:.5f} > EMA50 {ema50:.5f} > EMA200 {ema200:.5f}) "
                f"— SELL forbidden. Must trade WITH the trend."
            )
        if action == "BUY" and bearish:
            return (
                f"H4 trend is BEARISH (EMA20 {ema20:.5f} < EMA50 {ema50:.5f} < EMA200 {ema200:.5f}) "
                f"— BUY forbidden. Must trade WITH the trend."
            )
        return None

    def _build_proposal(
        self, data: dict, snapshot, prompt_hash: str
    ) -> SignalProposal:
        """Build SignalProposal from validated AI output."""
        raw_conf = Decimal(str(data["confidence"]))

        # Adjust confidence
        adjusted_conf, adj_log = self._adjuster.adjust(
            raw_conf, snapshot, data["action"]
        )

        return SignalProposal(
            signal_id=uuid4(),
            pair=snapshot.pair,
            action=Action(data["action"]),
            confidence_raw=raw_conf,
            confidence_adjusted=adjusted_conf,
            confidence_adjustment_log=adj_log,
            entry_price=Decimal(str(data["entry_price"])),
            stop_loss=Decimal(str(data["stop_loss"])),
            take_profit=Decimal(str(data["take_profit"])),
            summary=data["summary"],
            reasoning=data["reasoning"],
            timeframe_scores={
                "h4": data.get("timeframe_h4_score", 0),
                "h1": data.get("timeframe_h1_score", 0),
                "m15": data.get("timeframe_m15_score", 0),
            },
            indicators_snapshot=snapshot.indicators.to_dict(),
            key_levels=[Decimal(str(k)) for k in data.get("key_levels", [])],
            invalidation_level=Decimal(str(data.get("invalidation_level", 0))),
            expected_duration=TradeDuration(data.get("expected_duration", "INTRADAY")),
            generation_method=GenerationMethod.AI,
            session=snapshot.session,
            spread_pips=snapshot.spread_pips,
            news_context=snapshot.news_events,
            ai_prompt_hash=prompt_hash,
            created_at=datetime.now(timezone.utc),
            recommended_risk_pct=(
                Decimal(str(data["recommended_risk_pct"]))
                if data.get("recommended_risk_pct")
                else None
            ),
            risk_reasoning=data.get("risk_reasoning", ""),
        )

    async def _save_signal(self, proposal: SignalProposal) -> None:
        """Write signal record to DB."""
        try:
            await self._db.insert("signals", {
                "id": str(proposal.signal_id),
                "account_id": self.config.account_uuid,
                "pair": proposal.pair,
                "action": (proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action)),
                "confidence_raw": str(proposal.confidence_raw),
                "confidence_adjusted": str(proposal.confidence_adjusted),
                "confidence_adjustment_log": proposal.confidence_adjustment_log,
                "entry_price": str(proposal.entry_price),
                "stop_loss": str(proposal.stop_loss),
                "take_profit": str(proposal.take_profit),
                "summary": proposal.summary,
                "reasoning": proposal.reasoning,
                "indicators_snapshot": proposal.indicators_snapshot,
                "timeframe_scores": proposal.timeframe_scores,
                "key_levels": [str(k) for k in proposal.key_levels],
                "session": (proposal.session.value if hasattr(proposal.session, "value") else str(proposal.session)),
                "spread_pips": str(proposal.spread_pips),
                "executed": False,
                "generation_method": (proposal.generation_method.value if hasattr(proposal.generation_method, "value") else str(proposal.generation_method)),
                "ai_prompt_hash": proposal.ai_prompt_hash,
                "created_at": proposal.created_at.isoformat(),
            })
        except Exception as e:
            logger.error("signal_save_failed", error=str(e))

    async def _log_ai_interaction(
        self, prompt_hash: str, response: str, attempt: int
    ) -> None:
        """Log AI prompt/response for audit."""
        try:
            await self._db.insert("ai_interaction_log", {
                "account_id": self.config.account_uuid,
                "prompt_hash": prompt_hash,
                "response_text": response[:5000],
                "retry_count": attempt,
                "model_used": self.config.claude_model,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning("ai_interaction_log_failed", error=str(e))
