-- ============================================================================
-- Lumitrade: 006_subagent_tables.sql
-- BDS Section 16.7 - Sub-Agent Infrastructure Tables
-- ============================================================================
-- These tables support the multi-agent architecture: analyst briefings
-- produced by the Market Analyst sub-agent, risk monitoring logs from
-- the Risk Monitor sub-agent, and onboarding session tracking from the
-- Onboarding sub-agent.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- analyst_briefings - Market Analyst sub-agent output
-- ---------------------------------------------------------------------------
CREATE TABLE analyst_briefings (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id        UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    pair              TEXT NOT NULL,
    session           TEXT,
    briefing_type     TEXT NOT NULL,
    -- e.g. 'PRE_SESSION', 'MID_SESSION', 'POST_SESSION', 'AD_HOC'
    market_regime     TEXT,
    sentiment         TEXT,
    key_levels        JSONB DEFAULT '[]',
    economic_events   JSONB DEFAULT '[]',
    technical_summary TEXT,
    fundamental_summary TEXT,
    risk_factors      JSONB DEFAULT '[]',
    trade_ideas       JSONB DEFAULT '[]',
    confidence        DECIMAL(5,4),
    ai_model          TEXT,
    prompt_hash       TEXT,
    latency_ms        INT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- risk_monitor_log - Risk Monitor sub-agent output
-- ---------------------------------------------------------------------------
CREATE TABLE risk_monitor_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id          UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    check_type          TEXT NOT NULL,
    -- e.g. 'POSITION_REVIEW', 'DRAWDOWN_CHECK', 'CORRELATION_CHECK',
    --      'EXPOSURE_AUDIT', 'SL_VALIDATION', 'NEWS_PROXIMITY'
    status              TEXT NOT NULL CHECK (status IN ('PASS', 'WARNING', 'CRITICAL', 'ERROR')),
    risk_state_before   TEXT,
    risk_state_after    TEXT,
    open_positions      INT,
    total_exposure_usd  DECIMAL(14,2),
    drawdown_pct        DECIMAL(5,4),
    findings            JSONB DEFAULT '[]',
    actions_taken       JSONB DEFAULT '[]',
    -- e.g. [{"action": "TIGHTEN_SL", "trade_id": "...", "reason": "..."}]
    recommendations     JSONB DEFAULT '[]',
    ai_model            TEXT,
    prompt_hash         TEXT,
    latency_ms          INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- onboarding_sessions - Onboarding sub-agent session tracking
-- ---------------------------------------------------------------------------
CREATE TABLE onboarding_sessions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id          UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    session_type        TEXT NOT NULL,
    -- e.g. 'INITIAL_SETUP', 'RISK_PROFILE', 'STRATEGY_SELECTION',
    --      'BROKER_CONNECT', 'TUTORIAL', 'FEATURE_TOUR'
    status              TEXT NOT NULL DEFAULT 'IN_PROGRESS' CHECK (status IN (
        'IN_PROGRESS', 'COMPLETED', 'SKIPPED', 'ABANDONED'
    )),
    step_current        INT NOT NULL DEFAULT 1,
    step_total          INT NOT NULL,
    responses           JSONB DEFAULT '{}',  -- user answers/selections
    preferences_set     JSONB DEFAULT '{}',  -- preferences configured during onboarding
    risk_profile_result JSONB DEFAULT '{}',  -- computed risk profile
    completion_pct      DECIMAL(5,2) NOT NULL DEFAULT 0,
    ai_model            TEXT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes for sub-agent tables
-- ---------------------------------------------------------------------------

-- analyst_briefings
CREATE INDEX idx_analyst_briefings_account_id
    ON analyst_briefings (account_id);
CREATE INDEX idx_analyst_briefings_pair
    ON analyst_briefings (pair);
CREATE INDEX idx_analyst_briefings_type
    ON analyst_briefings (briefing_type);
CREATE INDEX idx_analyst_briefings_account_pair
    ON analyst_briefings (account_id, pair, created_at DESC);
CREATE INDEX idx_analyst_briefings_created_at
    ON analyst_briefings (created_at DESC);
CREATE INDEX idx_analyst_briefings_session
    ON analyst_briefings (session) WHERE session IS NOT NULL;

-- risk_monitor_log
CREATE INDEX idx_risk_monitor_account_id
    ON risk_monitor_log (account_id);
CREATE INDEX idx_risk_monitor_check_type
    ON risk_monitor_log (check_type);
CREATE INDEX idx_risk_monitor_status
    ON risk_monitor_log (status);
CREATE INDEX idx_risk_monitor_critical
    ON risk_monitor_log (status) WHERE status IN ('WARNING', 'CRITICAL');
CREATE INDEX idx_risk_monitor_account_created
    ON risk_monitor_log (account_id, created_at DESC);
CREATE INDEX idx_risk_monitor_created_at
    ON risk_monitor_log (created_at DESC);

-- onboarding_sessions
CREATE INDEX idx_onboarding_account_id
    ON onboarding_sessions (account_id);
CREATE INDEX idx_onboarding_status
    ON onboarding_sessions (status);
CREATE INDEX idx_onboarding_type
    ON onboarding_sessions (session_type);
CREATE INDEX idx_onboarding_account_status
    ON onboarding_sessions (account_id, status);
CREATE INDEX idx_onboarding_created_at
    ON onboarding_sessions (created_at DESC);

-- ---------------------------------------------------------------------------
-- RLS for sub-agent tables
-- ---------------------------------------------------------------------------
ALTER TABLE analyst_briefings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_monitor_log    ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY analyst_briefings_service_only ON analyst_briefings
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY risk_monitor_service_only ON risk_monitor_log
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);
CREATE POLICY onboarding_service_only ON onboarding_sessions
    FOR ALL TO authenticated, anon USING (FALSE) WITH CHECK (FALSE);

ALTER TABLE analyst_briefings   FORCE ROW LEVEL SECURITY;
ALTER TABLE risk_monitor_log    FORCE ROW LEVEL SECURITY;
ALTER TABLE onboarding_sessions FORCE ROW LEVEL SECURITY;
