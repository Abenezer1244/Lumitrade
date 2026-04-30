-- Migration: Partial scale-out tracking columns (2026-04-29)
-- See database/migrations/018_partial_close.sql for full context.

ALTER TABLE trades ADD COLUMN IF NOT EXISTS partial_closed BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS partial_close_price DECIMAL(18, 5);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS partial_close_units DECIMAL(12, 2);
