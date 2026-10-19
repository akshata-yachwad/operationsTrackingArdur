# The Django models do not match the production database

Found 2026-08-20 by connecting `scripts/check_schema_drift.py` to the live
MySQL (MariaDB 10.11) at `68.178.227.55`, database `ardurtechnology`.

## Summary

| | |
|---|---|
| Columns the models require that production does not have | **83** |
| Tables affected | **13** |
| Production columns no model references | **36** |
| Live rows at risk of being read as empty | ~420,000 |

This is not a missing-migration problem. The models were written against a
schema that production never had.

## The proof

`ot_worktypes` holds 58 rows. The work-type name lives in `worktypename`:

    {'id': 1, 'wt_id': 'WT-0001', 'worktypename': 'Master DE', ...}
    {'id': 2, 'wt_id': 'WT-0002', 'worktypename': 'Master Comp', ...}

`masters.WorkType` expects a column called `work_type`. That column does not
exist. Adding it with `ALTER TABLE` produces an **empty** column — the app
would render blank work types while the real values sit untouched in
`worktypename`.

`ot_batch_allocations` is worse than a rename. Production models title-search
orders — `property_address`, `owner_name`, `county`, `fees`, `margin`,
`vendor_rate`, `search_type`. The Django model expects a batch-allocation
workflow — `allocation_id`, `quantity`, `completed_quantity`, `priority`,
`qc_name`, `sla_notified`. These are different domain models, not different
spellings of the same one.

## Why "just add the columns" fails

1. **The data would not be there.** 83 new empty columns; the real values stay
   in the 36 columns nothing reads.
2. **It can break the Flask app.** Many are `NOT NULL`. The legacy app still
   INSERTs into these tables without supplying them.
3. **The app still would not work.** Reads return empty, writes go to columns
   no other system reads.

## What does work today

Verified against production, read-only:

- All 41 Django-owned tables exist (`django_cache_table`, `django_session`, …)
- `average_time`, `pages`, `work_units` are **intact** — 166,132 rows preserved
- `tracking/0005` is recorded as NOT applied, so the destructive step never ran
- The cache backend reads and writes correctly
- `general_instructions` and `alternate_phone` are present

The login 500 from the cache table is fixed. Login now fails one step later, on
`ot_users.last_login` — a column the model requires and production lacks.

## Also worth knowing

`django_migrations` shows apps **`trueAlign`** (7 migrations) and
**`django_cron`** (4) applied in this same database, alongside 175 tables
including `PA_DataAnalytics`, `aps_*`, `ind_*`, and `auth_user`. This database
is shared with at least one other application. Schema changes here affect more
than OpsTracking.

Only 1 migration per OpsTracking app is recorded, so `migrate` would still try
to apply 0002 onward — including `tracking/0005`, which drops the three live
columns. **Do not run `migrate` against this database.**

## The decision

Three options, in the order I would consider them:

1. **Point the models at the real columns.** Add `db_column=` to each field, or
   rename the model fields. No data moves, nothing breaks for Flask, and the
   app reads the values that actually exist. Largest code change; correct.

2. **Confirm this is even the right database.** The `ot_batch_allocations`
   mismatch is severe enough to ask whether the models were built against a
   different environment, or against a spec that was never implemented. Worth
   ten minutes before committing to option 1.

3. **Add the columns and backfill.** Only sane where a column is a true rename
   (`worktypename` → `work_type`). It is not viable for
   `ot_batch_allocations`, where no source column exists for most fields.

Whichever you pick, `scripts/check_schema_drift.py` reports progress: run it
until `MISSING IN DB` is empty. `EXTRA IN DB` is expected and harmless.

## Full column-by-column detail

### `aps_Break_Times` — 17,501 live rows

Model: `breaks.BreakTime`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `is_overrun` | **NO** | `created_at` |
| `overrun_notified` | **NO** | `duration` |
| `total_time` | **NO** | `reason_for_delay` |
| `user_name` | **NO** |  |

### `ot_batch_allocations` — 255 live rows

