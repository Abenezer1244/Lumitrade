-- Promote the lock-holder lease guard to fully VALIDATED.
-- Twin of database/migrations/020_validate_lock_holder_constraint.sql.
-- After the ghost eviction (2026-06-30) the singleton row holds a composite
-- token and settings.instance_id is NULL, so the NOT VALID constraint from
-- migration 20260629223000 can be validated against existing rows.
-- Idempotent (no-op if already validated), non-destructive (verification only).

ALTER TABLE system_state
    VALIDATE CONSTRAINT system_state_instance_id_leased;
