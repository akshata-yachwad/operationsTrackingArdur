"""Align migration state with the real production schema.

SeparateDatabaseAndState with NO database_operations: this migration issues
zero SQL. It only corrects Django's idea of the schema.

0001_initial describes a schema production never had. Without this, the next
makemigrations compares the models against that fiction and emits RemoveField
for columns that DO exist and hold live data -- average_time, pages and
work_units on ot_user_work_data alone cover 166,132 rows.

Generated 2026-08-23 by comparing the models against the live database.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='worksession',
                    name='work_units',
                ),
                migrations.RemoveField(
                    model_name='worksession',
                    name='average_time',
                ),
                migrations.RemoveField(
                    model_name='worksession',
                    name='pages',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='emp_id',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='project',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='work_type',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='target_date',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='target_units',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='achieved_units',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='created_by',
                ),
                migrations.RemoveField(
                    model_name='target',
                    name='created_at',
                ),
                migrations.CreateModel(
                    name='EmployeeSubmission',
                    fields=[
                        ('allocation', models.ForeignKey(db_column='allocation_id', db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='allocations.batchallocation', to_field='allocation_id')),
                        ('chain_sheet', models.FileField(blank=True, null=True, upload_to='submissions/chain_sheets/')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('report', models.FileField(blank=True, null=True, upload_to='submissions/reports/')),
                        ('search_package', models.FileField(blank=True, null=True, upload_to='submissions/search_packages/')),
                    ],
                    options={
                        'db_table': 'ot_employee_submissions',
                        'managed': True,
                    },
                ),
            ],
        ),
    ]
