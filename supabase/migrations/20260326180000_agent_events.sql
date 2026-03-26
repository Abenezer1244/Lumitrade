-- Mission Control: Agent Events Table
-- Stores real-time activity from all 5 subagents + risk engine + execution engine
-- Frontend subscribes via Supabase Realtime for live feed

CREATE TABLE IF NOT EXISTS agent_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    account_id TEXT NOT NULL DEFAULT '7a281498-2f2e-5ecc-8583-70118edeff28',
    agent TEXT NOT NULL,          -- 'SA-01', 'SA-02', 'SA-03', 'SA-04', 'SA-05', 'RISK_ENGINE', 'EXECUTION', 'CLAUDE', 'CONSENSUS', 'SCANNER'
    event_type TEXT NOT NULL,     -- 'SCAN_START', 'BRIEFING', 'SIGNAL', 'RISK_CHECK', 'ORDER', 'TRADE_CLOSE', 'THESIS_CHECK', 'ALERT'
    pair TEXT,                    -- 'EUR_USD', 'GBP_USD', 'USD_JPY'
    severity TEXT DEFAULT 'INFO', -- 'INFO', 'WARNING', 'ERROR', 'SUCCESS'
    title TEXT NOT NULL,          -- Short one-line summary
    detail TEXT,                  -- Full detail text (briefing, reasoning, risk check breakdown)
    metadata JSONB DEFAULT '{}',  -- Structured data (confidence, prices, check results)
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast feed queries (newest first, per account)
CREATE INDEX IF NOT EXISTS idx_agent_events_feed
    ON agent_events (account_id, created_at DESC);

-- Auto-delete events older than 7 days to prevent table bloat
-- (Run via Supabase cron or manual cleanup)

-- Enable Realtime on this table
ALTER PUBLICATION supabase_realtime ADD TABLE agent_events;
