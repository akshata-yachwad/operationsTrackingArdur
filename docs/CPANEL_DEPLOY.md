# Deploying OpsTracking to GoDaddy cPanel

Target: `opstracking.ardurtechnology.com` (+ `www.`), cPanel 134 on CloudLinux,
account `n20m30upmqr6`, MySQL `ardurtechnology` @ `68.178.227.55`.

This is a **cutover**, not an update. The subdomain currently serves the legacy
Flask app (`app.py`, `database.py`, `passenger_wsgi.py`). This repo is a Django
rewrite that takes over the *same* MySQL database.

---

## What shared hosting costs you

Passenger is WSGI-only and there is no Redis and no long-running process, so
three things do not survive the move. `opstracking/settings/cpanel.py` swaps in
in-process replacements:

| Capability | Normally | On cPanel | Effect |
|---|---|---|---|
| WebSockets | Daphne / ASGI | **none** | realtime is off; UI must poll |
| Channel layer | `channels_redis` | InMemory | `group_send` no-ops across processes |
| Cache | Redis | database table | slower, but shared across workers |
| Celery | worker + beat | **eager** | tasks run *inside* the web request |
| Scheduled jobs | celery beat | **none** | use cPanel → Cron Jobs |

The one to plan around: a heavy report export now blocks the HTTP request that
triggered it, and Passenger will kill it at the timeout. If exports matter,
move them to a cron job or move the app to a VPS.

---

## Phase 0 — Backups. Do not skip.

Everything below is reversible only if this phase happened.

1. **Database.** cPanel → *phpMyAdmin* → select `ardurtechnology` → *Export* →
   Custom → check **Structure and data** → Go. Keep the `.sql` file off-server.
   Larger DBs: cPanel → *Backup* → *Download a MySQL Database Backup*.
2. **The Flask app.** File Manager → select the subdomain folder → *Compress* →
   `flask-backup-YYYYMMDD.zip`. This is your rollback.
3. **Verify the dump is real** — open it and confirm you see
   `CREATE TABLE` and `INSERT INTO` lines. A 0-byte export is not a backup.

---

## Phase 1 — Send me the schema before any migration runs

The migrations in this repo were generated against a *development* database, so
they carry `'managed': True` and will happily issue DDL against your live
tables. Several would destroy or alter production data (details in Phase 4).
Deciding apply-vs-fake per migration requires the real schema.

In phpMyAdmin → *Export* → Custom → **Structure only** → Go. That file contains
no rows, only `CREATE TABLE` statements. Send it over and you get back an exact
per-migration decision list.

For comparison, `docs/schema_target_mysql.sql` is the **target** schema — all
41 tables as Django builds them, captured by applying every migration to a
clean MySQL 8. Diff your production structure against it to see the real gap.

---

## Phase 2 — Upload to a NEW folder, not over the Flask app

Deploy beside the live app, not on top of it. Dropping files over the running
app overwrites `passenger_wsgi.py` mid-request and takes the site down with no
clean way back.

Create `/home/n20m30upmqr6/opstracking_django/` and upload there.

Zip locally first — File Manager's *Upload* handles one archive far better than
a few thousand loose files:

```bash
# on your Mac, from the repo root
zip -r opstracking.zip . \
  -x '*.git/*' '.venv/*' '*__pycache__/*' '*.pyc' \
     '.env' '.pytest_cache/*' '.ruff_cache/*' '.coverage' 'logs/*' 'storage/*'
```

Upload `opstracking.zip`, then *Extract* in File Manager.

**Never upload `.env`.** Upload `.env.cpanel` separately, rename it to `.env`,
then File Manager → *Permissions* → `0600`.

---

## Phase 3 — Setup Python App

cPanel → *Setup Python App* → **Create Application**:

| Field | Value |
|---|---|
| Python version | **3.11.15** (already configured; Django 5.2 supports 3.10–3.13) |
| Application root | `subdomain/opstracking.ardurtechnology.com` |
| Application URL | `opstracking.ardurtechnology.com` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