Model: `allocations.BatchAllocation`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `allocated_at` | **NO** | `batch_id` |
| `allocated_by` | **NO** | `created_at` |
| `allocation_id` | **NO** | `ground_state` |
| `ar_number` | **NO** | `order_details` |
| `batch` | **NO** | `sla_date` |
| `chain_sheet` | **NO** | `task_id` |
| `chain_sheet_name` | **NO** | `updated_at` |
| `completed_at` | **NO** | `updated_by` |
| `completed_quantity` | **NO** |  |
| `due_at` | **NO** |  |
| `employee_comments` | **NO** |  |
| `employee_name` | **NO** |  |
| `order_id` | **NO** |  |
| `priority` | **NO** |  |
| `qc_comments` | **NO** |  |
| `qc_id` | **NO** |  |
| `qc_name` | **NO** |  |
| `quantity` | **NO** |  |
| `report` | **NO** |  |
| `report_name` | **NO** |  |
| `search_package` | **NO** |  |
| `search_package_name` | **NO** |  |
| `sla_notified` | **NO** |  |
| `started_at` | **NO** |  |
| `time_taken` | **NO** |  |

### `ot_clientcode` — 59 live rows

Model: `masters.ClientCode`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `client_name` | **NO** | `updated_by` |
| `is_active` | **NO** |  |
| `project` | **NO** |  |

### `ot_employees` — 297 live rows

Model: `accounts.Employee`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `designation` | **NO** | `created_by` |
| `email` | **NO** | `updated_by` |
| `employee_type` | **NO** |  |
| `phone` | **NO** |  |
| `reporting_to` | **NO** |  |

### `ot_feedback_images` — 4,750 live rows

Model: `feedback.FeedbackImage`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `caption` | **NO** |  |
| `file_id` | **NO** |  |

### `ot_feedbacks` — 4,979 live rows

Model: `feedback.Feedback`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `acknowledged_at` | **NO** | `fields` |
| `created_by_name` | **NO** |  |
| `description` | **NO** |  |
| `error_count` | **NO** |  |
| `feedback_type` | **NO** |  |
| `response` | **NO** |  |
| `sample_size` | **NO** |  |
| `subject` | **NO** |  |

### `ot_orders_history` — 464 live rows

Model: `allocations.OrderHistory`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `action` | **NO** | `assigned_by` |
| `allocation_id` | **NO** | `assigned_on` |
| `created_at` | **NO** | `assigned_to` |
| `employee_id` | **NO** | `batch_id` |
| `from_status` | **NO** | `client_code` |
| `order_id` | **NO** | `project` |
| `performed_by` | **NO** | `seen` |
| `quantity` | **NO** | `seen_on` |
| `to_status` | **NO** | `task_id` |
|  |  | `work_type` |

### `ot_projects` — 7 live rows

Model: `masters.Project`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `client_name` | **NO** | `updated_by` |
| `end_date` | **NO** |  |
| `is_active` | **NO** |  |
| `project_code` | **NO** |  |
| `start_date` | **NO** |  |

### `ot_shift_master` — 4 live rows

Model: `masters.Shift`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `break_minutes` | **NO** |  |
| `created_at` | **NO** |  |
| `created_by` | **NO** |  |
| `is_active` | **NO** |  |
| `updated_at` | **NO** |  |

### `ot_targets` — 4 live rows

Model: `tracking.Target`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `achieved_units` | **NO** | `project_id` |
| `created_at` | **NO** | `project_name` |
| `created_by` | **NO** | `set_at` |
| `emp_id` | **NO** | `set_by` |
| `project` | **NO** | `target` |
| `target_date` | **NO** | `updated_by` |
| `target_units` | **NO** |  |
| `work_type` | **NO** |  |

### `ot_user_login_history` — 48,256 live rows

Model: `accounts.LoginHistory`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `ip_address` | **NO** |  |
| `name` | **NO** |  |
| `session_key` | **NO** |  |
| `user_agent` | **NO** |  |

### `ot_users` — 238 live rows

Model: `accounts.User`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `last_login` | **NO** | `login_time` |
|  |  | `logout_time` |

### `ot_worktypes` — 58 live rows

Model: `masters.WorkType`

| Django model expects | Present in DB? | Columns the DB actually has |
|---|---|---|
| `description` | **NO** | `updated_by` |
| `is_active` | **NO** | `worktypename` |
| `standard_rate` | **NO** |  |
| `work_type` | **NO** |  |