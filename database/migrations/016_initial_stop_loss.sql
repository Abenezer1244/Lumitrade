-- Migration 016: Add initial_stop_loss to trades for trailing-stop math
--
-- Context: Codex full-system audit (2026-04-25) finding [high] #5 —
-- ExecutionEngine._check_and_trail computes the trail distance as
-- abs(entry - current_sl). After breakeven moves SL to entry, that
-- distance collapses to zero, so the next monitor cycle moves SL
-- essentially to current market price and exits a winner on noise.
--
-- Fix: persist the ORIGINAL stop loss at trade open and trail from that
-- fixed value. Schema change: add initial_stop_loss column to trades.
-- Backfill existing OPEN trades from the current stop_loss as the best
-- available approximation; CLOSED trades are not used by the trailer.

ALTER TABLE trades ADD COLUMN IF NOT EXISTS initial_stop_loss DECIMAL(12,5);

-- Backfill: for OPEN rows where initial_stop_loss is NULL, copy the
-- current stop_loss. This is approximate for OPEN trades where the SL
-- has already moved (e.g. been trailed) but is the best we can do
-- without historical SL audit logs. Scoped to status='OPEN' only —
-- CLOSED trades are not consumed by the trailer, so backfilling them
-- adds no behavioral value. Per Codex round-1 review of finding #5.
UPDATE trades
SET initial_stop_loss = stop_loss
WHERE initial_stop_loss IS NULL
  AND stop_loss IS NOT NULL
  AND status = 'OPEN';
