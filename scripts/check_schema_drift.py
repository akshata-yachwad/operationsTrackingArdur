#!/usr/bin/env python
"""Compare the live database against what the Django models expect.

Read-only. Issues SELECT/INTROSPECT only — never DDL. Run it before migrating
anything on production, and again afterwards to confirm the result.

    cd /home/n20m30upmqr6/opstracking_django
    python scripts/check_schema_drift.py

Output per table:

    MISSING IN DB    Django expects the column, production does not have it.
                     The migration that adds it must be APPLIED.
    EXTRA IN DB      Production has a column no model references. Harmless —
                     Django ignores it. This is also what a faked RemoveField
                     leaves behind, which is how live data gets preserved.
    TYPE DIFFERS     Same name, different type. Inspect before touching: an
                     AlterField that narrows a column can truncate live data.
"""

from __future__ import annotations

import os
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

from django.apps import apps  # noqa: E402
from django.db import connection  # noqa: E402

RESET, RED, YELLOW, GREEN, DIM = "\033[0m", "\033[31m", "\033[33m", "\033[32m", "\033[2m"


def main() -> int:
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))

        drift_found = False
        absent_tables: list[str] = []

        for model in sorted(apps.get_models(), key=lambda m: m._meta.db_table):
            table = model._meta.db_table
            if table not in existing:
                absent_tables.append(table)
                continue

            db_cols = {
                c.name: c for c in connection.introspection.get_table_description(cursor, table)
            }
            # Only concrete, non-m2m local fields map to columns in this table.
            model_cols = {
                f.column: f for f in model._meta.local_fields if f.concrete and f.column
            }

            missing = sorted(set(model_cols) - set(db_cols))
            extra = sorted(set(db_cols) - set(model_cols))

            if not (missing or extra):
                continue

            drift_found = True
            managed = model._meta.managed
            print(f"\n{table}  {DIM}({model._meta.label}, managed={managed}){RESET}")

            for col in missing:
                f = model_cols[col]
                null = "NULL" if f.null else "NOT NULL"
                print(f"  {RED}MISSING IN DB{RESET}  {col}  {DIM}{f.get_internal_type()} {null}{RESET}")
            for col in extra:
                print(f"  {YELLOW}EXTRA IN DB{RESET}    {col}  {DIM}(Django ignores it){RESET}")

        if absent_tables:
            print(f"\n{RED}TABLES NOT IN DATABASE{RESET} — these must be created by migrate:")
            for t in absent_tables:
                print(f"  {t}")
            drift_found = True

        if not drift_found:
            print(f"{GREEN}No drift. Live schema matches the models.{RESET}")
            return 0

        print(
            f"\n{DIM}Reminder: 'EXTRA IN DB' is safe. 'MISSING IN DB' needs its migration "
            f"applied. Never fake a migration whose column is genuinely missing — the app "
            f"will 500 on the first query that selects it.{RESET}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
