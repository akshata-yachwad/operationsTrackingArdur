# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_employee_options_alter_loginhistory_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='employee',
            options={'managed': True, 'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='employee',
            name='employee_type',
            field=models.CharField(choices=[('employee', 'Employee'), ('consultant', 'Consultant'), ('freelancer', 'Freelancer')], db_index=True, default='employee', max_length=50),
        ),
        migrations.AlterModelOptions(
            name='employee',
            options={'managed': False, 'ordering': ['name']},
        ),
    ]