Copy the **"Enter to the virtual environment"** command it shows you. Every
command below must run inside that environment, from
cPanel → *Terminal* (or SSH):

```bash
source /home/n20m30upmqr6/virtualenv/opstracking_django/3.12/bin/activate
cd /home/n20m30upmqr6/opstracking_django

pip install --upgrade pip
pip install -r requirements-cpanel.txt
```

Use `requirements-cpanel.txt`, **not** `requirements.txt` — the latter pulls
`psycopg` and `gunicorn` you don't need, and omits the MySQL driver you do.

Confirm Django can read its settings before going further:

```bash
python manage.py check --deploy
```

Then confirm the database actually answers:

```bash
python manage.py dbshell -c "SELECT COUNT(*) FROM ot_users;"
```

An `access denied` here means the MySQL grant is on a different host — try the
`127.0.0.1` variant commented in `.env`.

---

## Phase 4 — Migrations

**Read this section fully before running anything.**

`manage.py migrate` on its own would damage production. Three groups:

### 4a. Tables that already exist → adopt, never create

`ot_users`, `ot_employees`, `ot_user_login_history`, `ot_batch_allocations`,
`ot_orders_history`, `ot_order_rates`, `aps_Break_Times`, `ot_feedbacks`,
`ot_feedback_images`, `ot_worktypes`, `ot_projects`, `ot_clientcode`,
`ot_shift_master`, `ot_app_settings`, `ot_user_work_data`, `ot_targets`.

`--fake-initial` detects each table already exists and records the migration as
applied without running the `CREATE TABLE`:

```bash
python manage.py migrate --fake-initial
```

Stop if this errors. Do not add `--fake` to force past it.

### 4b. Tables that are genuinely new → let Django create them

`ot_stored_files`, `ot_notifications`, `ot_notification_prefs`, `ot_presence`,
`ot_realtime_outbox`, `ot_ws_tickets`, `ot_report_jobs`,
`ot_employee_submissions`, plus Django's own `django_session`,
`django_migrations`, `auth_*`, and the celery-results tables.

The same `--fake-initial` run creates these normally, because their tables do
not exist yet. Nothing extra to do.

### 4c. Migrations that ALTER live tables → decide one by one

These carry real DDL against tables holding production rows:

| Migration | Operations | Live table | Risk |
|---|---|---|---|
| `tracking/0005_remove_worksession_average_time_and_more` | `RemoveField` ×3 | `ot_user_work_data` | **DROP COLUMN — permanent data loss** |
| `feedback/0002_feedback_acknowledgment_and_more` | `AddField` ×18, `AlterField` ×12 | `ot_feedbacks` | `MODIFY COLUMN` can truncate |
| `allocations/0003_…` | `AddField` ×12 | `ot_batch_allocations` | new columns |
| `allocations/0008_batchallocation_chain_sheet_and_more` | `AddField` ×9, `AlterField` ×1 | `ot_batch_allocations` | `MODIFY COLUMN` |
| `accounts/0002_employee_active_inactive_date_…` | `AddField` ×3, `AlterField` ×4 | `ot_users`, `ot_employees` | `MODIFY COLUMN` |
| `masters/0002_clientcode_cc_id_…` | `AddField` ×6 | masters tables | new columns |
| `masters/0006_alter_shift_end_time_…` | `AlterField` ×3 | `ot_shift_master` | `MODIFY COLUMN` |

**`tracking/0005` must be faked.** It drops `average_time`, `pages` and
`work_units` from your live work-data table. Faking marks it applied while the
columns and their data stay in MySQL — Django simply stops referencing them:

```bash
python manage.py migrate tracking 0005 --fake
```

For every other row, inspect the generated SQL first, then choose:

```bash
python manage.py sqlmigrate feedback 0002      # read it, do not pipe to mysql
```

- Column **missing** in production → apply the migration normally.
- Column **already present** → `--fake` that migration.
- `AlterField` narrowing a type (e.g. `varchar(255)` → `varchar(50)`) → **stop**
  and widen the model instead; MySQL will silently truncate under a permissive
  `sql_mode`, and this app sets `STRICT_TRANS_TABLES` so it errors instead.

