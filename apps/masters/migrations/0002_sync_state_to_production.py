"""Align migration state with the real production schema.

SeparateDatabaseAndState with NO database_operations: this migration issues
zero SQL. It only corrects Django's idea of the schema.

0001_initial describes a schema production never had. Without this, the next
makemigrations compares the models against that fiction and emits RemoveField
for columns that DO exist and hold live data -- average_time, pages and
work_units on ot_user_work_data alone cover 166,132 rows.

Generated 2026-08-23 by comparing the models against the live database.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('masters', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='worktype',
                    name='is_active',
                ),
                migrations.RemoveField(
                    model_name='worktype',
                    name='work_type',
                ),
                migrations.RemoveField(
                    model_name='worktype',
                    name='description',
                ),
                migrations.RemoveField(
                    model_name='worktype',
                    name='standard_rate',
                ),
                migrations.AddField(
                    model_name='worktype',
                    name='wt_id',
                    field=models.CharField(blank=True, default='', max_length=20),
                ),
                migrations.RemoveField(
                    model_name='project',
                    name='is_active',
                ),
                migrations.RemoveField(
                    model_name='project',
                    name='project_code',
                ),
                migrations.RemoveField(
                    model_name='project',
                    name='client_name',
                ),
                migrations.RemoveField(
                    model_name='project',
                    name='start_date',
                ),
                migrations.RemoveField(
                    model_name='project',
                    name='end_date',
                ),
                migrations.AddField(
                    model_name='project',
                    name='client_code',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.AddField(
                    model_name='project',
                    name='project_id',
                    field=models.CharField(blank=True, default='', max_length=20),
                ),
                migrations.AddField(
                    model_name='project',
                    name='worktypes',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.RemoveField(
                    model_name='clientcode',
                    name='is_active',
                ),
                migrations.RemoveField(
                    model_name='clientcode',
                    name='client_name',
                ),
                migrations.RemoveField(
                    model_name='clientcode',
                    name='project',
                ),
                migrations.AddField(
                    model_name='clientcode',
                    name='cc_id',
                    field=models.CharField(blank=True, default='', max_length=50),
                ),
                migrations.AddField(
                    model_name='clientcode',
                    name='worktypes',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='is_active',
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='created_at',
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='updated_at',
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='created_by',
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='shift_name',
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='start_time',
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='end_time',
                ),
                migrations.RemoveField(
                    model_name='shift',
                    name='break_minutes',
                ),
                migrations.AddField(
                    model_name='shift',
                    name='end_time',
                    field=models.TimeField(db_column='endedAt'),
                ),
                migrations.AddField(
                    model_name='shift',
                    name='shift_name',
                    field=models.CharField(db_column='shift', max_length=50, unique=True),
                ),
                migrations.AddField(
                    model_name='shift',
                    name='start_time',
                    field=models.TimeField(db_column='startedAt'),
                ),
            ],
        ),
    ]
