#!/usr/bin/env python
"""Finish the cPanel cutover in one command.

    python scripts/finish_setup.py
    python scripts/finish_setup.py --set-password AT0001
    python scripts/finish_setup.py --set-password AT0001 --password 'MyNewPass#1'

Safe by design. It will:

    * REPORT whether the three columns tracking/0005 drops still exist,
      so you learn immediately if live data was lost.
    * ADD the two columns the models need but no migration creates
      (additive only — nothing is dropped, narrowed, or renamed).
    * CREATE the cache table DRF's login throttle reads.
    * OPTIONALLY set one user's password.

It will NEVER run `migrate`, drop a column, or alter an existing column type.
Anything destructive is reported for a human to decide on.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import environ

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        environ.Env.read_env(str(env_file))
except ImportError:
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "opstracking.settings.cpanel")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402

OK, WARN, BAD, DIM, BOLD, RESET = (
    "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m",
)

# Columns tracking/0005 removes. Present == live data intact.
DROPPED_BY_0005 = ("average_time", "pages", "work_units")

# Columns the models require that no migration creates. Additive, safe.
MISSING_COLUMNS = [
    ("ot_batch_allocations", "general_instructions", "longtext NULL"),
    ("ot_employees", "alternate_phone", "varchar(20) NOT NULL DEFAULT ''"),
]


def header(text: str) -> None:
    print(f"\n{BOLD}{text}{RESET}\n" + "-" * len(text))


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        [table, column],
    )
    return cursor.fetchone()[0] > 0


def table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        [table],
    )
    return cursor.fetchone()[0] > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set-password", metavar="EMP_ID", help="reset this user's password")
    ap.add_argument("--password", help="the new password (generated if omitted)")
    args = ap.parse_args()

    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), VERSION()")
        dbname, version = cursor.fetchone()
        print(f"{OK}Connected{RESET}  db={dbname}  mysql={version}")

        # ── 1. did tracking/0005 destroy live data? ──────────────
        header("1. Live data check — columns tracking/0005 drops")
        survived, lost = [], []
        for col in DROPPED_BY_0005:
            (survived if column_exists(cursor, "ot_user_work_data", col) else lost).append(col)

        for col in survived:
            print(f"  {OK}INTACT{RESET}  ot_user_work_data.{col}")
        for col in lost:
            print(f"  {BAD}GONE{RESET}    ot_user_work_data.{col}")

        if lost:
            print(
                f"\n  {BAD}{len(lost)} column(s) were dropped — that migration ran.{RESET}\n"
                f"  {DIM}The column definitions and their data are only in your Phase 0\n"
                f"  backup now. Restore them from that dump; re-adding an empty column\n"
                f"  gets the schema back but not the values.{RESET}"
            )
        else:
            print(f"\n  {OK}All three intact — no data was lost.{RESET}")

        # ── 2. add the columns no migration creates ──────────────
        header("2. Columns the models need but no migration creates")
        for table, column, ddl in MISSING_COLUMNS:
            if not table_exists(cursor, table):
                print(f"  {WARN}SKIP{RESET}    {table} — table not found")
                continue
            if column_exists(cursor, table, column):
                print(f"  {OK}PRESENT{RESET} {table}.{column}")
                continue
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {ddl}")
            print(f"  {OK}ADDED{RESET}   {table}.{column}  {DIM}({ddl}){RESET}")

        # ── 3. cache table for the login throttle ────────────────
        header("3. Cache table (DRF login throttle reads it)")
        if table_exists(cursor, "django_cache_table"):
            print(f"  {OK}PRESENT{RESET} django_cache_table")
        else:
            call_command("createcachetable", verbosity=0)
            print(f"  {OK}CREATED{RESET} django_cache_table")

    # ── 4. password reset ────────────────────────────────────────
    if args.set_password:
        header(f"4. Password reset — {args.set_password}")
        from apps.accounts.models import User

        user = User.objects.filter(emp_id=args.set_password).first()
        if user is None:
            print(f"  {BAD}No user with emp_id={args.set_password!r}{RESET}")
            sample = list(User.objects.values_list("emp_id", "name")[:15])
            print(f"  {DIM}First users in ot_users: {sample}{RESET}")
        else:
            new_password = args.password or f"Ops{secrets.token_urlsafe(9)}!"
            user.set_password(new_password)
            user.save(update_fields=["password"])
            print(f"  {OK}Password set{RESET} for {user.emp_id} ({user.name or 'no name'})")
            print(f"\n  {BOLD}emp_id:   {user.emp_id}{RESET}")
            print(f"  {BOLD}password: {new_password}{RESET}")
            print(f"\n  {DIM}Change it after logging in. This is printed once.{RESET}")

    header("Done")
    print("Restart the app:  mkdir -p tmp && touch tmp/restart.txt")
    print("Then verify:      python scripts/check_schema_drift.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
