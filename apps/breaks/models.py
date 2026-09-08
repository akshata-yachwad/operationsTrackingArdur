"""Break records.

Maps onto the legacy ``aps_Break_Times`` table, whose column names differ from
the rest of the schema (``user_id`` rather than ``emp_id``). The mismatch is
preserved in the database and hidden behind properties, rather than renamed —
the Flask app may still be reading it during cutover.
"""

from __future__ import annotations

from django.db import models

from core.managers import OwnedQuerySet
from core.models import legacy_managed
from core.timezone import elapsed_seconds, now_ist


class BreakQuerySet(OwnedQuerySet):
    owner_field = "user_id"

    def visible_to(self, user):
        if user is None or not user.is_authenticated:
            return self.none()
        if user.is_super_admin:
            return self
        if user.is_project_admin or user.is_team_lead:
            projects = user.get_authorized_projects()
            if projects:
                from apps.accounts.models import Employee
                from django.db.models import Q
                q_objs = Q()
                for p in projects:
                    q_objs |= Q(project__icontains=p)
                team_emp_ids = Employee.objects.filter(q_objs).values_list('employee_id', flat=True)
                return self.filter(user_id__in=team_emp_ids)
            return self.filter(user_id=user.emp_id)
        return self.filter(user_id=user.emp_id)

    def open(self):
        return self.filter(end_time__isnull=True)

    def closed(self):
        return self.filter(end_time__isnull=False)

    def for_day(self, day=None):
        from core.timezone import day_bounds

        start, end = day_bounds(day)
        return self.filter(start_time__gte=start, start_time__lt=end)

    def overrunning(self, grace_seconds: int = 0):
        """Open breaks that have already exceeded their allowance.

        The comparison is done in the database so the beat task does not load
        every open break into Python every minute. Postgres and MySQL both
        support interval arithmetic on a duration expression, which is what
        Django emits for ``timedelta(seconds=1) * F("allotted_time")``.
        """
        from datetime import timedelta

        from django.db.models import DurationField, ExpressionWrapper, F

        deadline = ExpressionWrapper(
            F("start_time") + timedelta(seconds=1) * (F("allotted_time") + grace_seconds),
            output_field=DurationField(),
        )
        return self.open().annotate(deadline=deadline).filter(deadline__lt=now_ist())


class BreakTime(models.Model):
    """One break. Open while ``end_time`` is null."""

    id = models.AutoField(primary_key=True)
    # Legacy column name; `emp_id` below is the alias the rest of the app uses.
    user_id = models.CharField(max_length=20, db_index=True)
    user_name = models.CharField(max_length=100, blank=True, default="")
    break_type = models.CharField(max_length=50)

    start_time = models.DateTimeField(default=now_ist)
    end_time = models.DateTimeField(null=True, blank=True)
    total_time = models.FloatField(null=True, blank=True, help_text="Seconds taken")
    allotted_time = models.IntegerField(
        default=0, help_text="Seconds allowed — set by the server from BREAK_ALLOWANCES"
    )
    is_overrun = models.BooleanField(default=False)
    overrun_notified = models.BooleanField(default=False)

    objects = BreakQuerySet.as_manager()

    class Meta:
        managed = legacy_managed()
        db_table = "aps_Break_Times"
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["user_id", "end_time"], name="ix_break_user_open"),
            models.Index(fields=["start_time"], name="ix_break_start"),
        ]
        constraints = [
            # One open break per person, enforced by the database rather than
            # by hope. Two clicks 40ms apart cannot both insert.
            models.UniqueConstraint(
                fields=["user_id"],
                condition=models.Q(end_time__isnull=True),
                name="uq_one_open_break_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.break_type} · {self.start_time:%H:%M}"

    # ── aliases, so the rest of the app speaks one vocabulary ──

    @property
    def emp_id(self) -> str:
        return self.user_id

    @property
    def is_open(self) -> bool:
        return self.end_time is None

    @property
    def live_elapsed_seconds(self) -> float:
        if self.end_time:
            try:
                return float(self.total_time) if self.total_time is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        return elapsed_seconds(self.start_time)

    @property
    def remaining_seconds(self) -> float:
        """Negative once the allowance is spent — the UI shows it counting down
        and then counting up in red."""
        return (self.allotted_time or 0) - self.live_elapsed_seconds

    @property
    def overrun_seconds(self) -> float:
        return max(-self.remaining_seconds, 0.0)
