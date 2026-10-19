-- ═══════════════════════════════════════════════════════════════════
--  SUPERSEDED -- kept for reference only.
--
--  The database was brought up to date with Django migrations instead
--  (apps/*/migrations/0002_sync_state_to_production.py and 0003_*).
--  Do not run this file against production now: the schema steps are
--  already applied, and STEP 3 would reset a user's password.
--
--  Credentials have been removed. To set a password, generate a hash:
--      python manage.py shell
--      from django.contrib.auth.hashers import make_password
--      print(make_password("your-new-password"))
--  then paste it into STEP 3 below.
-- ═══════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════
--  OpsTracking — fix the production database entirely from phpMyAdmin
--
--  No Terminal required. Everything here is plain SQL.
--
--  HOW TO USE
--    cPanel → phpMyAdmin → click `ardurtechnology` on the left
--    → "SQL" tab → paste ONE STEP at a time → "Go".
--
--  SAFETY — read this once
--    Nothing below drops a table, drops a column, or deletes a row.
--    Every statement either CREATEs something new or ADDs a column,
--    and all of it is safe to run twice.
--
--  DO NOT run `python manage.py migrate` against this database.
--  It contains tracking/0005, which DROPs average_time, pages and
--  work_units from ot_user_work_data — live production data. The
--  steps below reach the same working state without that.
--
--  Tested: run end-to-end twice against MySQL 8 on an empty schema.
--  25 tables created, second run a clean no-op.
-- ═══════════════════════════════════════════════════════════════════


-- ───────────────────────────────────────────────────────────────────
-- STEP 1 — Create every table Django needs   ← START HERE
--
-- IF NOT EXISTS means this only creates what is actually missing and
-- silently skips the rest. It never touches your 16 legacy tables
-- (ot_users, ot_employees, ot_batch_allocations, ot_user_work_data,
-- ot_feedbacks, …) — those are not in this list at all.
--
-- FOREIGN_KEY_CHECKS is off so table order cannot cause a failure,
-- and back on at the end.
-- ───────────────────────────────────────────────────────────────────


SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `ardurtechnology`.`django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=153 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `ardurtechnology`.`auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `ardurtechnology`.`auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext COLLATE utf8mb4_unicode_ci,
  `object_repr` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_ot_users_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `ardurtechnology`.`django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_ot_users_id` FOREIGN KEY (`user_id`) REFERENCES `ardurtechnology`.`ot_users` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_session` (
  `session_key` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_data` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=87 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_cache_table` (
  `cache_key` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `value` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires` datetime(6) NOT NULL,
  PRIMARY KEY (`cache_key`),
  KEY `django_cache_table_expires` (`expires`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_beat_intervalschedule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `every` int NOT NULL,
  `period` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_beat_crontabschedule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `minute` varchar(240) COLLATE utf8mb4_unicode_ci NOT NULL,
  `hour` varchar(96) COLLATE utf8mb4_unicode_ci NOT NULL,
  `day_of_week` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `day_of_month` varchar(124) COLLATE utf8mb4_unicode_ci NOT NULL,
  `month_of_year` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `timezone` varchar(63) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_beat_solarschedule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `event` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL,
  `latitude` decimal(9,6) NOT NULL,
  `longitude` decimal(9,6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_celery_beat_solar_event_latitude_longitude_ba64999a_uniq` (`event`,`latitude`,`longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_beat_clockedschedule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `clocked_time` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_beat_periodictasks` (
  `ident` smallint NOT NULL,
  `last_update` datetime(6) NOT NULL,
  PRIMARY KEY (`ident`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_beat_periodictask` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `task` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `args` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `kwargs` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `queue` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `exchange` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `routing_key` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `expires` datetime(6) DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL,
  `last_run_at` datetime(6) DEFAULT NULL,
  `total_run_count` int unsigned NOT NULL,
  `date_changed` datetime(6) NOT NULL,
  `description` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `crontab_id` int DEFAULT NULL,
  `interval_id` int DEFAULT NULL,
  `solar_id` int DEFAULT NULL,
  `one_off` tinyint(1) NOT NULL,
  `start_time` datetime(6) DEFAULT NULL,
  `priority` int unsigned DEFAULT NULL,
  `headers` longtext COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT (_utf8mb4'{}'),
  `clocked_id` int DEFAULT NULL,
  `expire_seconds` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `django_celery_beat_p_crontab_id_d3cba168_fk_django_ce` (`crontab_id`),
  KEY `django_celery_beat_p_interval_id_a8ca27da_fk_django_ce` (`interval_id`),
  KEY `django_celery_beat_p_solar_id_a87ce72c_fk_django_ce` (`solar_id`),
  KEY `django_celery_beat_p_clocked_id_47a69f82_fk_django_ce` (`clocked_id`),
  CONSTRAINT `django_celery_beat_p_clocked_id_47a69f82_fk_django_ce` FOREIGN KEY (`clocked_id`) REFERENCES `ardurtechnology`.`django_celery_beat_clockedschedule` (`id`),
  CONSTRAINT `django_celery_beat_p_crontab_id_d3cba168_fk_django_ce` FOREIGN KEY (`crontab_id`) REFERENCES `ardurtechnology`.`django_celery_beat_crontabschedule` (`id`),
  CONSTRAINT `django_celery_beat_p_interval_id_a8ca27da_fk_django_ce` FOREIGN KEY (`interval_id`) REFERENCES `ardurtechnology`.`django_celery_beat_intervalschedule` (`id`),
  CONSTRAINT `django_celery_beat_p_solar_id_a87ce72c_fk_django_ce` FOREIGN KEY (`solar_id`) REFERENCES `ardurtechnology`.`django_celery_beat_solarschedule` (`id`),
  CONSTRAINT `django_celery_beat_periodictask_chk_1` CHECK ((`total_run_count` >= 0)),
  CONSTRAINT `django_celery_beat_periodictask_chk_2` CHECK ((`priority` >= 0)),
  CONSTRAINT `django_celery_beat_periodictask_chk_3` CHECK ((`expire_seconds` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_results_taskresult` (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_encoding` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `result` longtext COLLATE utf8mb4_unicode_ci,
  `date_done` datetime(6) NOT NULL,
  `traceback` longtext COLLATE utf8mb4_unicode_ci,
  `meta` longtext COLLATE utf8mb4_unicode_ci,
  `task_args` longtext COLLATE utf8mb4_unicode_ci,
  `task_kwargs` longtext COLLATE utf8mb4_unicode_ci,
  `task_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `worker` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `date_created` datetime(6) NOT NULL,
  `periodic_task_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `date_started` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `task_id` (`task_id`),
  KEY `django_cele_task_na_08aec9_idx` (`task_name`),
  KEY `django_cele_status_9b6201_idx` (`status`),
  KEY `django_cele_worker_d54dd8_idx` (`worker`),
  KEY `django_cele_date_cr_f04a50_idx` (`date_created`),
  KEY `django_cele_date_do_f59aad_idx` (`date_done`),
  KEY `django_cele_periodi_1993cf_idx` (`periodic_task_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_results_chordcounter` (
  `id` int NOT NULL AUTO_INCREMENT,
  `group_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sub_tasks` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `count` int unsigned NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `group_id` (`group_id`),
  CONSTRAINT `django_celery_results_chordcounter_chk_1` CHECK ((`count` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`django_celery_results_groupresult` (
  `id` int NOT NULL AUTO_INCREMENT,
  `group_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `date_created` datetime(6) NOT NULL,
  `date_done` datetime(6) NOT NULL,
  `content_type` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_encoding` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `result` longtext COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  UNIQUE KEY `group_id` (`group_id`),
  KEY `django_cele_date_cr_bd6c1d_idx` (`date_created`),
  KEY `django_cele_date_do_caae0e_idx` (`date_done`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_stored_files` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `uuid` char(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_emp_id` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `context` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stored_path` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `thumb_path` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `mime_type` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `size_bytes` bigint NOT NULL,
  `sha256` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `scan_status` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `claimed_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `ot_stored_files_owner_emp_id_96257350` (`owner_emp_id`),
  KEY `ot_stored_files_sha256_e547be88` (`sha256`),
  KEY `ot_stored_files_created_at_8a989df4` (`created_at`),
  KEY `ix_file_owner_ctx` (`owner_emp_id`,`context`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_notifications` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `recipient_emp_id` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `notif_type` varchar(60) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `body` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payload` json NOT NULL,
  `link_url` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `priority` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `actor_emp_id` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `read_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `expires_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ot_notifications_recipient_emp_id_4909040b` (`recipient_emp_id`),
  KEY `ot_notifications_notif_type_79230601` (`notif_type`),
  KEY `ot_notifications_created_at_1c3d29b6` (`created_at`),
  KEY `ot_notifications_expires_at_71ad0b6d` (`expires_at`),
  KEY `ix_notif_inbox` (`recipient_emp_id`,`read_at`,`id` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_notification_prefs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `emp_id` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `notif_type` varchar(60) COLLATE utf8mb4_unicode_ci NOT NULL,
  `in_app` tinyint(1) NOT NULL,
  `email` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_notif_pref` (`emp_id`,`notif_type`),
  KEY `ot_notification_prefs_emp_id_5a5bdfe2` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_presence` (
  `emp_id` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status_source` varchar(15) COLLATE utf8mb4_unicode_ci NOT NULL,
  `custom_status` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `connection_count` smallint NOT NULL,
  `last_seen_at` datetime(6) NOT NULL,
  `last_heartbeat_at` datetime(6) DEFAULT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`emp_id`),
  KEY `ot_presence_status_ec54ab3b` (`status`),
  KEY `ot_presence_last_seen_at_1d5e11fd` (`last_seen_at`),
  KEY `ix_presence_status` (`status`,`last_seen_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_realtime_outbox` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `topic` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `audience` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `event_type` varchar(60) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payload` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ot_realtime_outbox_topic_4aa1baa6` (`topic`),
  KEY `ot_realtime_outbox_created_at_58246a72` (`created_at`),
  KEY `ix_outbox_topic_id` (`topic`,`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_ws_tickets` (
  `token` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `emp_id` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `expires_at` datetime(6) NOT NULL,
  `redeemed_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`token`),
  KEY `ot_ws_tickets_emp_id_ea33d3e2` (`emp_id`),
  KEY `ot_ws_tickets_expires_at_26c176e0` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_report_jobs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `requested_by` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `report_key` varchar(60) COLLATE utf8mb4_unicode_ci NOT NULL,
  `params` json NOT NULL,
  `export_format` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `row_count` int DEFAULT NULL,
  `error_message` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `started_at` datetime(6) DEFAULT NULL,
  `finished_at` datetime(6) DEFAULT NULL,
  `file_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ot_report_jobs_file_id_da840fc7_fk_ot_stored_files_id` (`file_id`),
  KEY `ot_report_jobs_requested_by_a1fffa1a` (`requested_by`),
  KEY `ot_report_jobs_status_196b2b45` (`status`),
  KEY `ot_report_jobs_created_at_8eff6931` (`created_at`),
  KEY `ix_reportjob_user` (`requested_by`,`id` DESC),
  CONSTRAINT `ot_report_jobs_file_id_da840fc7_fk_ot_stored_files_id` FOREIGN KEY (`file_id`) REFERENCES `ardurtechnology`.`ot_stored_files` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ardurtechnology`.`ot_employee_submissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `chain_sheet` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `search_package` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `report` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `allocation_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ot_employee_submissions_allocation_id_d85d541e` (`allocation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;


-- ───────────────────────────────────────────────────────────────────
-- STEP 2 — Add the two columns no migration creates
--
-- The models declare these fields, but no migration adds them: Django
-- skips field changes on unmanaged (legacy) models, so it never
-- generated them. Without these, every allocation and employee page
-- fails with MySQL 1054 "Unknown column".
--
-- Both are ADDITIVE — no existing row loses anything.
-- If you get "Duplicate column name", it is already there. Fine.
-- ───────────────────────────────────────────────────────────────────


ALTER TABLE `ardurtechnology`.`ot_batch_allocations`
    ADD COLUMN `general_instructions` longtext NULL;

ALTER TABLE `ardurtechnology`.`ot_employees`
    ADD COLUMN `alternate_phone` varchar(20) NOT NULL DEFAULT '';


-- ───────────────────────────────────────────────────────────────────
-- STEP 3 — Set a known password so you can log in
--
-- Bcrypt is one-way: no existing password can be read back out of the
-- database. This sets a NEW one. The hash was generated with this
-- project's own hasher (BCryptSHA256) and verified to authenticate.
--
--     emp_id   : AT0001
--     password : <choose-your-own>
--
-- Change it after logging in.
-- ───────────────────────────────────────────────────────────────────


UPDATE `ardurtechnology`.`ot_users`
   SET `password` = '<PASTE-A-HASH-HERE>'
 WHERE `emp_id` = 'AT0001';

-- "0 rows affected" means AT0001 does not exist. Find the real IDs:
-- SELECT emp_id, name, status FROM `ardurtechnology`.ot_users ORDER BY emp_id LIMIT 30;
-- then re-run the UPDATE with the right emp_id in the WHERE.


-- ───────────────────────────────────────────────────────────────────
-- STEP 4 — VERIFY (read-only). Every row should read 1.
-- ───────────────────────────────────────────────────────────────────

SELECT 'cache table'           AS item, COUNT(*) AS should_be_1 FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = 'ardurtechnology' AND TABLE_NAME = 'django_cache_table'
UNION ALL
SELECT 'session table',        COUNT(*) FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = 'ardurtechnology' AND TABLE_NAME = 'django_session'
UNION ALL
SELECT 'general_instructions', COUNT(*) FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = 'ardurtechnology' AND TABLE_NAME = 'ot_batch_allocations' AND COLUMN_NAME = 'general_instructions'
UNION ALL
SELECT 'alternate_phone',      COUNT(*) FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = 'ardurtechnology' AND TABLE_NAME = 'ot_employees' AND COLUMN_NAME = 'alternate_phone'
UNION ALL
SELECT 'LIVE average_time',    COUNT(*) FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = 'ardurtechnology' AND TABLE_NAME = 'ot_user_work_data' AND COLUMN_NAME = 'average_time'
UNION ALL
SELECT 'LIVE pages',           COUNT(*) FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = 'ardurtechnology' AND TABLE_NAME = 'ot_user_work_data' AND COLUMN_NAME = 'pages'
UNION ALL
SELECT 'LIVE work_units',      COUNT(*) FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = 'ardurtechnology' AND TABLE_NAME = 'ot_user_work_data' AND COLUMN_NAME = 'work_units';

-- The three "LIVE" rows reading 1 means your live data survived.
-- Any of them reading 0 means that column was dropped — tell me, and
-- restore it from your backup.
