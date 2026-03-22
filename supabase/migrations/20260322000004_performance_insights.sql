-- ============================================================================
-- Lumitrade: 004_performance_insights.sql
-- Addition Set 1A - Performance Insights Table
-- ============================================================================
-- Stores computed analytical insights derived from trade history and
-- performance snapshots. Used by the analytics engine and AI coach.
-- ============================================================================

CREATE TABLE performance_insights (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    insight_type    TEXT NOT NULL,
    -- e.g. 'WIN_STREAK', 'SESSION_PERFORMANCE', 'PAIR_ANALYSIS',
    --      'DRAWDOWN_WARNING', 'CONFIDENCE_CALIBRATION', 'RISK_EFFICIENCY'
    pair            TEXT,                -- NULL for account-wide insights
    session         TEXT,                -- NULL for cross-session insights
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    metric_name     TEXT NOT NULL,
    metric_value    DECIMAL(12,4) NOT NULL,
    benchmark_value DECIMAL(12,4),       -- comparison baseline
    deviation_pct   DECIMAL(8,4),        -- % deviation from benchmark
    sample_size     INT NOT NULL DEFAULT 0,
    is_actionable   BOOLEAN NOT NULL DEFAULT FALSE,
    recommendation  TEXT,                -- AI-generated suggestion
    detail          JSONB DEFAULT '{}',  -- additional structured data
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes for performance_insights
-- ---------------------------------------------------------------------------
CREATE INDEX idx_perf_insights_account_id
    ON performance_insights (account_id);
CREATE INDEX idx_perf_insights_type
    ON performance_insights (insight_type);
CREATE INDEX idx_perf_insights_account_type
    ON performance_insights (account_id, insight_type);
CREATE INDEX idx_perf_insights_pair
    ON performance_insights (pair) WHERE pair IS NOT NULL;
CREATE INDEX idx_perf_insights_session
    ON performance_insights (session) WHERE session IS NOT NULL;
CREATE INDEX idx_perf_insights_period
    ON performance_insights (period_start, period_end);
CREATE INDEX idx_perf_insights_actionable
    ON performance_insights (is_actionable) WHERE is_actionable = TRUE;
CREATE INDEX idx_perf_insights_created_at
    ON performance_insights (created_at DESC);

-- ---------------------------------------------------------------------------
-- RLS for performance_insights
-- ---------------------------------------------------------------------------
ALTER TABLE performance_insights ENABLE ROW LEVEL SECURITY;

CREATE POLICY perf_insights_service_only ON performance_insights
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

ALTER TABLE performance_insights FORCE ROW LEVEL SECURITY;
