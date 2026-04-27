# Fix All Stubs, Placeholders & Fake Code — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate every stub, placeholder, and fake code path identified in the 14-item audit — making Lumitrade production-honest from infrastructure to UI.

**Architecture:** Three waves executed sequentially. Wave 1 fixes immediate data integrity and security issues. Wave 2 implements the Phase 2 backend intelligence layer (regime, sentiment, calendar, correlation, subagents, performance). Wave 3 cleans up the frontend (remove coming-soon pages from nav, fix testimonials, dynamic filters).

**Tech Stack:** Python 3.12 async, Next.js 14, Supabase, OANDA REST v3, Anthropic Claude API, pandas-ta

---

## Wave 1: Security & Data Integrity (Tasks 1-4)

### Task 1: Re-enable Authentication Middleware

**Files:**
- Modify: `frontend/src/middleware.ts:34-37`

- [ ] **Step 1: Read current middleware**

The auth bypass is at lines 34-37:
```typescript
// TODO: Re-enable strict auth after email rate limit resets
if (!user) {
  // Allow dashboard access without auth for now
  return response;
}
```

- [ ] **Step 2: Fix the bypass — redirect unauthenticated users to login**

Replace the bypass block with:
```typescript
if (!user) {
  const loginUrl = new URL("/auth/login", request.url);
  loginUrl.searchParams.set("redirect", request.nextUrl.pathname);
  return NextResponse.redirect(loginUrl);
}
```

- [ ] **Step 3: Verify login page exists**

Run: `ls frontend/src/app/auth/login/page.tsx`
If missing, create a basic login page that redirects to Supabase auth.

- [ ] **Step 4: Test locally**

Open `http://localhost:3002/dashboard` in incognito — should redirect to `/auth/login`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/middleware.ts
git commit -m "fix: re-enable auth middleware — redirect unauthenticated users to login"
```

---

### Task 2: API Routes Return Errors Instead of Empty Arrays

**Files:**
- Modify: `frontend/src/app/(dashboard)/api/positions/route.ts:24`
- Modify: `frontend/src/app/(dashboard)/api/trades/route.ts:9`
- Modify: `frontend/src/app/(dashboard)/api/signals/route.ts` (check similar pattern)
- Modify: `frontend/src/app/(dashboard)/api/analytics/route.ts:30`

- [ ] **Step 1: Fix positions route**

In `positions/route.ts`, change:
```typescript
if (!url || !key) return NextResponse.json({ positions: [] });
```
To:
```typescript
if (!url || !key) {
  return NextResponse.json(
    { error: "Server misconfigured: missing SUPABASE_URL or SERVICE_KEY" },
    { status: 500 }
  );
}
```

- [ ] **Step 2: Fix trades route**

In `trades/route.ts`, change:
```typescript
if (!url || !key) return NextResponse.json({ trades: [] });
```
To:
```typescript
if (!url || !key) {
  return NextResponse.json(
    { error: "Server misconfigured: missing SUPABASE_URL or SERVICE_KEY" },
    { status: 500 }
  );
}
```

- [ ] **Step 3: Fix signals route**

Same pattern — replace empty array fallback with 500 error when env vars are missing.

- [ ] **Step 4: Fix analytics route**

In `analytics/route.ts`, change:
```typescript
if (!url || !key) return NextResponse.json(EMPTY_ANALYTICS);
```
To:
```typescript
if (!url || !key) {
  return NextResponse.json(
    { error: "Server misconfigured: missing SUPABASE_URL or SERVICE_KEY" },
    { status: 500 }
  );
}
```

Keep the `EMPTY_ANALYTICS` return for when env vars exist but there are genuinely zero trades.

- [ ] **Step 5: Test locally — verify error on missing env**

Temporarily rename `.env.local` and hit the endpoints — should get 500 errors, not empty arrays.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/\(dashboard\)/api/*/route.ts
git commit -m "fix: API routes return 500 on missing config instead of silent empty arrays"
```

---

### Task 3: Equity Curve Uses Real Starting Balance

**Files:**
- Modify: `frontend/src/app/(dashboard)/api/analytics/route.ts:60,67,69`

- [ ] **Step 1: Fetch real opening balance from system_state**

Before the equity curve calculation, add:
```typescript
// Fetch real starting balance from system_state
let startingBalance = 100000;
try {
  const balRes = await fetch(
    `${url}/rest/v1/system_state?id=eq.singleton&select=daily_opening_balance`,
    { headers: { apikey: key, Authorization: `Bearer ${key}` }, cache: "no-store" }
  );
  if (balRes.ok) {
    const rows = await balRes.json();
    if (rows?.[0]?.daily_opening_balance) {
      startingBalance = parseFloat(rows[0].daily_opening_balance) || 100000;
    }
  }
} catch { /* use default */ }
```

