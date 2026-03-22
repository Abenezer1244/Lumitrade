-- ============================================================================
-- Lumitrade: 001_initial_schema.sql
-- BDS Section 9.1 - Core Domain Tables
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- accounts
-- ---------------------------------------------------------------------------
CREATE TABLE accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_name      TEXT NOT NULL,
    broker          TEXT NOT NULL DEFAULT 'OANDA',
    broker_account_id TEXT NOT NULL,
    account_type    TEXT NOT NULL CHECK (account_type IN ('PRACTICE', 'LIVE')),
    base_currency   TEXT NOT NULL DEFAULT 'USD',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- signals
-- ---------------------------------------------------------------------------
CREATE TABLE signals (
    id                        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id                UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    pair                      TEXT NOT NULL,
    action                    TEXT NOT NULL CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    confidence_raw            DECIMAL(5,4) NOT NULL,
    confidence_adjusted       DECIMAL(5,4) NOT NULL,
    confidence_adjustment_log JSONB DEFAULT '{}',
    entry_price               DECIMAL(12,5) NOT NULL,
    stop_loss                 DECIMAL(12,5) NOT NULL,
    take_profit               DECIMAL(12,5) NOT NULL,
    summary                   TEXT NOT NULL,
    reasoning                 TEXT,
    indicators_snapshot       JSONB DEFAULT '{}',
    timeframe_scores          JSONB DEFAULT '{}',
    key_levels                JSONB DEFAULT '[]',
    news_context              JSONB DEFAULT '[]',
    session                   TEXT,
    spread_pips               DECIMAL(6,2),
    executed                  BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reason          TEXT,
    generation_method         TEXT NOT NULL DEFAULT 'AI',
    ai_prompt_hash            TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- trades
-- ---------------------------------------------------------------------------
CREATE TABLE trades (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id       UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    signal_id        UUID REFERENCES signals(id) ON DELETE SET NULL,
    broker_trade_id  TEXT,
    pair             TEXT NOT NULL,
    direction        TEXT NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    mode             TEXT NOT NULL CHECK (mode IN ('PAPER', 'LIVE')),
    entry_price      DECIMAL(12,5) NOT NULL,
    exit_price       DECIMAL(12,5),
    stop_loss        DECIMAL(12,5) NOT NULL,
    take_profit      DECIMAL(12,5) NOT NULL,
    position_size    INT NOT NULL,
    confidence_score DECIMAL(5,4),
    slippage_pips    DECIMAL(6,2),
    pnl_pips         DECIMAL(8,2),
    pnl_usd          DECIMAL(12,2),
    status           TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),
    exit_reason      TEXT CHECK (exit_reason IN ('SL_HIT', 'TP_HIT', 'AI_CLOSE', 'MANUAL', 'EMERGENCY', 'UNKNOWN')),
    outcome          TEXT CHECK (outcome IN ('WIN', 'LOSS', 'BREAKEVEN')),
    session          TEXT,
    opened_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at        TIMESTAMPTZ,
    duration_minutes INT
);

-- ---------------------------------------------------------------------------
-- risk_events
-- ---------------------------------------------------------------------------
CREATE TABLE risk_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id  UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    signal_id   UUID REFERENCES signals(id) ON DELETE SET NULL,
    event_type  TEXT NOT NULL,
    detail      TEXT,
    risk_state  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- system_state (singleton pattern)
-- ---------------------------------------------------------------------------
CREATE TABLE system_state (
    id                           TEXT PRIMARY KEY DEFAULT 'singleton',
    risk_state                   TEXT NOT NULL DEFAULT 'NORMAL',
    open_trades                  JSONB NOT NULL DEFAULT '[]',
    pending_orders               JSONB NOT NULL DEFAULT '[]',
    daily_pnl_usd               DECIMAL(12,2) NOT NULL DEFAULT 0,
    weekly_pnl_usd              DECIMAL(12,2) NOT NULL DEFAULT 0,
    daily_opening_balance        DECIMAL(12,2),
    weekly_opening_balance       DECIMAL(12,2),
    daily_trade_count            INT NOT NULL DEFAULT 0,
    consecutive_losses           INT NOT NULL DEFAULT 0,
    circuit_breaker_state        TEXT NOT NULL DEFAULT 'CLOSED',
    circuit_breaker_failures     INT NOT NULL DEFAULT 0,
    last_signal_time             JSONB NOT NULL DEFAULT '{}',
    confidence_threshold_override DECIMAL(5,4),
    is_primary_instance          BOOLEAN NOT NULL DEFAULT FALSE,
    instance_id                  TEXT,
    lock_expires_at              TIMESTAMPTZ,
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert the singleton row
INSERT INTO system_state (id) VALUES ('singleton');

-- ---------------------------------------------------------------------------
-- performance_snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE performance_snapshots (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id        UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    date              DATE NOT NULL,
    starting_balance  DECIMAL(12,2) NOT NULL,
    ending_balance    DECIMAL(12,2) NOT NULL,
    total_trades      INT NOT NULL DEFAULT 0,
    wins              INT NOT NULL DEFAULT 0,
    losses            INT NOT NULL DEFAULT 0,
    breakevens        INT NOT NULL DEFAULT 0,
    win_rate          DECIMAL(5,4),
    profit_factor     DECIMAL(8,4),
    max_drawdown_pct  DECIMAL(5,4),
    total_pnl_usd     DECIMAL(12,2) NOT NULL DEFAULT 0,
    UNIQUE (account_id, date)
);

-- ---------------------------------------------------------------------------
-- execution_log
-- ---------------------------------------------------------------------------
CREATE TABLE execution_log (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id     UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    endpoint       TEXT NOT NULL,
    method         TEXT NOT NULL,
    request_ref    TEXT,
    response_code  INT,
    latency_ms     INT,
    error_message  TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- alerts_log
-- ---------------------------------------------------------------------------
CREATE TABLE alerts_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id  UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    level       TEXT NOT NULL,
    message     TEXT NOT NULL,
    channel     TEXT NOT NULL,
    delivered   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- system_events
-- ---------------------------------------------------------------------------
CREATE TABLE system_events (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id   UUID,
    event_type   TEXT NOT NULL,
    detail       TEXT,
    triggered_by TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- ai_interaction_log
-- ---------------------------------------------------------------------------
CREATE TABLE ai_interaction_log (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id        UUID,
    prompt_hash       TEXT,
    response_text     TEXT,
    validation_result TEXT,
    retry_count       INT NOT NULL DEFAULT 0,
    latency_ms        INT,
    model_used        TEXT,
    agent_type        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
