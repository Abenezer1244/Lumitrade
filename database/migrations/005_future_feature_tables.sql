-- ============================================================================
-- Lumitrade: 005_future_feature_tables.sql
-- BDS Section 13.7 - Future Feature Tables
-- ============================================================================
-- These tables support planned features: trade journaling, intelligence
-- reports, market regime detection, sentiment analysis, AI coaching,
-- strategy marketplace, copy trading, backtesting, API access, and
-- fund management. Created now to avoid future migrations breaking
-- existing data.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. trade_journals - User trade annotations and reflections
-- ---------------------------------------------------------------------------
CREATE TABLE trade_journals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    trade_id        UUID REFERENCES trades(id) ON DELETE SET NULL,
    signal_id       UUID REFERENCES signals(id) ON DELETE SET NULL,
    pair            TEXT NOT NULL,
    direction       TEXT CHECK (direction IN ('BUY', 'SELL')),
    entry_notes     TEXT,
    exit_notes      TEXT,
    emotion_pre     TEXT,             -- e.g. 'CONFIDENT', 'ANXIOUS', 'NEUTRAL'
    emotion_post    TEXT,
    lessons_learned TEXT,
    rating          INT CHECK (rating BETWEEN 1 AND 5),
    tags            JSONB DEFAULT '[]',
    screenshots     JSONB DEFAULT '[]', -- URLs to chart screenshots
    ai_feedback     TEXT,               -- AI coach analysis of the trade
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 2. intelligence_reports - AI-generated market analysis reports
-- ---------------------------------------------------------------------------
CREATE TABLE intelligence_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID REFERENCES accounts(id) ON DELETE SET NULL,
    report_type     TEXT NOT NULL,
    -- e.g. 'DAILY_BRIEF', 'WEEKLY_REVIEW', 'PAIR_DEEP_DIVE', 'NEWS_ANALYSIS'
    title           TEXT NOT NULL,
    summary         TEXT NOT NULL,
    body            TEXT NOT NULL,       -- full report content (markdown)
    pairs_covered   JSONB DEFAULT '[]',
    timeframe       TEXT,                -- 'DAILY', 'WEEKLY', 'MONTHLY'
    key_findings    JSONB DEFAULT '[]',
    ai_model        TEXT,
    prompt_hash     TEXT,
    published_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 3. market_regimes - Detected market regime history
-- ---------------------------------------------------------------------------
CREATE TABLE market_regimes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pair            TEXT NOT NULL,
    regime          TEXT NOT NULL CHECK (regime IN (
        'TRENDING', 'RANGING', 'HIGH_VOLATILITY', 'LOW_LIQUIDITY', 'UNKNOWN'
    )),
    confidence      DECIMAL(5,4) NOT NULL,
    indicators_used JSONB DEFAULT '{}',
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,         -- NULL = still active
    duration_hours  INT,
    detail          JSONB DEFAULT '{}',
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 4. sentiment_snapshots - Currency/market sentiment over time
-- ---------------------------------------------------------------------------
CREATE TABLE sentiment_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    currency        TEXT NOT NULL,        -- e.g. 'EUR', 'USD', 'GBP'
    pair            TEXT,                 -- NULL for single-currency sentiment
    sentiment       TEXT NOT NULL CHECK (sentiment IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    score           DECIMAL(5,4) NOT NULL, -- -1.0 to +1.0
    sources         JSONB DEFAULT '{}',   -- what data sources contributed
    news_events     JSONB DEFAULT '[]',
    cot_data        JSONB DEFAULT '{}',   -- Commitment of Traders data
    retail_sentiment JSONB DEFAULT '{}',
    sample_time     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 5. coach_conversations - AI coaching chat history
-- ---------------------------------------------------------------------------
CREATE TABLE coach_conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    session_id      UUID NOT NULL,        -- groups messages in a conversation
    role            TEXT NOT NULL CHECK (role IN ('USER', 'COACH', 'SYSTEM')),
    content         TEXT NOT NULL,
    context         JSONB DEFAULT '{}',   -- trade/performance context provided
    ai_model        TEXT,
    tokens_used     INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 6. strategies - Trading strategy definitions (marketplace)
-- ---------------------------------------------------------------------------
CREATE TABLE strategies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    creator_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    strategy_type   TEXT NOT NULL,        -- 'MANUAL', 'RULE_BASED', 'AI_HYBRID'
    asset_class     TEXT NOT NULL CHECK (asset_class IN (
        'FOREX', 'CRYPTO', 'STOCKS', 'OPTIONS'
    )),
    pairs           JSONB DEFAULT '[]',
    risk_profile    TEXT NOT NULL CHECK (risk_profile IN (
        'CONSERVATIVE', 'MODERATE', 'AGGRESSIVE'
    )),
    parameters      JSONB DEFAULT '{}',
    entry_rules     JSONB DEFAULT '[]',
    exit_rules      JSONB DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT', 'PENDING', 'ACTIVE', 'PAUSED'
    )),
    is_public       BOOLEAN NOT NULL DEFAULT FALSE,
    subscriber_count INT NOT NULL DEFAULT 0,
    win_rate        DECIMAL(5,4),
    profit_factor   DECIMAL(8,4),
    max_drawdown    DECIMAL(5,4),
    version         INT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 7. strategy_subscriptions - Who follows which strategy
