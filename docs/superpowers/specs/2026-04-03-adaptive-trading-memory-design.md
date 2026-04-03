# Adaptive Trading Memory + Visual Chart Analysis

## Overview

Two systems that make Lumitrade's AI learn from every trade and see charts like a human trader.

**System 1: Trading Memory** — After every trade closes, extract the pattern (pair, session, indicators, direction) and query historical results for that same pattern. If win rate < 35% over 5+ trades, create a BLOCK rule. If > 65%, create a BOOST rule. Rules are permanent and hard — BLOCK means the AI never sees the setup.

**System 2: Visual Chart Analysis** — Generate a multi-timeframe candlestick chart (H4/H1/M15) as a PNG image and send it to Claude alongside the text data. Claude analyzes visual patterns (engulfing candles, double bottoms, trendline breaks) like a human trader would.

## System 1: Trading Memory

### Database

New `trading_lessons` table:

```sql
CREATE TABLE trading_lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    pattern_key TEXT NOT NULL,        -- "BUY:USD_JPY:ASIAN:RSI_40_60"
    pair TEXT NOT NULL,
    direction TEXT NOT NULL,          -- BUY/SELL/ANY
    session TEXT,                     -- ASIAN/LONDON/NY/ANY
    indicator_conditions JSONB,       -- {"rsi_bracket": "40-60", "ema_alignment": "BULLISH"}
    rule_type TEXT NOT NULL,          -- BLOCK/BOOST
    win_count INT NOT NULL DEFAULT 0,
    loss_count INT NOT NULL DEFAULT 0,
    sample_size INT NOT NULL DEFAULT 0,
    win_rate DECIMAL(5,4),
    total_pnl DECIMAL(12,2),
    evidence TEXT,                    -- Human-readable summary
    created_from_trade_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(account_id, pattern_key)
);
```

### Lesson Extraction (after every trade close)

When a trade closes:

1. Capture entry conditions:
   - pair, direction
   - session (hour → ASIAN 0-8, LONDON 8-13, NY 13-21)
   - RSI bracket at entry (< 30, 30-40, 40-50, 50-60, 60-70, > 70)
   - EMA alignment (BULLISH: 20>50>200, BEARISH: 20<50<200, MIXED)
   - ATR bracket (LOW/NORMAL/HIGH relative to 20-period average)

2. Build pattern_key: `"{direction}:{pair}:{session}:{rsi_bracket}:{ema_alignment}"`
   - Also build broader keys: `"{direction}:{pair}:{session}"`, `"{direction}:{pair}"`

3. For each pattern_key, query ALL historical trades matching that pattern

4. Update or create lesson:
   - If win_rate < 0.35 AND sample_size >= 5 → rule_type = BLOCK
   - If win_rate > 0.65 AND sample_size >= 5 → rule_type = BOOST
   - If 0.35 <= win_rate <= 0.65 → rule_type = NEUTRAL (no action)

### Pre-Filter (before AI call)

Before calling Claude for a pair:

1. Determine current conditions (session, RSI bracket, EMA alignment)
2. Check ALL trading_lessons where rule_type = BLOCK
3. If ANY BLOCK rule matches current conditions → skip pair, log reason
4. Collect all BOOST rules → inject into AI prompt as preferred setups

### Seed Rules

Pre-load from 72-trade analysis:
- BLOCK: SELL:*:*:*:* (0% WR, 13 trades)
- BLOCK: *:*:NY:*:* (22% WR, 23 trades)
- BLOCK: *:GBP_USD:*:*:* (7% WR, 14 trades)
- BLOCK: *:EUR_USD:*:*:* (31% WR, 13 trades)
- BOOST: BUY:USD_JPY:ASIAN:*:* (80% WR, 5 trades)
- BOOST: BUY:USD_CAD:LONDON:*:* (100% WR, 3 trades)

## System 2: Visual Chart Analysis

### Chart Generation

Use matplotlib + mplfinance to generate a 3-panel chart:

- Panel 1: H4 candlesticks (20 bars) + EMA 20/50/200 + Bollinger Bands
- Panel 2: H1 candlesticks (20 bars) + support/resistance lines
- Panel 3: M15 candlesticks (20 bars) + RSI subplot

Output: PNG bytes in memory (no file I/O). Target size: ~800x1200px.

### Claude Multimodal Call

Send both image and text:

```python
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,
    system=system_prompt,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": chart_b64}},
            {"type": "text", "text": data_prompt},
        ]
    }]
)
```

### Chart-Specific Prompt Addition

```
VISUAL ANALYSIS INSTRUCTIONS:
You are receiving a multi-timeframe candlestick chart. Analyze it like a professional trader:
1. H4 (top): Identify the dominant trend. Look for trend continuation or reversal patterns.
2. H1 (middle): Identify key support/resistance levels. Is price at a decision point?
3. M15 (bottom): Look for entry timing patterns — pin bars, engulfing candles, breakouts.

Combine what you SEE in the chart with the indicator data below. If the chart shows a clear pattern that contradicts the indicators, trust the chart — price action is king.
```

### Token Cost

~$0.024 per scan vs $0.015 current. ~$3.40/day additional at 4 pairs x 4 scans/hr x 13 hours.

## Implementation Files

### Backend Changes
1. `backend/lumitrade/ai_brain/lesson_analyzer.py` — NEW: extract patterns, query history, create/update rules
2. `backend/lumitrade/ai_brain/lesson_filter.py` — NEW: pre-filter that checks BLOCK/BOOST rules
3. `backend/lumitrade/ai_brain/chart_generator.py` — NEW: matplotlib chart generation
4. `backend/lumitrade/ai_brain/scanner.py` — MODIFY: add lesson filter before AI, add chart to Claude call
5. `backend/lumitrade/ai_brain/claude_client.py` — MODIFY: support multimodal (image + text) messages
6. `backend/lumitrade/ai_brain/prompt_builder.py` — MODIFY: add chart analysis instructions + BOOST injection
7. `backend/lumitrade/execution_engine/engine.py` — MODIFY: call lesson_analyzer after trade closes

### Database Changes
8. New migration: `database/migrations/007_trading_lessons.sql`

### Frontend Changes
9. `frontend/src/app/(dashboard)/api/lessons/route.ts` — NEW: API to list/manage lessons
10. Dashboard component showing active rules (future phase)

## Dependencies

- `mplfinance` (pip install) — candlestick chart generation
- `matplotlib` — already available or easy to add
- No new frontend npm packages needed
