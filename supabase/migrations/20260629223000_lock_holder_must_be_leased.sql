-- Lock holder token must be lease-qualified (permanent guard + ghost eviction).
-- Twin of database/migrations/019_lock_holder_must_be_leased.sql — see that file
-- for the full incident context (2026-06-29 bare-token "ghost" lock holder).
--
-- Forbids any non-lease value in system_state.instance_id. The audited
-- lock.py always writes '<INSTANCE_ID>#<12-hex-lease>' or NULL, so this never
-- blocks the real engine; it permanently blocks pre-lease (bare-token) code and
-- evicts the current ghost (its 60s renewal UPDATE fails -> lease expires ->
-- audited engine takes over). Enforced even for the service role (CHECK
-- constraints are not bypassed by BYPASSRLS). Added NOT VALID so the currently
-- bare singleton row is tolerated while the constraint enforces on every new
-- write. After takeover (no bare value remains), run:
--   ALTER TABLE system_state VALIDATE CONSTRAINT system_state_instance_id_leased;
-- NOTE: this evicts DB leadership only — rotate the OANDA token to fully retire
-- the rogue host.

ALTER TABLE system_state
    DROP CONSTRAINT IF EXISTS system_state_instance_id_leased;

ALTER TABLE system_state
    ADD CONSTRAINT system_state_instance_id_leased
    CHECK (instance_id IS NULL OR instance_id ~ '^[^#]+#[0-9a-f]{12}$')
    NOT VALID;
