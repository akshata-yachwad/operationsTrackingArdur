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
        ('allocations', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='allocation_id',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='employee_name',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='batch',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='order_id',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='quantity',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='completed_quantity',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='priority',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='allocated_at',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='due_at',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='started_at',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='completed_at',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='allocated_by',
                ),
                migrations.RemoveField(
                    model_name='batchallocation',
                    name='sla_notified',
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='county',
                    field=models.CharField(blank=True, max_length=100, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='document_file',
                    field=models.FileField(blank=True, max_length=255, null=True, upload_to='order_docs/'),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='document_name',
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='eta',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='fees',
                    field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='general_instructions',
                    field=models.TextField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='margin',
                    field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='owner_name',
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='property_address',
                    field=models.CharField(blank=True, max_length=500, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='received_date',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='search_type',
                    field=models.CharField(blank=True, max_length=100, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='state',
                    field=models.CharField(blank=True, max_length=100, null=True),
                ),
                migrations.AddField(
                    model_name='batchallocation',
                    name='vendor_rate',
                    field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='allocation_id',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='order_id',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='employee_id',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='action',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='from_status',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='to_status',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='quantity',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='performed_by',
                ),
                migrations.RemoveField(
                    model_name='orderhistory',
                    name='created_at',
                ),
                migrations.CreateModel(
                    name='OrderRate',
                    fields=[
                        ('county', models.CharField(max_length=100)),
                        ('eta_rts', models.IntegerField(blank=True, null=True)),
                        ('eta_slt', models.IntegerField(blank=True, null=True)),
                        ('id', models.AutoField(primary_key=True, serialize=False)),
                        ('order_type', models.CharField(max_length=100)),
                        ('remark', models.CharField(blank=True, default='', max_length=250)),
                        ('state', models.CharField(max_length=100)),
                        ('stateabr', models.CharField(blank=True, default='', max_length=100)),
                        ('vendor_rts', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                        ('vendor_slt', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                    ],
                    options={
                        'db_table': 'ot_order_rates',
                        'managed': True,
                    },
                ),
            ],
        ),
    ]
