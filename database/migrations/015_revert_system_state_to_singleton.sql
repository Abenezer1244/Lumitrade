-- Migration 015: Revert system_state to singleton fixed-column schema
--
-- Context: Codex full-system audit (2026-04-25) [critical] finding #1 —
-- Migration 007_system_state_kv.sql replaced the singleton fixed-column
-- table from migration 001 with a key/value table, but the Phase 6 Python
-- code in backend/lumitrade/state/manager.py and backend/lumitrade/state/lock.py
-- still uses the original singleton contract:
--   * select_one("system_state", {"id": "singleton"})
--   * upsert with flat columns: risk_state, open_trades, daily_pnl_usd,
--     instance_id, is_primary_instance, lock_expires_at, etc.
-- Plus a second row id='settings' that holds dashboard user settings
-- (riskPct, maxPositions, confidence, scanInterval, dashboard live-mode flag)
-- in the open_trades JSONB column. Read by main.py:561 and risk_engine/engine.py:597.
--
-- The KV-pattern Python code described in 007's comment never landed.
-- Migration 007 silently broke restore() and the distributed lock CAS path:
-- on a KV table, select_one returns None, lock acquisition always thinks
-- it is first, and persisted state is lost on restart.
--
-- Fix chosen: revert schema to the singleton pattern documented in
-- backend/lumitrade/state/manager.py:16-29.
--
-- IDEMPOTENT and NON-DESTRUCTIVE when the schema is already correct:
-- this migration only drops+recreates if the table is missing the 'id'
-- column (i.e., currently in the KV shape). When the singleton shape is
-- already in place, it is a no-op — preserving the dashboard's id='settings'
-- row and any live lock state.
--
-- DEPLOY PRECONDITION: stop the running engine before applying. Even
-- though this is no-op when the schema is correct, if the schema IS
-- wrong (KV) and the engine is running, dropping the table during a
-- live deploy can split-brain the lock. See Codex review 2026-04-25 follow-up.
--
-- DO NOT add another KV migration on top of this without also rewriting
-- state/manager.py and state/lock.py to use the JSONB pattern. The two
-- must move together.

DO $$
DECLARE
    -- Per Codex round-2 review of finding #1: verify the FULL contract that
    -- state/manager.py and state/lock.py actually access, not just the
    -- presence of 'id'. A half-migrated table with 'id' but missing
    -- risk_state / lock columns would otherwise be misclassified as healthy
    -- and the migration would not repair it (or would error at ON CONFLICT
    -- if 'id' lacks a unique/PK).
    required_columns TEXT[] := ARRAY[
        'id',
        'risk_state',
        'open_trades',
        'daily_pnl_usd',
        'weekly_pnl_usd',
        'consecutive_losses',
        'last_signal_time',
        'confidence_threshold_override',
        'is_primary_instance',
        'instance_id',
        'lock_expires_at',
        'updated_at'
        -- NOTE: kill_switch_active is intentionally NOT in this list.
        -- It was added after the original singleton contract, so a healthy
        -- pre-existing schema may not have it. The schema_intact path
        -- additively ensures it via ADD COLUMN IF NOT EXISTS below; the
        -- recreate path includes it in CREATE TABLE.
    ];
    present_count INT;
    has_id_pk BOOLEAN;
    table_exists BOOLEAN;
    schema_intact BOOLEAN := FALSE;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'system_state'
    ) INTO table_exists;

    IF table_exists THEN
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'system_state'
          AND column_name = ANY (required_columns)
        INTO present_count;

        -- PK must be on 'id' as the SOLE column. A composite PK that
        -- happens to include 'id' would otherwise satisfy a naive existence
        -- check but still break the ON CONFLICT (id) below. Per Codex
        -- round-3 review of finding #1.
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints tc
            WHERE tc.table_schema = 'public'
              AND tc.table_name = 'system_state'
              AND tc.constraint_type = 'PRIMARY KEY'
              AND (
                  SELECT array_agg(kcu.column_name ORDER BY kcu.ordinal_position)
                  FROM information_schema.key_column_usage kcu
                  WHERE kcu.constraint_name = tc.constraint_name
                    AND kcu.table_schema = tc.table_schema
              ) = ARRAY['id']
        ) INTO has_id_pk;

        schema_intact := (present_count = array_length(required_columns, 1)) AND has_id_pk;
    END IF;

    IF schema_intact THEN
        -- Full singleton contract already in place. No-op on the table shape,
        -- but additively add kill_switch_active if missing — it was added
        -- AFTER migration 001's original schema, so a deployed singleton
        -- table predating this work won't have it. Per Codex post-fix audit
        -- of finding #4. Idempotent.
        ALTER TABLE system_state
            ADD COLUMN IF NOT EXISTS kill_switch_active BOOLEAN NOT NULL DEFAULT FALSE;
        -- Make sure the singleton row exists (cheap insert-if-missing).
        INSERT INTO system_state (id) VALUES ('singleton')
        ON CONFLICT (id) DO NOTHING;
        RAISE NOTICE 'migration 015: system_state already matches singleton contract; ensured kill_switch_active column';
    ELSE
        -- KV schema (post-007), partially-migrated drift, or table missing.
        -- Recreate the singleton contract from scratch.
        RAISE NOTICE 'migration 015: system_state contract incomplete (present_count=%, has_id_pk=%); recreating singleton schema',
            COALESCE(present_count, 0), COALESCE(has_id_pk, FALSE);

        DROP TABLE IF EXISTS system_state CASCADE;

        CREATE TABLE system_state (
            id                            TEXT PRIMARY KEY DEFAULT 'singleton',
            risk_state                    TEXT NOT NULL DEFAULT 'NORMAL',
            open_trades                   JSONB NOT NULL DEFAULT '[]',
            pending_orders                JSONB NOT NULL DEFAULT '[]',
            daily_pnl_usd                 DECIMAL(12,2) NOT NULL DEFAULT 0,
            weekly_pnl_usd                DECIMAL(12,2) NOT NULL DEFAULT 0,
            daily_opening_balance         DECIMAL(12,2),
            weekly_opening_balance        DECIMAL(12,2),
            daily_trade_count             INT NOT NULL DEFAULT 0,
            consecutive_losses            INT NOT NULL DEFAULT 0,
            circuit_breaker_state         TEXT NOT NULL DEFAULT 'CLOSED',
            circuit_breaker_failures      INT NOT NULL DEFAULT 0,
            last_signal_time              JSONB NOT NULL DEFAULT '{}',
            confidence_threshold_override DECIMAL(5,4),
            is_primary_instance           BOOLEAN NOT NULL DEFAULT FALSE,
            instance_id                   TEXT,
            lock_expires_at               TIMESTAMPTZ,
            -- Kill switch: written by HTTP /kill-switch endpoint and engine
            -- save() / refresh path. Per finding #4 + post-fix Codex audit.
            kill_switch_active            BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        INSERT INTO system_state (id) VALUES ('singleton');

        ALTER TABLE system_state ENABLE ROW LEVEL SECURITY;
        -- Match migration 003's hardening: FORCE applies RLS even to the
        -- table owner. Without this, service-role queries bypass the
        -- deny-all policy. Per Codex round-4 review.
        ALTER TABLE system_state FORCE ROW LEVEL SECURITY;

        CREATE POLICY system_state_service_only ON system_state
            FOR ALL
            TO authenticated, anon
            USING (FALSE)
            WITH CHECK (FALSE);
    END IF;
END $$;
