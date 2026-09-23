# Hand-written migration.
#
# The `is_paused` column already exists in ot_attendance (added outside Django)
# but was defined WITHOUT a DEFAULT value.  Django's AddField would fail with
# (1060, "Duplicate column name 'is_paused'"), so we:
#   1. Use SeparateDatabaseAndState so Django's state layer knows the field
#      exists without trying to ALTER TABLE to add it.
#   2. Use RunSQL to ALTER the existing column in-place, setting DEFAULT 0 so
#      MySQL (in STRICT mode) no longer rejects INSERTs that don't name the
#      column explicitly.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0008_softwareshift_accumulated_seconds_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Register the field in Django's migration state (no DDL).
            state_operations=[
                migrations.AddField(
                    model_name='attendance',
                    name='is_paused',
                    field=models.BooleanField(default=False),
                ),
            ],
            # ALTER the pre-existing column so it has a DB-level DEFAULT.
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE ot_attendance "
                        "MODIFY COLUMN is_paused TINYINT(1) NOT NULL DEFAULT 0;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE ot_attendance "
                        "MODIFY COLUMN is_paused TINYINT(1) NOT NULL;"
                    ),
                ),
            ],
        ),
    ]