-- ---------------------------------------------------------------------------
CREATE TABLE strategy_subscriptions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    strategy_id     UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    risk_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.00,
    max_position_size INT,
    subscribed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ,
    UNIQUE (account_id, strategy_id)
);

-- ---------------------------------------------------------------------------
-- 8. copy_relationships - Copy trading linkages
-- ---------------------------------------------------------------------------
CREATE TABLE copy_relationships (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    leader_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    copier_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    risk_multiplier   DECIMAL(5,2) NOT NULL DEFAULT 1.00,
    max_position_pct  DECIMAL(5,4) NOT NULL DEFAULT 0.02, -- max % of balance per trade
    pairs_filter      JSONB DEFAULT '[]', -- empty = copy all pairs
    copied_trades     INT NOT NULL DEFAULT 0,
    total_pnl_usd     DECIMAL(12,2) NOT NULL DEFAULT 0,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at        TIMESTAMPTZ,
    UNIQUE (leader_account_id, copier_account_id)
);

-- ---------------------------------------------------------------------------
-- 9. backtest_runs - Backtesting execution metadata
-- ---------------------------------------------------------------------------
CREATE TABLE backtest_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    strategy_id     UUID REFERENCES strategies(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    pairs           JSONB NOT NULL DEFAULT '[]',
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    initial_balance DECIMAL(12,2) NOT NULL,
    parameters      JSONB DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'
    )),
    total_trades    INT,
    wins            INT,
    losses          INT,
    win_rate        DECIMAL(5,4),
    profit_factor   DECIMAL(8,4),
    max_drawdown    DECIMAL(5,4),
    sharpe_ratio    DECIMAL(8,4),
    total_pnl_usd   DECIMAL(12,2),
    final_balance   DECIMAL(12,2),
    execution_ms    INT,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 10. backtest_results - Individual trades from a backtest run
-- ---------------------------------------------------------------------------
CREATE TABLE backtest_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id          UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    trade_number    INT NOT NULL,
    pair            TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    entry_price     DECIMAL(12,5) NOT NULL,
    exit_price      DECIMAL(12,5) NOT NULL,
    stop_loss       DECIMAL(12,5) NOT NULL,
    take_profit     DECIMAL(12,5) NOT NULL,
    position_size   INT NOT NULL,
    pnl_pips        DECIMAL(8,2) NOT NULL,
    pnl_usd         DECIMAL(12,2) NOT NULL,
    outcome         TEXT NOT NULL CHECK (outcome IN ('WIN', 'LOSS', 'BREAKEVEN')),
    exit_reason     TEXT CHECK (exit_reason IN (
        'SL_HIT', 'TP_HIT', 'AI_CLOSE', 'MANUAL', 'EMERGENCY', 'UNKNOWN'
    )),
    confidence_score DECIMAL(5,4),
    opened_at       TIMESTAMPTZ NOT NULL,
    closed_at       TIMESTAMPTZ NOT NULL,
    duration_minutes INT
);

