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
from .claude_client import ClaudeClient
from .confidence import ConfidenceAdjuster
from .fallback import RuleBasedFallback
from .prompt_builder import PromptBuilder
from .sentiment_analyzer import SentimentAnalyzer
from .validator import AIOutputValidator

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

        # 3. Build prompt (includes analyst briefing + sentiment if available)
        prompt = await self._prompt_builder.build_prompt(
            snapshot, analyst_briefing=analyst_briefing, sentiment_context=sentiment_context,
        )
        system = self._prompt_builder.get_system_prompt()
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

        # 4. Call Claude (with retry + fallback)
        proposal = await self._call_ai_with_retry(
            pair, system, prompt, prompt_hash, snapshot
        )

        # 5. Publish signal result
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

        # 6. Write signal record to DB
        if proposal:
            await self._save_signal(proposal)

        return proposal

    async def _call_ai_with_retry(
        self, pair: str, system: str, prompt: str, prompt_hash: str, snapshot
    ) -> SignalProposal | None:
        """
        3 AI attempts + rule-based fallback.
        Attempt 1: full prompt
        Attempt 2: simplified prompt
        Attempt 3: rule-based fallback
        """
        live_price = snapshot.bid

        for attempt in range(3):
            try:
                raw_response = await self._claude.call(system, prompt)

                # Log AI interaction
                await self._log_ai_interaction(prompt_hash, raw_response, attempt)

                # Validate output
                result = self._validator.validate(raw_response, live_price)
                if result.passed and result.data:
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
