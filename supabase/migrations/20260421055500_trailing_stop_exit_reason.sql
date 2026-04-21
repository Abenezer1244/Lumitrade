-- Migration 014: Add TRAILING_STOP to exit_reason enum check constraint
--
-- Context: Turtle strategy closes most winning trades via OANDA's trailing
-- stop. Previously these were classified as UNKNOWN by the reconciler's
-- ghost-trade path, which broke 22% of audit attribution. Reconciler now
-- writes TRAILING_STOP / SL_HIT / TP_HIT based on OANDA's fill reason,
-- and the column constraint needs to accept the new value.

ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_exit_reason_check;

ALTER TABLE trades
    ADD CONSTRAINT trades_exit_reason_check
    CHECK (exit_reason IN (
        'SL_HIT',
        'TP_HIT',
        'TRAILING_STOP',
        'AI_CLOSE',
        'MANUAL',
        'EMERGENCY',
        'UNKNOWN'
    ));
