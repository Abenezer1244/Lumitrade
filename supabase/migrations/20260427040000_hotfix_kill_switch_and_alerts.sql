-- Migration 017: HOTFIX for production runtime errors observed on cutover day
-- (2026-04-27 03:39 UTC, engine in PAPER mode, state.save fails every 5s).
--
-- BUG #1 — system_state.kill_switch_active column missing.
--   Phase 6 code (state/manager.py: 64, 111, 167, 271, 410, 433) reads and
--   writes this column for hydrate + persist, but no migration ever created
--   it. The original singleton schema in 001_initial_schema.sql does not
--   declare it, and 015_revert_system_state_to_singleton.sql intentionally
--   excludes it from its precondition check (otherwise 015 would mis-classify
--   already-singleton tables as "broken" and recreate them, splitting brain
--   on lock state). Result: every state.save() upsert raises PGRST204 and
--   the engine has not been persisting kill-switch state, instance lock,
--   daily P&L, or trade list.
--
-- BUG #2 — alerts_log.account_id NOT NULL prevents system-level alerts.
--   alert_service._log_alert() does not pass account_id (system alerts have
--   no account context), but the schema requires it. Compare to
--   system_events.account_id which IS nullable in 001. Aligning alerts_log
--   with that pattern. The FK is preserved — only the NOT NULL is dropped.
--
-- IDEMPOTENT and NON-DESTRUCTIVE:
--   * Bug #1 ALTER uses IF NOT EXISTS + DEFAULT FALSE (sets the singleton
--     row's value safely; if column already exists, this is a no-op).
--   * Bug #2 ALTER drops a nullability constraint (no data loss possible).
--
-- DEPLOY ORDER:
--   1. Run this migration in Supabase SQL editor (safe to run while engine
--      is live; both ALTERs take a brief ACCESS EXCLUSIVE lock measured in
--      milliseconds on a singleton-row table).
--   2. Engine errors stop on the next state-persist cycle (5-second loop).
--   3. NO code change required. NO Railway redeploy required.
--
-- After this migration, schema matches Phase 6 code expectations and the
-- alert_service contract documented in BDS spec §11.

ALTER TABLE system_state
    ADD COLUMN IF NOT EXISTS kill_switch_active BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE alerts_log
    ALTER COLUMN account_id DROP NOT NULL;