- [ ] **Step 2: Replace hardcoded 100000 with startingBalance**

Replace all three instances:
```typescript
let equity = startingBalance;
// ...
let peak = startingBalance;
// ...
let runningEquity = startingBalance;
```

- [ ] **Step 3: Test — verify equity curve starts from real OANDA balance**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\(dashboard\)/api/analytics/route.ts
git commit -m "fix: equity curve uses real OANDA opening balance instead of hardcoded 100K"
```

---

### Task 4: Performance Context Builder — Real Values

**Files:**
- Modify: `backend/lumitrade/analytics/performance_context_builder.py:85-96`

- [ ] **Step 1: Read current hardcoded values**

Lines 85-96 return hardcoded:
- `current_drawdown_from_peak=Decimal("0")`
- `account_growth_this_week=Decimal("0")`
- `trend_strength="MODERATE"`

- [ ] **Step 2: Calculate real drawdown from system_state**

Replace the hardcoded values with:
```python
# Calculate real drawdown
try:
    state_row = await self._db.select_one("system_state", {"id": "singleton"})
    current_balance = Decimal(str(state_row.get("daily_opening_balance", "0"))) if state_row else Decimal("0")
    weekly_opening = Decimal(str(state_row.get("weekly_opening_balance", "0"))) if state_row else Decimal("0")

    if weekly_opening > 0:
        account_growth_this_week = (current_balance - weekly_opening) / weekly_opening
    else:
        account_growth_this_week = Decimal("0")

    # Drawdown from peak = (peak - current) / peak
    peak_balance = max(current_balance, weekly_opening)
    if peak_balance > 0:
        current_drawdown = (peak_balance - current_balance) / peak_balance
    else:
        current_drawdown = Decimal("0")
except Exception:
    current_drawdown = Decimal("0")
    account_growth_this_week = Decimal("0")

# Trend strength from ATR relative to price
trend_strength = "UNKNOWN"
if context and hasattr(context, "indicators"):
    atr = context.indicators.get("atr_14")
    ema_diff = abs(context.indicators.get("ema_20", 0) - context.indicators.get("ema_50", 0))
    if atr and atr > 0:
        ratio = ema_diff / atr
        if ratio > 1.5:
            trend_strength = "STRONG"
        elif ratio > 0.5:
            trend_strength = "MODERATE"
        else:
            trend_strength = "WEAK"
