-- ============================================================================
-- Lumitrade: 003_add_rls_policies.sql
-- BDS Section 9.3 - Row Level Security Policies
-- ============================================================================
-- Lumitrade uses a service-role key for all backend operations.
-- RLS is enabled as defense-in-depth: the service role bypasses RLS,
-- but if the anon key is ever exposed, no data is accessible.
--
-- Policy pattern:
--   - All tables: RLS enabled
--   - service_role: full access (inherent Supabase behavior, bypasses RLS)
--   - anon/authenticated: denied by default (no policies grant access)
--   - system_state: extra restrictive (singleton, service-only)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Enable RLS on all tables
-- ---------------------------------------------------------------------------
ALTER TABLE accounts              ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals               ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades                ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_state          ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts_log            ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_events         ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_interaction_log    ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Deny-all policies for anon role
-- These explicitly block anonymous access. Even without these, RLS being
-- enabled with no permissive policies would block access, but explicit
-- deny policies make the intent clear.
-- ---------------------------------------------------------------------------

-- accounts: service-only read/write
CREATE POLICY accounts_service_only ON accounts
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- signals: service-only read/write
CREATE POLICY signals_service_only ON signals
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- trades: service-only read/write
CREATE POLICY trades_service_only ON trades
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- risk_events: service-only read/write
CREATE POLICY risk_events_service_only ON risk_events
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- system_state: absolute lockdown (singleton, critical state)
CREATE POLICY system_state_service_only ON system_state
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- performance_snapshots: service-only read/write
CREATE POLICY perf_snapshots_service_only ON performance_snapshots
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- execution_log: service-only write, no external reads
CREATE POLICY execution_log_service_only ON execution_log
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- alerts_log: service-only read/write
CREATE POLICY alerts_log_service_only ON alerts_log
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- system_events: service-only read/write
CREATE POLICY system_events_service_only ON system_events
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- ai_interaction_log: service-only read/write
CREATE POLICY ai_interaction_log_service_only ON ai_interaction_log
    FOR ALL
    TO authenticated, anon
    USING (FALSE)
    WITH CHECK (FALSE);

-- ---------------------------------------------------------------------------
-- Force RLS for table owners (prevents bypassing via ownership)
-- ---------------------------------------------------------------------------
ALTER TABLE accounts              FORCE ROW LEVEL SECURITY;
ALTER TABLE signals               FORCE ROW LEVEL SECURITY;
ALTER TABLE trades                FORCE ROW LEVEL SECURITY;
ALTER TABLE risk_events           FORCE ROW LEVEL SECURITY;
ALTER TABLE system_state          FORCE ROW LEVEL SECURITY;
ALTER TABLE performance_snapshots FORCE ROW LEVEL SECURITY;
ALTER TABLE execution_log         FORCE ROW LEVEL SECURITY;
ALTER TABLE alerts_log            FORCE ROW LEVEL SECURITY;
ALTER TABLE system_events         FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_interaction_log    FORCE ROW LEVEL SECURITY;
