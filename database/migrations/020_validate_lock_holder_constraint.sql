-- Migration 020: Promote the lock-holder lease guard to fully VALIDATED.
--
-- Context: migration 019 added system_state_instance_id_leased as NOT VALID so
-- it could be created while the singleton row still held the bare 'cloud-primary'
-- ghost token. The ghost was then evicted (2026-06-30 16:48 UTC) and the audited
-- engine took over as 'cloud-primary#<lease>'. With no bare value remaining
-- (singleton = composite, settings.instance_id = NULL), the constraint can now
-- be validated against existing rows — turning it from "enforced on new writes
-- only" into a fully-proven table invariant.
--
-- IDEMPOTENT: VALIDATE CONSTRAINT on an already-validated constraint is a no-op.
-- NON-DESTRUCTIVE: validation only scans/verifies; it modifies no data. Takes a
-- brief SHARE UPDATE EXCLUSIVE lock on a 2-row table.
--
-- DEPLOY: applied via `supabase db push` (twin at
-- supabase/migrations/20260630170000_validate_lock_holder_constraint.sql).

ALTER TABLE system_state
    VALIDATE CONSTRAINT system_state_instance_id_leased;