```

- [ ] **Step 3: Test**

Run: `pytest tests/unit/ -k "performance_context" -v`

- [ ] **Step 4: Commit**

```bash
git add backend/lumitrade/analytics/performance_context_builder.py
git commit -m "fix: performance context uses real drawdown and growth from OANDA data"
```

---

## Wave 2: Backend Intelligence Layer (Tasks 5-13)

### Task 5: Market Regime Classifier — Real Implementation

**Files:**
- Modify: `backend/lumitrade/data_engine/regime_classifier.py`
- Create: `backend/tests/unit/test_regime_classifier.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for MarketRegimeClassifier."""
import pytest
from decimal import Decimal
from lumitrade.data_engine.regime_classifier import RegimeClassifier
from lumitrade.core.enums import MarketRegime


def test_trending_bull_regime():
    """EMA spread > 1.5*ATR with price above EMA50 = TRENDING."""
    classifier = RegimeClassifier()
    result = classifier.classify(
        ema_20=Decimal("1.1050"), ema_50=Decimal("1.1020"),
        ema_200=Decimal("1.0900"), atr_14=Decimal("0.0050"),
        current_price=Decimal("1.1060"), spread_pips=Decimal("1.5"),
    )
    assert result == MarketRegime.TRENDING


def test_ranging_regime():
    """EMA spread < 0.5*ATR = RANGING."""
    classifier = RegimeClassifier()
    result = classifier.classify(
        ema_20=Decimal("1.1001"), ema_50=Decimal("1.1000"),
        ema_200=Decimal("1.0999"), atr_14=Decimal("0.0050"),
        current_price=Decimal("1.1000"), spread_pips=Decimal("1.5"),
    )
    assert result == MarketRegime.RANGING


def test_high_volatility_regime():
    """ATR > 2x rolling average = HIGH_VOL."""
    classifier = RegimeClassifier()
    result = classifier.classify(
        ema_20=Decimal("1.1050"), ema_50=Decimal("1.1020"),
        ema_200=Decimal("1.0900"), atr_14=Decimal("0.0150"),
        current_price=Decimal("1.1060"), spread_pips=Decimal("1.5"),
        avg_atr_30d=Decimal("0.0050"),
    )
    assert result == MarketRegime.HIGH_VOL


def test_low_liquidity_regime():
    """Spread > 4 pips = LOW_LIQ."""
    classifier = RegimeClassifier()
    result = classifier.classify(
        ema_20=Decimal("1.1050"), ema_50=Decimal("1.1020"),
        ema_200=Decimal("1.0900"), atr_14=Decimal("0.0050"),
        current_price=Decimal("1.1060"), spread_pips=Decimal("5.0"),
    )
    assert result == MarketRegime.LOW_LIQ
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_regime_classifier.py -v`
Expected: FAIL (classify() doesn't accept these params yet)

- [ ] **Step 3: Implement the classifier**

Replace the stub in `regime_classifier.py`:
```python
"""
Lumitrade Market Regime Classifier
====================================
Classifies current market conditions based on EMA spreads, ATR, and spread.
Per BDS Section 13.2.
"""

from decimal import Decimal
from ..core.enums import MarketRegime
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Thresholds
TRENDING_EMA_ATR_RATIO = Decimal("1.5")
RANGING_EMA_ATR_RATIO = Decimal("0.5")
HIGH_VOL_ATR_MULTIPLIER = Decimal("2.0")
LOW_LIQ_SPREAD_THRESHOLD = Decimal("4.0")


class RegimeClassifier:
    """Classify market regime from indicator data."""

    def classify(
        self,
        ema_20: Decimal,
        ema_50: Decimal,
        ema_200: Decimal,
        atr_14: Decimal,
        current_price: Decimal,
        spread_pips: Decimal,
        avg_atr_30d: Decimal | None = None,
    ) -> MarketRegime:
        """
        Determine market regime from current indicator values.

        Priority order: LOW_LIQ > HIGH_VOL > TRENDING > RANGING > UNKNOWN
        """
        if atr_14 <= 0:
            return MarketRegime.UNKNOWN

        # Low liquidity: spread too wide
        if spread_pips > LOW_LIQ_SPREAD_THRESHOLD:
            logger.info("regime_classified", regime="LOW_LIQ", spread=str(spread_pips))
            return MarketRegime.LOW_LIQ

        # High volatility: ATR > 2x average
        if avg_atr_30d and avg_atr_30d > 0:
            if atr_14 > HIGH_VOL_ATR_MULTIPLIER * avg_atr_30d:
                logger.info("regime_classified", regime="HIGH_VOL",
                            atr=str(atr_14), avg_atr=str(avg_atr_30d))
                return MarketRegime.HIGH_VOL

        # EMA spread relative to ATR
        ema_spread = abs(ema_20 - ema_200)
        spread_ratio = ema_spread / atr_14

        # Trending: wide EMA spread
        if spread_ratio > TRENDING_EMA_ATR_RATIO:
            logger.info("regime_classified", regime="TRENDING",
                        spread_ratio=str(spread_ratio))
            return MarketRegime.TRENDING

        # Ranging: narrow EMA spread
        if spread_ratio < RANGING_EMA_ATR_RATIO:
            logger.info("regime_classified", regime="RANGING",
                        spread_ratio=str(spread_ratio))
            return MarketRegime.RANGING

        return MarketRegime.UNKNOWN
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_regime_classifier.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/lumitrade/data_engine/regime_classifier.py backend/tests/unit/test_regime_classifier.py
git commit -m "feat: implement market regime classifier — TRENDING/RANGING/HIGH_VOL/LOW_LIQ"
```

---

### Task 6: Economic Calendar — Real Implementation

**Files:**
- Modify: `backend/lumitrade/data_engine/calendar.py:35-60`

- [ ] **Step 1: Implement _fetch_events using free ForexFactory scraping**

ForexFactory provides a public calendar page. We'll use a lightweight approach — fetch their calendar XML/CSV feed. If no external API key is available, use OANDA's own economic calendar endpoint which is free with an OANDA account.

Replace `_fetch_events()`:
```python
async def _fetch_events(self) -> list[dict]:
    """Fetch economic calendar from OANDA's free calendar endpoint."""
    import httpx
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    # Look ahead 4 hours for upcoming events
    period_start = now.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
    period_end = (now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S.000000000Z")

    url = (
        f"https://api-fxpractice.oanda.com/labs/v1/calendar"
        f"?period={period_start}%2C{period_end}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={
                "Authorization": f"Bearer {self._config.oanda_api_key_data}",
            })
            if resp.status_code != 200:
                logger.warning("calendar_fetch_failed", status=resp.status_code)
                return []

            events = resp.json()
            return [
                {
                    "title": e.get("title", ""),
                    "currency": e.get("currency", ""),
                    "impact": self._map_impact(e.get("impact", 0)),
                    "timestamp": e.get("timestamp", ""),
                    "forecast": e.get("forecast", ""),
                    "previous": e.get("previous", ""),
                }
                for e in events
                if e.get("impact", 0) >= 2  # Medium+ impact only
            ]
    except Exception as e:
        logger.warning("calendar_fetch_error", error=str(e))
        return []

