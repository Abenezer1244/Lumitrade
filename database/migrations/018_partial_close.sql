-- Migration 018: Partial scale-out tracking columns
--
-- Context: 2026-04-29 sweep showed partial close at 1.5×RR / 67% improves
-- all metrics for USD_CAD (PF 1.96→2.00, Sharpe 1.76→1.94) and USD_JPY
-- (PF 1.04→1.23, MAR 0.07→0.50 — crossing the live threshold).
--
-- Three columns added to trades:
--   partial_closed       — TRUE once partial scale-out has executed
--   partial_close_price  — mid-price at the moment of partial close
--   partial_close_units  — units removed from the position (logged for audit)
--
-- Gate: partial close is off by default (partial_close_enabled=False in config).
-- Enable only after confirming DB migration has run on all environments.

ALTER TABLE trades ADD COLUMN IF NOT EXISTS partial_closed BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS partial_close_price DECIMAL(18, 5);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS partial_close_units DECIMAL(12, 2);