Confirm the end state — every migration listed `[X]`:

```bash
python manage.py showmigrations
```

### 4d. Two columns no migration creates — you must add these by hand

`scripts/check_schema_drift.py` caught a genuine gap in the repo. These fields
exist on the models but **no migration anywhere adds them**:

| Model field | Table | Column |
|---|---|---|
| `apps/allocations/models.py:97` `general_instructions` | `ot_batch_allocations` | `longtext NULL` |
| `apps/accounts/models.py:140` `alternate_phone` | `ot_employees` | `varchar(20) NOT NULL DEFAULT ''` |

`makemigrations` does not report them because both models are `managed=False`
in production and Django skips field changes on unmanaged models. Migrating
without this step leaves the app raising MySQL 1054 *Unknown column* on every
page that touches an allocation or an employee.

Both statements are additive — nothing is dropped or altered:

```bash
mysql -u ardurdev -p ardurtechnology < docs/schema_fix_missing_columns.sql
```

Then confirm the database and the models agree:

```bash
python scripts/check_schema_drift.py     # exits 0 when clean
```

Run this before *and* after Phase 4c. `EXTRA IN DB` is expected and safe — it
is what a faked `RemoveField` leaves behind, and it is how the live data in
`average_time`, `pages` and `work_units` survives.

### 4e. Passwords

The Flask app stored bare bcrypt hashes; Django needs a `bcrypt$` prefix or
**every existing user is locked out**:

```bash
python manage.py shell < scripts/migrate_password_hashes.py
```

Verify one account can log in before the cutover.

---

## Phase 5 — Cache table and static files

```bash
python manage.py createcachetable          # settings/cpanel.py uses a DB cache
python manage.py collectstatic --noinput
```

`collectstatic` writes to `STATIC_ROOT` from `.env`. WhiteNoise serves those,
so no Apache alias is needed.

Create the private upload directory **outside** the web root, or uploaded files
become downloadable by anyone guessing a URL:

```bash
mkdir -p /home/n20m30upmqr6/opstracking_storage
chmod 750 /home/n20m30upmqr6/opstracking_storage
mkdir -p /home/n20m30upmqr6/logs
```

---

## Phase 6 — Cutover

1. Setup Python App → edit the app → set **Application URL** to
   `opstracking.ardurtechnology.com` → **Restart**.
2. Test `https://opstracking.ardurtechnology.com/login`.
3. Broken? Set Application URL back to the Flask folder and restart. That is
   your rollback, and it takes about thirty seconds.

Passenger caches aggressively. After any file change:

```bash
mkdir -p tmp && touch tmp/restart.txt
```

Logs, when something 500s: `/home/n20m30upmqr6/logs/opstracking-django.log`,
plus cPanel → *Errors*.

---

## Phase 7 — Fix TLS. It is currently broken.

The certificate for `opstracking.ardurtechnology.com` **expired 2025-12-23**
(Let's Encrypt R13). Browsers show a full-page warning today.

cPanel → *SSL/TLS Status* → tick both the bare and `www.` host → **Run AutoSSL**.

Only once that shows valid and the site loads clean, flip these in `.env` and
restart:

```ini
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Leave `SECURE_HSTS_SECONDS=0` for at least a week after that. HSTS instructs
browsers to refuse plain HTTP for a year, it is cached client-side, and **it
cannot be undone from the server** — turning it on over a flaky certificate
locks your users out with no remedy.

---

## After go-live

- **`www.` must resolve.** Add a CNAME `www.opstracking` → `opstracking` in
  cPanel → *Zone Editor*, otherwise the `ALLOWED_HOSTS` entry is decorative.
- **Rotate the DB password.** It was shared in plaintext in chat.
- **Retire the Flask app** only after a few days of clean Django operation —
  two apps writing the same tables will produce inconsistent state.
- **Scheduled work** that Celery beat used to run needs cPanel → *Cron Jobs*.