-- ---------------------------------------------------------------------------
-- 11. api_keys - Developer API access tokens
-- ---------------------------------------------------------------------------
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    key_hash        TEXT NOT NULL,        -- bcrypt/argon2 hash, never store plain
    key_prefix      TEXT NOT NULL,        -- first 8 chars for identification
    permissions     JSONB NOT NULL DEFAULT '["read"]',
    rate_limit_rpm  INT NOT NULL DEFAULT 60,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 12. webhook_endpoints - User-configured webhook delivery targets
-- ---------------------------------------------------------------------------
CREATE TABLE webhook_endpoints (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    secret_hash     TEXT NOT NULL,        -- HMAC signing secret hash
    events          JSONB NOT NULL DEFAULT '["trade.opened", "trade.closed"]',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_triggered  TIMESTAMPTZ,
    failure_count   INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 13. fund_accounts - Managed fund / pool accounts
-- ---------------------------------------------------------------------------
CREATE TABLE fund_accounts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    manager_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    strategy_id     UUID REFERENCES strategies(id) ON DELETE SET NULL,
    total_aum       DECIMAL(14,2) NOT NULL DEFAULT 0, -- assets under management
    investor_count  INT NOT NULL DEFAULT 0,
    performance_fee DECIMAL(5,4) NOT NULL DEFAULT 0.20, -- 20% default
    management_fee  DECIMAL(5,4) NOT NULL DEFAULT 0.02, -- 2% default
    high_water_mark DECIMAL(14,2) NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT', 'OPEN', 'CLOSED', 'LIQUIDATING'
    )),
    inception_date  DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes for future feature tables
-- ---------------------------------------------------------------------------

-- trade_journals
CREATE INDEX idx_trade_journals_account_id ON trade_journals (account_id);
CREATE INDEX idx_trade_journals_trade_id ON trade_journals (trade_id) WHERE trade_id IS NOT NULL;
CREATE INDEX idx_trade_journals_created_at ON trade_journals (created_at DESC);

-- intelligence_reports
CREATE INDEX idx_intel_reports_account_id ON intelligence_reports (account_id) WHERE account_id IS NOT NULL;
CREATE INDEX idx_intel_reports_type ON intelligence_reports (report_type);
CREATE INDEX idx_intel_reports_published_at ON intelligence_reports (published_at DESC);

-- market_regimes
CREATE INDEX idx_market_regimes_pair ON market_regimes (pair);
CREATE INDEX idx_market_regimes_regime ON market_regimes (regime);
CREATE INDEX idx_market_regimes_start_time ON market_regimes (start_time DESC);
CREATE INDEX idx_market_regimes_active ON market_regimes (pair, end_time) WHERE end_time IS NULL;

-- sentiment_snapshots
CREATE INDEX idx_sentiment_currency ON sentiment_snapshots (currency);
CREATE INDEX idx_sentiment_pair ON sentiment_snapshots (pair) WHERE pair IS NOT NULL;
CREATE INDEX idx_sentiment_sample_time ON sentiment_snapshots (sample_time DESC);

-- coach_conversations
CREATE INDEX idx_coach_conv_account_id ON coach_conversations (account_id);
CREATE INDEX idx_coach_conv_session_id ON coach_conversations (session_id);
CREATE INDEX idx_coach_conv_created_at ON coach_conversations (created_at DESC);

-- strategies
CREATE INDEX idx_strategies_creator_id ON strategies (creator_id);
CREATE INDEX idx_strategies_status ON strategies (status);
CREATE INDEX idx_strategies_public ON strategies (is_public) WHERE is_public = TRUE;
CREATE INDEX idx_strategies_asset_class ON strategies (asset_class);

-- strategy_subscriptions
CREATE INDEX idx_strat_subs_account_id ON strategy_subscriptions (account_id);
CREATE INDEX idx_strat_subs_strategy_id ON strategy_subscriptions (strategy_id);
CREATE INDEX idx_strat_subs_active ON strategy_subscriptions (is_active) WHERE is_active = TRUE;

