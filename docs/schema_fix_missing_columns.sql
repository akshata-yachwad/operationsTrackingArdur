-- ─────────────────────────────────────────────────────────────
--  OpsTracking — two columns the models require but no migration creates.
--
--  Found by scripts/check_schema_drift.py after applying all 33 migrations
--  to a clean MySQL 8: the models declare these fields, yet no migration in
--  apps/*/migrations/ ever adds them. Django's autodetector stays silent
--  because both models are managed=False in production, and it skips field
--  changes on unmanaged models.
--
--  Consequence if you skip this: every SELECT against these models names the
--  column, so MySQL raises 1054 "Unknown column" and the page 500s.
--
--  Both statements are ADDITIVE. No column is dropped, altered, or renamed,
--  and no existing row loses data.
--
--  Run in phpMyAdmin (SQL tab) or:
--      mysql -u ardurdev -p ardurtechnology < docs/schema_fix_missing_columns.sql
--
--  Take the Phase 0 backup first.
-- ─────────────────────────────────────────────────────────────

-- apps/allocations/models.py:97
--   general_instructions = models.TextField(blank=True, null=True)
ALTER TABLE `ot_batch_allocations`
    ADD COLUMN `general_instructions` longtext NULL;

-- apps/accounts/models.py:140
--   alternate_phone = models.CharField(max_length=20, blank=True, default="")
--
-- Django's own schema editor emits a third statement here dropping the
-- default, because Django applies defaults in Python rather than in the
-- database. DO NOT run that statement on this table: the legacy Flask app is
-- still INSERTing into ot_employees and does not supply this column, so a
-- NOT NULL column with no default would break every Flask insert. Keeping the
-- default costs nothing and Django ignores it.
ALTER TABLE `ot_employees`
    ADD COLUMN `alternate_phone` varchar(20) NOT NULL DEFAULT '';

-- Verify:
--   SHOW COLUMNS FROM `ot_batch_allocations` LIKE 'general_instructions';
--   SHOW COLUMNS FROM `ot_employees` LIKE 'alternate_phone';
-- then re-run:  python scripts/check_schema_drift.py
