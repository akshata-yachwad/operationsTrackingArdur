"""Master data models.

These four tables are read on nearly every page and written a few times a
week, which is why the service layer caches them and why the API is
read-for-everyone, write-for-admins.
"""

from __future__ import annotations

from django.db import models

from core.managers import ActiveManager
from core.models import legacy_managed
from core.timezone import now_ist


class MasterRecord(models.Model):
    """Shared shape: a name, an active flag, and audit stamps.

    Abstract, so each concrete table keeps its own legacy table name.
    """

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=now_ist)
    updated_at = models.DateTimeField(default=now_ist)
    created_by = models.CharField(max_length=20, blank=True, default="")

    objects = ActiveManager()

    class Meta:
        abstract = True


class WorkType(MasterRecord):
    id = models.AutoField(primary_key=True)
    wt_id = models.CharField(max_length=20, default="", blank=True)
    work_type = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")
    # Expected units per hour — the productivity reports compare against it.
    standard_rate = models.FloatField(null=True, blank=True)

    class Meta:
        managed = legacy_managed()
        db_table = "ot_worktypes"
        ordering = ["wt_id"]
        verbose_name = "work type"

    def __str__(self) -> str:
        return self.work_type


class Project(MasterRecord):
    id = models.AutoField(primary_key=True)
    project_id = models.CharField(max_length=20, default="", blank=True)
    project_name = models.CharField(max_length=150, unique=True)
    project_code = models.CharField(max_length=50, blank=True, default="", db_index=True)
    client_name = models.CharField(max_length=150, blank=True, default="")
    client_code = models.TextField(blank=True, default="")
    worktypes = models.TextField(blank=True, default="")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    requires_attendance = models.BooleanField(default=False)
    is_simplified_project = models.BooleanField(default=False)

    class Meta:
        managed = legacy_managed()
        db_table = "ot_projects"
        ordering = ["project_id"]

    def __str__(self) -> str:
        return self.project_name


class ClientCode(MasterRecord):
    id = models.AutoField(primary_key=True)
    cc_id = models.CharField(max_length=50, default="", blank=True)
    client_code = models.CharField(max_length=50, unique=True)
    client_name = models.CharField(max_length=150, blank=True, default="")
    project = models.CharField(max_length=150, blank=True, default="", db_index=True)
    worktypes = models.TextField(blank=True, default="")

    class Meta:
        managed = legacy_managed()
        db_table = "ot_clientcode"
        ordering = ["cc_id"]

    def __str__(self) -> str:
        return self.client_code


class Shift(MasterRecord):
    id = models.AutoField(primary_key=True)
    shift_name = models.CharField(max_length=50, unique=True, db_column='shift')
    start_time = models.TimeField(db_column='startedAt')
    end_time = models.TimeField(db_column='endedAt')
    # Total paid break minutes for this shift. The per-break allowances that
    # the app actually enforces live in apps/breaks/constants.py.
    break_minutes = models.IntegerField(default=0)

    class Meta:
        managed = legacy_managed()
        db_table = "ot_shift_master"
        ordering = ["start_time"]

    def __str__(self) -> str:
        return f"{self.shift_name} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"

    @property
    def is_overnight(self) -> bool:
        """A shift that ends before it starts crosses midnight.

        Every duration calculation over a shift has to know this, and getting
        it wrong makes the night shift's hours come out negative.
        """
        return self.end_time <= self.start_time