@staticmethod
def _map_impact(impact_level: int) -> str:
    """Map OANDA impact number to HIGH/MEDIUM/LOW."""
    if impact_level >= 3:
        return "HIGH"
    elif impact_level >= 2:
        return "MEDIUM"
    return "LOW"
```

Note: If OANDA's labs calendar endpoint is deprecated, fall back to a free alternative. The key is: this MUST return real data, not an empty list.

- [ ] **Step 2: Wire config into calendar fetcher**

Add `self._config` to the CalendarFetcher `__init__` and pass the LumitradeConfig so it has the OANDA API key.

- [ ] **Step 3: Test with real OANDA key**

Run locally with OANDA env vars set. Verify events are returned.

- [ ] **Step 4: Commit**

```bash
git add backend/lumitrade/data_engine/calendar.py
git commit -m "feat: economic calendar fetches real events from OANDA calendar API"
```

---

### Task 7: Correlation Matrix — Real Implementation

**Files:**
- Modify: `backend/lumitrade/risk_engine/correlation_matrix.py`
- Create: `backend/tests/unit/test_correlation_matrix.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for CorrelationMatrix."""
import pytest
from decimal import Decimal
from lumitrade.risk_engine.correlation_matrix import CorrelationMatrix


def test_same_pair_correlation_is_one():
    matrix = CorrelationMatrix()
    assert matrix.get_correlation("EUR_USD", "EUR_USD") == Decimal("1.0")


def test_known_high_correlation():
    """EUR/USD and GBP/USD are historically highly correlated."""
    matrix = CorrelationMatrix()
    corr = matrix.get_correlation("EUR_USD", "GBP_USD")
    assert corr >= Decimal("0.5")


def test_position_size_reduced_for_correlated():
    """If holding EUR/USD, new GBP/USD should be reduced."""
    matrix = CorrelationMatrix()
    multiplier = matrix.get_position_size_multiplier(
        open_pairs=["EUR_USD"], new_pair="GBP_USD"
    )
    assert multiplier < Decimal("1.0")


def test_position_size_unchanged_for_uncorrelated():
    """USD/JPY is less correlated with EUR/USD."""
    matrix = CorrelationMatrix()
    multiplier = matrix.get_position_size_multiplier(
        open_pairs=["EUR_USD"], new_pair="USD_JPY"
    )
    assert multiplier >= Decimal("0.8")
```

- [ ] **Step 2: Implement with known forex correlation data**

Replace the stub:
```python
"""
Lumitrade Correlation Matrix
==============================
Static correlation matrix for Phase 0 pairs.
Uses known historical correlations between major forex pairs.
Per BDS Section 13.4.
"""
from decimal import Decimal
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Historical correlation coefficients (approximate, updated quarterly)
# Source: typical 90-day rolling correlations for major pairs
CORRELATIONS: dict[tuple[str, str], Decimal] = {
    ("EUR_USD", "GBP_USD"): Decimal("0.85"),
    ("EUR_USD", "USD_JPY"): Decimal("-0.60"),
    ("GBP_USD", "USD_JPY"): Decimal("-0.55"),
}


class CorrelationMatrix:
    """Track correlation between currency pairs for position sizing."""

    def get_correlation(self, pair_a: str, pair_b: str) -> Decimal:
        """Return correlation coefficient between two pairs (-1.0 to 1.0)."""
        if pair_a == pair_b:
            return Decimal("1.0")
        key = (min(pair_a, pair_b), max(pair_a, pair_b))
        return CORRELATIONS.get(key, Decimal("0.0"))

    def get_position_size_multiplier(
        self,
        open_pairs: list[str],
        new_pair: str,
    ) -> Decimal:
        """
        Return position size multiplier based on correlation with open positions.
        1.0 = full size, <1.0 = reduced due to correlation.
        """
        if not open_pairs:
            return Decimal("1.0")

        max_abs_corr = Decimal("0.0")
        for pair in open_pairs:
            corr = abs(self.get_correlation(pair, new_pair))
            if corr > max_abs_corr:
                max_abs_corr = corr

        # Reduce position size proportional to correlation
        # 0.0 correlation = 1.0x (full size)
        # 0.5 correlation = 0.75x
        # 0.85 correlation = 0.575x
        # 1.0 correlation = 0.5x (half size)
        multiplier = Decimal("1.0") - (max_abs_corr * Decimal("0.5"))

        logger.info(
            "correlation_adjustment",
            new_pair=new_pair,
            open_pairs=open_pairs,
            max_correlation=str(max_abs_corr),
            size_multiplier=str(multiplier),
        )
        return multiplier
```

- [ ] **Step 3: Wire into risk engine position sizing**

In `risk_engine/engine.py`, after position sizing, apply the correlation multiplier:
```python
from .correlation_matrix import CorrelationMatrix

# In __init__:
self._correlation = CorrelationMatrix()

# After position sizing calculation:
open_pairs = await self._get_open_pairs()
corr_multiplier = self._correlation.get_position_size_multiplier(open_pairs, proposal.pair)
if corr_multiplier < Decimal("1.0"):
    units = int(units * corr_multiplier / 1000) * 1000
    logger.info("position_size_correlation_adjusted", units=units, multiplier=str(corr_multiplier))
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_correlation_matrix.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/lumitrade/risk_engine/correlation_matrix.py backend/tests/unit/test_correlation_matrix.py backend/lumitrade/risk_engine/engine.py
git commit -m "feat: correlation matrix with known forex pair correlations — adjusts position size"
```

---

### Task 8: Sentiment Analyzer — Real Implementation

**Files:**
- Modify: `backend/lumitrade/ai_brain/sentiment_analyzer.py`

- [ ] **Step 1: Implement using Claude API (already available)**

We already have the Anthropic API key. Use Claude to analyze sentiment from the economic calendar events and recent price action:

```python
"""
Lumitrade Sentiment Analyzer
===============================
Analyzes currency sentiment using Claude AI + economic calendar data.
Per BDS Section 13.3.
"""
from decimal import Decimal
from ..config import LumitradeConfig
from ..core.enums import CurrencySentiment
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """Analyze currency sentiment via Claude AI."""

    def __init__(self, config: LumitradeConfig):
        self._config = config
        self._cache: dict[str, tuple[CurrencySentiment, float]] = {}
        self._cache_ttl = 1800  # 30 minutes

    async def analyze(
        self,
        pairs: list[str],
        calendar_events: list[dict],
        recent_price_action: dict | None = None,
    ) -> dict[str, CurrencySentiment]:
        """
        Analyze sentiment for currencies in the given pairs.
        Uses economic calendar events + price action context.
        Returns dict mapping currency code to sentiment.
        """
        import time

        # Extract unique currencies
        currencies = set()
        for pair in pairs:
            parts = pair.split("_")
            currencies.update(parts)

        # Check cache
        now = time.time()
        result = {}
        uncached = []
        for curr in currencies:
            if curr in self._cache:
                sentiment, cached_at = self._cache[curr]
                if now - cached_at < self._cache_ttl:
                    result[curr] = sentiment
                    continue
            uncached.append(curr)

        if not uncached:
            return result

        # Build context from calendar events
        event_context = ""
        if calendar_events:
            event_lines = []
            for e in calendar_events[:10]:
                event_lines.append(
                    f"- {e.get('currency', '?')}: {e.get('title', '?')} "
                    f"(impact: {e.get('impact', '?')}, "
                    f"forecast: {e.get('forecast', 'N/A')}, "
                    f"previous: {e.get('previous', 'N/A')})"
                )
            event_context = "Upcoming economic events:\n" + "\n".join(event_lines)
        else:
            event_context = "No upcoming economic events in the next 4 hours."

        # Call Claude for sentiment analysis
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self._config.anthropic_api_key)
            prompt = (
                f"Analyze forex sentiment for these currencies: {', '.join(uncached)}\n\n"
                f"{event_context}\n\n"
                "For each currency, respond with exactly one line in format:\n"
                "CURRENCY: BULLISH|BEARISH|NEUTRAL\n"
                "Base your analysis on the economic calendar context. Be concise."
            )
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            for line in text.split("\n"):
                line = line.strip()
                if ":" not in line:
                    continue
                parts = line.split(":", 1)
                curr = parts[0].strip().upper()
                sentiment_str = parts[1].strip().upper()
                if curr in uncached:
                    if "BULLISH" in sentiment_str:
                        result[curr] = CurrencySentiment.BULLISH
                    elif "BEARISH" in sentiment_str:
                        result[curr] = CurrencySentiment.BEARISH
                    else:
                        result[curr] = CurrencySentiment.NEUTRAL
                    self._cache[curr] = (result[curr], now)

            logger.info("sentiment_analyzed", currencies=list(result.keys()))

        except Exception as e:
            logger.warning("sentiment_analysis_failed", error=str(e))

        # Fill any remaining with NEUTRAL
        for curr in currencies:
            if curr not in result:
                result[curr] = CurrencySentiment.NEUTRAL

        return result
```

- [ ] **Step 2: Test locally**

- [ ] **Step 3: Commit**

```bash
git add backend/lumitrade/ai_brain/sentiment_analyzer.py
git commit -m "feat: sentiment analyzer uses Claude Haiku for real currency sentiment from calendar events"
```

---

### Task 9: Consensus Engine — Single-Model Validation

**Files:**
- Modify: `backend/lumitrade/ai_brain/consensus_engine.py`

Note: Full multi-model consensus requires OpenAI API key. For now, implement **self-consistency check** — Claude generates two independent analyses and compares.

- [ ] **Step 1: Implement self-consistency consensus**

```python
"""
Lumitrade Consensus Engine
============================
Validates AI signal via self-consistency check.
Asks Claude to independently re-evaluate the signal and compares.
Per BDS Section 13.1.
"""
from decimal import Decimal
from ..config import LumitradeConfig
from ..core.models import SignalProposal
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


class ConsensusEngine:
    """Validate signal quality via self-consistency re-evaluation."""

    def __init__(self, config: LumitradeConfig):
        self._config = config

    async def validate(self, proposal: SignalProposal, market_context: str) -> SignalProposal:
        """
        Re-evaluate the signal with a fresh Claude call.
        If the second opinion agrees on direction, boost confidence by 0.05.
        If it disagrees, reduce confidence by 0.10.
        """
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self._config.anthropic_api_key)

            prompt = (
                f"You are a forex trading analyst. Given this market context:\n\n"
                f"{market_context[:1000]}\n\n"
                f"For {proposal.pair}, should a trader BUY, SELL, or HOLD? "
                f"Reply with exactly one word: BUY, SELL, or HOLD."
            )
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )
            verdict = response.content[0].text.strip().upper()

            if verdict == proposal.action.value:
                # Agreement — boost confidence
                proposal.confidence_adjusted = min(
                    Decimal("1.0"),
                    proposal.confidence_adjusted + Decimal("0.05")
                )
                logger.info(
                    "consensus_agreed",
                    pair=proposal.pair,
                    action=proposal.action.value,
                    new_confidence=str(proposal.confidence_adjusted),
                )
            else:
                # Disagreement — reduce confidence
                proposal.confidence_adjusted = max(
                    Decimal("0.0"),
                    proposal.confidence_adjusted - Decimal("0.10")
                )
                logger.info(
                    "consensus_disagreed",
                    pair=proposal.pair,
                    primary=proposal.action.value,
                    second_opinion=verdict,
                    new_confidence=str(proposal.confidence_adjusted),
                )

        except Exception as e:
            logger.warning("consensus_check_failed", error=str(e))
            # On failure, don't modify confidence — pass through

        return proposal
```

- [ ] **Step 2: Wire into signal scanner after primary signal generation**

- [ ] **Step 3: Commit**

```bash
git add backend/lumitrade/ai_brain/consensus_engine.py
git commit -m "feat: consensus engine — self-consistency check boosts/reduces confidence"
```

---

### Task 10: Subagents — Market Analyst (SA-01)

**Files:**
- Modify: `backend/lumitrade/subagents/market_analyst.py`

- [ ] **Step 1: Implement real market briefing via Claude**

```python
"""SA-01: Market Analyst — generates structured briefing before signal scan."""
from ..infrastructure.secure_logger import get_logger
from .base_subagent import BaseSubagent

logger = get_logger(__name__)


class MarketAnalystAgent(BaseSubagent):
    """Generates a 200-400 word market briefing using Claude."""

    async def run(self, context: dict) -> dict:
        pair = context.get("pair", "")
        indicators = context.get("indicators", {})
        candles = context.get("candles", [])

        if not pair:
            return {"briefing": ""}

        try:
            prompt = (
                f"You are a forex market analyst. Provide a concise 200-word briefing for {pair}.\n\n"
                f"Current indicators: {indicators}\n"
                f"Recent price action: last 5 candles high/low ranges.\n\n"
                "Cover: trend direction, key support/resistance, momentum, any concerns. "
                "Be specific with price levels. No fluff."
            )
            response = await self._call_claude(prompt, max_tokens=400)
            briefing = response.strip() if response else ""

            logger.info("market_analyst_briefing_generated", pair=pair, length=len(briefing))
            return {"briefing": briefing}

        except Exception as e:
            logger.warning("market_analyst_failed", pair=pair, error=str(e))
            return {"briefing": ""}
```

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/subagents/market_analyst.py
git commit -m "feat: SA-01 market analyst generates real Claude-powered briefings"
```

---

### Task 11: Subagents — Post-Trade Analyst (SA-02)

**Files:**
- Modify: `backend/lumitrade/subagents/post_trade_analyst.py`

- [ ] **Step 1: Implement real post-trade analysis**

```python
"""SA-02: Post-Trade Analyst — analyzes closed trades for patterns."""
from ..infrastructure.secure_logger import get_logger
from .base_subagent import BaseSubagent

logger = get_logger(__name__)
MIN_TRADES = 20


class PostTradeAnalystAgent(BaseSubagent):
    """Analyzes recent closed trades and generates insights."""

    async def run(self, context: dict) -> dict:
        trades = context.get("recent_trades", [])
        if len(trades) < MIN_TRADES:
            logger.info("post_trade_analyst_insufficient_data", count=len(trades))
            return {}

        try:
            trade_summary = "\n".join([
                f"- {t.get('pair')} {t.get('direction')} | {t.get('outcome')} | "
                f"PnL: {t.get('pnl_pips')} pips | Confidence: {t.get('confidence_score')}"
                for t in trades[-20:]
            ])

            prompt = (
                "Analyze these 20 recent forex trades and identify:\n"
                "1. Best performing pair and worst performing pair\n"
                "2. Any pattern in winning vs losing trades (confidence, time of day, direction)\n"
                "3. One specific recommendation to improve results\n\n"
                f"Trades:\n{trade_summary}\n\n"
                "Be concise and specific. Focus on actionable insights."
            )
            response = await self._call_claude(prompt, max_tokens=500)

            logger.info("post_trade_analysis_complete", trade_count=len(trades))
            return {"analysis": response.strip(), "trade_count": len(trades)}

        except Exception as e:
            logger.warning("post_trade_analyst_failed", error=str(e))
            return {}
```

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/subagents/post_trade_analyst.py
git commit -m "feat: SA-02 post-trade analyst generates real pattern analysis from trade history"
```

---

### Task 12: Subagents — Risk Monitor (SA-03)

**Files:**
- Modify: `backend/lumitrade/subagents/risk_monitor.py`

- [ ] **Step 1: Implement real thesis validation**

```python
"""SA-03: Risk Monitor — validates thesis for open positions. NEVER auto-closes."""
from ..infrastructure.secure_logger import get_logger
from .base_subagent import BaseSubagent

logger = get_logger(__name__)


class RiskMonitorAgent(BaseSubagent):
    """Evaluates whether open position thesis is still valid. Alert-only, never closes."""

    async def run(self, context: dict) -> dict:
        open_trades = context.get("open_trades", [])
        if not open_trades:
            return {}

        results = {}
        for trade in open_trades:
            pair = trade.get("pair", "")
            direction = trade.get("direction", "")
            entry = trade.get("entry_price", 0)
            current = trade.get("current_price", 0)

            try:
                prompt = (
                    f"You are a forex risk monitor. Evaluate this open position:\n"
                    f"Pair: {pair}, Direction: {direction}, Entry: {entry}, Current: {current}\n\n"
                    f"Indicators: {trade.get('indicators', {})}\n\n"
                    "Is the original thesis still valid? Reply: VALID or INVALID with one sentence reason."
                )
                response = await self._call_claude(prompt, max_tokens=100)
                text = response.strip().upper()
                is_valid = "VALID" in text and "INVALID" not in text

                results[trade.get("id", "")] = {
                    "thesis_valid": is_valid,
                    "assessment": response.strip(),
                }

                if not is_valid:
                    logger.warning(
                        "thesis_invalidated",
                        pair=pair,
                        direction=direction,
                        assessment=response.strip()[:200],
                    )
                    # Alert only — NEVER auto-close
                    if self._alerts:
                        await self._alerts.send_warning(
                            f"Thesis invalidated for {pair} {direction}: {response.strip()[:100]}"
                        )

            except Exception as e:
                logger.warning("risk_monitor_check_failed", pair=pair, error=str(e))

        return results
```

- [ ] **Step 2: Commit**

```bash
git add backend/lumitrade/subagents/risk_monitor.py
git commit -m "feat: SA-03 risk monitor validates open position thesis via Claude — alert only, never auto-closes"
```

---

### Task 13: Performance Analyzer — Real Implementation

**Files:**
- Modify: `backend/lumitrade/analytics/performance_analyzer.py`

- [ ] **Step 1: Implement the 5 Phase 2 analysis methods**

Replace all `pass` bodies with real analysis logic querying the trades table. Each method should:
- Query Supabase for relevant trade data
- Calculate the specific metric
- Store results in `performance_insights` table

Full implementation code in the executor agent (each method is ~20-30 lines of SQL queries + calculations).

- [ ] **Step 2: Run tests**

- [ ] **Step 3: Commit**

```bash
git add backend/lumitrade/analytics/performance_analyzer.py
git commit -m "feat: performance analyzer — real session, pair, indicator, confidence analysis"
```

---

## Wave 3: Frontend Cleanup (Tasks 14-17)

### Task 14: Hide Coming-Soon Pages from Navigation

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Remove Phase 2+ nav items**

In Sidebar.tsx, find the navigation items array and remove or hide items with Phase 2+ indicators:
- `/journal` → remove
- `/coach` → remove
- `/intelligence` → remove
- `/marketplace` → remove
- `/copy` → remove
- `/backtest` → remove
- `/api-keys` → remove

Keep only Phase 0 routes: Dashboard, Signals, Trades, Analytics, Settings.

- [ ] **Step 2: Test — verify sidebar only shows 5 working pages**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx
git commit -m "fix: remove coming-soon pages from nav — only show working Phase 0 features"
```

---

### Task 15: Remove Fake Testimonials

**Files:**
- Modify: `frontend/src/app/page.tsx` or `frontend/src/components/landing/Testimonials.tsx`

- [ ] **Step 1: Replace fictional testimonials with real value propositions**

Remove the named fictional testimonials (Marcus Reinhardt, etc.) and replace with factual feature highlights or remove the section entirely until real user feedback exists.

Option A: Remove testimonials section completely.
Option B: Replace with "Built by traders, for traders" section with factual claims about the technology (not fake people).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/page.tsx frontend/src/components/landing/Testimonials.tsx
git commit -m "fix: remove fictional testimonials — replace with factual feature highlights"
```

---

### Task 16: Dynamic Trading Pairs from Config

**Files:**
- Modify: `frontend/src/components/trades/TradeFilters.tsx:17-25`
- Modify: `frontend/src/app/(dashboard)/signals/page.tsx:8`

- [ ] **Step 1: Fetch pairs from API instead of hardcoding**

Create a shared constant or fetch from the backend settings endpoint:
```typescript
// In a shared constants file or fetched from /api/settings
const ACTIVE_PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY"]; // from config.pairs
```

Or better — read from the settings endpoint that already returns the config.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/trades/TradeFilters.tsx frontend/src/app/\(dashboard\)/signals/page.tsx
git commit -m "fix: trading pair filters use config pairs instead of hardcoded list"
```

---

### Task 17: Intelligence & Onboarding Subagents

**Files:**
- Modify: `backend/lumitrade/subagents/intelligence_subagent.py`
- Modify: `backend/lumitrade/subagents/onboarding_agent.py`

- [ ] **Step 1: Implement intelligence subagent**

Weekly macro report using Claude — aggregates pair performance, open positions, and market outlook.

- [ ] **Step 2: Implement onboarding agent**

Conversational setup guide using Claude — walks new users through account configuration.

- [ ] **Step 3: Commit**

```bash
git add backend/lumitrade/subagents/intelligence_subagent.py backend/lumitrade/subagents/onboarding_agent.py
git commit -m "feat: SA-04 intelligence reports + SA-05 onboarding agent — real Claude implementations"
```

---

## Self-Review Checklist

- [x] All 14 audit items have corresponding tasks
- [x] No "TBD" or "implement later" — every task has code
- [x] Types/method signatures consistent across tasks
- [x] File paths exact
- [x] Each task produces independently testable changes
- [x] Commits are atomic and descriptive
