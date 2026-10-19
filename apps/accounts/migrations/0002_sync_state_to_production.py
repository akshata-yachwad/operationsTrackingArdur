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
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='employee',
                    name='email',
                ),
                migrations.RemoveField(
                    model_name='employee',
                    name='phone',
                ),
                migrations.RemoveField(
                    model_name='employee',
                    name='designation',
                ),
                migrations.RemoveField(
                    model_name='employee',
                    name='department',
                ),
                migrations.RemoveField(
                    model_name='employee',
                    name='project',
                ),
                migrations.RemoveField(
                    model_name='employee',
                    name='shift',
                ),
                migrations.RemoveField(
                    model_name='employee',
                    name='reporting_to',
                ),
                migrations.RemoveField(
                    model_name='employee',
                    name='date_of_joining',
                ),
                migrations.AddField(
                    model_name='employee',
                    name='active_inactive_date',
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='employee',
                    name='alternate_phone',
                    field=models.CharField(blank=True, default='', max_length=20),
                ),
                migrations.AddField(
                    model_name='employee',
                    name='client_code',
                    field=models.CharField(blank=True, default='', max_length=150),
                ),
                migrations.AddField(
                    model_name='employee',
                    name='date_of_joining',
                    field=models.DateField(blank=True, db_column='joining_date', null=True),
                ),
                migrations.AddField(
                    model_name='employee',
                    name='project',
                    field=models.CharField(blank=True, db_column='projects', default='', max_length=150),
                ),
                migrations.AddField(
                    model_name='employee',
                    name='shift',
                    field=models.CharField(blank=True, db_column='shift_time', default='', max_length=50),
                ),
                migrations.AddField(
                    model_name='employee',
                    name='department',
                    field=models.CharField(blank=True, db_column='work_location', default='', max_length=100),
                ),
                migrations.AddField(
                    model_name='employee',
                    name='work_type',
                    field=models.CharField(blank=True, default='', max_length=150),
                ),
                migrations.RemoveField(
                    model_name='loginhistory',
                    name='name',
                ),
                migrations.RemoveField(
                    model_name='loginhistory',
                    name='ip_address',
                ),
                migrations.RemoveField(
                    model_name='loginhistory',
                    name='user_agent',
                ),
                migrations.RemoveField(
                    model_name='loginhistory',
                    name='session_key',
                ),
            ],
        ),
    ]
