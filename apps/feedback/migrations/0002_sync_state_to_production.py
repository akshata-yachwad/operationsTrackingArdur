"""Align migration state with the real production schema.

SeparateDatabaseAndState with NO database_operations: this migration issues
zero SQL. It only corrects Django's idea of the schema.

0001_initial describes a schema production never had. Without this, the next
makemigrations compares the models against that fiction and emits RemoveField
for columns that DO exist and hold live data -- average_time, pages and
work_units on ot_user_work_data alone cover 166,132 rows.

Generated 2026-08-23 by comparing the models against the live database.
"""

import core.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feedback', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='feedback',
                    name='feedback_type',
                ),
                migrations.RemoveField(
                    model_name='feedback',
                    name='subject',
                ),
                migrations.RemoveField(
                    model_name='feedback',
                    name='description',
                ),
                migrations.RemoveField(
                    model_name='feedback',
                    name='error_count',
                ),
                migrations.RemoveField(
                    model_name='feedback',
                    name='sample_size',
                ),
                migrations.RemoveField(
                    model_name='feedback',
                    name='created_by_name',
                ),
                migrations.RemoveField(
                    model_name='feedback',
                    name='acknowledged_at',
                ),
                migrations.RemoveField(
                    model_name='feedback',
                    name='response',
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='acknowledgment',
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='acknowledgment_comment',
                    field=models.TextField(blank=True, default='', null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='acknowledgment_date',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='action_taken',
                    field=models.TextField(blank=True, default='', null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='client_code',
                    field=models.CharField(blank=True, default='', max_length=150),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='closure_date',
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='comments',
                    field=models.TextField(blank=True, default='', null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='feedback',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='feedback_provided_by',
                    field=models.CharField(blank=True, default='', max_length=100),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='feedback_received_date',
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='feedback_received_mode',
                    field=models.CharField(blank=True, default='email', max_length=50),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='feedback_recorded',
                    field=models.CharField(blank=True, default='internalAudit', max_length=50),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='open_date',
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='processed_date',
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='status',
                    field=models.CharField(blank=True, default='open', max_length=20),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='type',
                    field=models.CharField(blank=True, default='', max_length=100),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='updated_at',
                    field=models.DateTimeField(blank=True, default=core.timezone.now_ist, null=True),
                ),
                migrations.AddField(
                    model_name='feedback',
                    name='updated_by',
                    field=models.CharField(blank=True, default='', max_length=50, null=True),
                ),
                migrations.RemoveField(
                    model_name='feedbackimage',
                    name='caption',
                ),
                migrations.RemoveField(
                    model_name='feedbackimage',
                    name='file',
                ),
            ],
        ),
    ]
