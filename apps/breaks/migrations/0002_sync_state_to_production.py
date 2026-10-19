"""Align migration state with the real production schema.

SeparateDatabaseAndState with NO database_operations: this migration issues
zero SQL. It only corrects Django's idea of the schema.

0001_initial describes a schema production never had. Without this, the next
makemigrations compares the models against that fiction and emits RemoveField
for columns that DO exist and hold live data -- average_time, pages and
work_units on ot_user_work_data alone cover 166,132 rows.

Generated 2026-08-23 by comparing the models against the live database.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('breaks', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='breaktime',
                    name='user_name',
                ),
                migrations.RemoveField(
                    model_name='breaktime',
                    name='total_time',
                ),
                migrations.RemoveField(
                    model_name='breaktime',
                    name='is_overrun',
                ),
                migrations.RemoveField(
                    model_name='breaktime',
                    name='overrun_notified',
                ),
            ],
        ),
    ]
