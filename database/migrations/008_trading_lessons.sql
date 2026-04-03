-- Migration 008: Trading Lessons (Adaptive Trading Memory)
-- Stores learned patterns from historical trade outcomes.
-- BLOCK rules prevent the AI from seeing losing setups.
-- BOOST rules inject preferred setups into the AI prompt.

CREATE TABLE IF NOT EXISTS trading_lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    pattern_key TEXT NOT NULL,
    pair TEXT NOT NULL,
    direction TEXT NOT NULL,
    session TEXT,
    indicator_conditions JSONB DEFAULT '{}',
    rule_type TEXT NOT NULL CHECK (rule_type IN ('BLOCK', 'BOOST', 'NEUTRAL')),
    win_count INT NOT NULL DEFAULT 0,
    loss_count INT NOT NULL DEFAULT 0,
    sample_size INT NOT NULL DEFAULT 0,
    win_rate DECIMAL(5,4),
    total_pnl DECIMAL(12,2) DEFAULT 0,
    evidence TEXT,
    created_from_trade_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(account_id, pattern_key)
);

-- Indexes for fast lookup during pre-filter checks
CREATE INDEX IF NOT EXISTS idx_trading_lessons_account_id ON trading_lessons(account_id);
CREATE INDEX IF NOT EXISTS idx_trading_lessons_pattern_key ON trading_lessons(pattern_key);
CREATE INDEX IF NOT EXISTS idx_trading_lessons_rule_type ON trading_lessons(rule_type);
CREATE INDEX IF NOT EXISTS idx_trading_lessons_pair_direction ON trading_lessons(pair, direction);

-- Enable RLS
ALTER TABLE trading_lessons ENABLE ROW LEVEL SECURITY;

-- Service-role policy: full access for backend service
CREATE POLICY trading_lessons_service_policy ON trading_lessons
    FOR ALL
    USING (TRUE)
    WITH CHECK (TRUE);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_trading_lessons_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_trading_lessons_updated_at
    BEFORE UPDATE ON trading_lessons
    FOR EACH ROW
    EXECUTE FUNCTION update_trading_lessons_updated_at();
