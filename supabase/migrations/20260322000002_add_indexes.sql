-- ============================================================================
-- Lumitrade: 002_add_indexes.sql
-- BDS Section 9.2 - Performance Indexes
-- ============================================================================

-- ---------------------------------------------------------------------------
-- accounts indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_accounts_broker_account
    ON accounts (broker_account_id);
CREATE INDEX idx_accounts_is_active
    ON accounts (is_active) WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- signals indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_signals_account_id
    ON signals (account_id);
CREATE INDEX idx_signals_pair
    ON signals (pair);
CREATE INDEX idx_signals_created_at
    ON signals (created_at DESC);
CREATE INDEX idx_signals_account_pair_created
    ON signals (account_id, pair, created_at DESC);
CREATE INDEX idx_signals_executed
    ON signals (executed) WHERE executed = FALSE;
CREATE INDEX idx_signals_action
    ON signals (action);
CREATE INDEX idx_signals_confidence_adjusted
    ON signals (confidence_adjusted DESC);

-- ---------------------------------------------------------------------------
-- trades indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_trades_account_id
    ON trades (account_id);
CREATE INDEX idx_trades_signal_id
    ON trades (signal_id);
CREATE INDEX idx_trades_pair
    ON trades (pair);
CREATE INDEX idx_trades_status
    ON trades (status);
CREATE INDEX idx_trades_opened_at
    ON trades (opened_at DESC);
CREATE INDEX idx_trades_closed_at
    ON trades (closed_at DESC) WHERE closed_at IS NOT NULL;
CREATE INDEX idx_trades_account_status
    ON trades (account_id, status);
CREATE INDEX idx_trades_account_pair_opened
    ON trades (account_id, pair, opened_at DESC);
CREATE INDEX idx_trades_outcome
    ON trades (outcome) WHERE outcome IS NOT NULL;
CREATE INDEX idx_trades_mode
    ON trades (mode);
CREATE INDEX idx_trades_broker_trade_id
    ON trades (broker_trade_id) WHERE broker_trade_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- risk_events indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_risk_events_account_id
    ON risk_events (account_id);
CREATE INDEX idx_risk_events_event_type
    ON risk_events (event_type);
CREATE INDEX idx_risk_events_created_at
    ON risk_events (created_at DESC);
CREATE INDEX idx_risk_events_account_created
    ON risk_events (account_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- performance_snapshots indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_perf_snapshots_account_id
    ON performance_snapshots (account_id);
CREATE INDEX idx_perf_snapshots_date
    ON performance_snapshots (date DESC);
CREATE INDEX idx_perf_snapshots_account_date
    ON performance_snapshots (account_id, date DESC);

-- ---------------------------------------------------------------------------
-- execution_log indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_execution_log_account_id
    ON execution_log (account_id);
CREATE INDEX idx_execution_log_created_at
    ON execution_log (created_at DESC);
CREATE INDEX idx_execution_log_endpoint
    ON execution_log (endpoint);
CREATE INDEX idx_execution_log_response_code
    ON execution_log (response_code) WHERE response_code >= 400;
CREATE INDEX idx_execution_log_request_ref
    ON execution_log (request_ref) WHERE request_ref IS NOT NULL;

-- ---------------------------------------------------------------------------
-- alerts_log indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_alerts_log_account_id
    ON alerts_log (account_id);
CREATE INDEX idx_alerts_log_created_at
    ON alerts_log (created_at DESC);
CREATE INDEX idx_alerts_log_level
    ON alerts_log (level);
CREATE INDEX idx_alerts_log_delivered
    ON alerts_log (delivered) WHERE delivered = FALSE;

-- ---------------------------------------------------------------------------
-- system_events indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_system_events_account_id
    ON system_events (account_id) WHERE account_id IS NOT NULL;
CREATE INDEX idx_system_events_event_type
    ON system_events (event_type);
CREATE INDEX idx_system_events_created_at
    ON system_events (created_at DESC);

-- ---------------------------------------------------------------------------
-- ai_interaction_log indexes
-- ---------------------------------------------------------------------------
CREATE INDEX idx_ai_interaction_log_account_id
    ON ai_interaction_log (account_id) WHERE account_id IS NOT NULL;
CREATE INDEX idx_ai_interaction_log_created_at
    ON ai_interaction_log (created_at DESC);
CREATE INDEX idx_ai_interaction_log_prompt_hash
    ON ai_interaction_log (prompt_hash) WHERE prompt_hash IS NOT NULL;
CREATE INDEX idx_ai_interaction_log_agent_type
    ON ai_interaction_log (agent_type) WHERE agent_type IS NOT NULL;
CREATE INDEX idx_ai_interaction_log_model_used
    ON ai_interaction_log (model_used) WHERE model_used IS NOT NULL;