-- copy_relationships
CREATE INDEX idx_copy_rel_leader ON copy_relationships (leader_account_id);
CREATE INDEX idx_copy_rel_copier ON copy_relationships (copier_account_id);
CREATE INDEX idx_copy_rel_active ON copy_relationships (is_active) WHERE is_active = TRUE;

-- backtest_runs
CREATE INDEX idx_backtest_runs_account_id ON backtest_runs (account_id);
CREATE INDEX idx_backtest_runs_strategy_id ON backtest_runs (strategy_id) WHERE strategy_id IS NOT NULL;
CREATE INDEX idx_backtest_runs_status ON backtest_runs (status);
CREATE INDEX idx_backtest_runs_created_at ON backtest_runs (created_at DESC);

-- backtest_results
CREATE INDEX idx_backtest_results_run_id ON backtest_results (run_id);
CREATE INDEX idx_backtest_results_outcome ON backtest_results (outcome);

-- api_keys
CREATE INDEX idx_api_keys_account_id ON api_keys (account_id);
CREATE INDEX idx_api_keys_prefix ON api_keys (key_prefix);
CREATE INDEX idx_api_keys_active ON api_keys (is_active) WHERE is_active = TRUE;

-- webhook_endpoints
CREATE INDEX idx_webhooks_account_id ON webhook_endpoints (account_id);
CREATE INDEX idx_webhooks_active ON webhook_endpoints (is_active) WHERE is_active = TRUE;

-- fund_accounts
CREATE INDEX idx_fund_accounts_manager_id ON fund_accounts (manager_id);
CREATE INDEX idx_fund_accounts_status ON fund_accounts (status);
CREATE INDEX idx_fund_accounts_strategy_id ON fund_accounts (strategy_id) WHERE strategy_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- RLS for all future feature tables
-- ---------------------------------------------------------------------------
ALTER TABLE trade_journals         ENABLE ROW LEVEL SECURITY;
ALTER TABLE intelligence_reports   ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_regimes         ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentiment_snapshots    ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_conversations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategies             ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE copy_relationships     ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_runs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_results       ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys               ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_endpoints      ENABLE ROW LEVEL SECURITY;
ALTER TABLE fund_accounts          ENABLE ROW LEVEL SECURITY;

CREATE POLICY trade_journals_service_only ON trade_journals
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY intel_reports_service_only ON intelligence_reports
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY market_regimes_service_only ON market_regimes
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY sentiment_service_only ON sentiment_snapshots
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY coach_conv_service_only ON coach_conversations
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY strategies_service_only ON strategies
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY strat_subs_service_only ON strategy_subscriptions
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY copy_rel_service_only ON copy_relationships
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY backtest_runs_service_only ON backtest_runs
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY backtest_results_service_only ON backtest_results
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY api_keys_service_only ON api_keys
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY webhooks_service_only ON webhook_endpoints
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY fund_accounts_service_only ON fund_accounts
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);

ALTER TABLE trade_journals         FORCE ROW LEVEL SECURITY;
ALTER TABLE intelligence_reports   FORCE ROW LEVEL SECURITY;
ALTER TABLE market_regimes         FORCE ROW LEVEL SECURITY;
ALTER TABLE sentiment_snapshots    FORCE ROW LEVEL SECURITY;
ALTER TABLE coach_conversations    FORCE ROW LEVEL SECURITY;
ALTER TABLE strategies             FORCE ROW LEVEL SECURITY;
ALTER TABLE strategy_subscriptions FORCE ROW LEVEL SECURITY;
ALTER TABLE copy_relationships     FORCE ROW LEVEL SECURITY;
ALTER TABLE backtest_runs          FORCE ROW LEVEL SECURITY;
ALTER TABLE backtest_results       FORCE ROW LEVEL SECURITY;
ALTER TABLE api_keys               FORCE ROW LEVEL SECURITY;
ALTER TABLE webhook_endpoints      FORCE ROW LEVEL SECURITY;
ALTER TABLE fund_accounts          FORCE ROW LEVEL SECURITY;
