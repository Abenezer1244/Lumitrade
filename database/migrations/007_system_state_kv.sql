-- Migration 007: Convert system_state to key-value pattern
-- The Phase 6 Python code (state/manager.py, state/lock.py) uses a key-value
-- pattern with {"key": "engine_state"} and {"key": "engine_lock"} rows.
-- The original migration 001 created a fixed-column singleton pattern.
-- This migration drops the old table and creates the key-value version.

-- Drop existing system_state (singleton row with fixed columns)
DROP TABLE IF EXISTS system_state CASCADE;

-- Create key-value system_state table
CREATE TABLE system_state (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- No singleton insert needed — the Python code creates rows on first use
-- via upsert when the engine starts.
