"""Reusable QuerySet and Manager classes.

A query that appears in two services belongs here instead — that is the
difference between a manager and a pile of copy-pasted ``.filter()`` chains.
"""

from __future__ import annotations

from django.db import models

from core.timezone import day_bounds, now_ist


class SoftDeleteQuerySet(models.QuerySet):  # pragma: no cover — no concrete model uses this yet
    """For models with a nullable ``deleted_at``."""

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def soft_delete(self):
        return self.update(deleted_at=now_ist())


class SoftDeleteManager(  # pragma: no cover — no concrete model uses this yet
    models.Manager.from_queryset(SoftDeleteQuerySet)
):
    """Default manager that hides soft-deleted rows.

    Keep a second, unfiltered manager on the model (conventionally
    ``all_objects``) — the admin and any repair script need to see everything.
    """

    def get_queryset(self):
        return super().get_queryset().alive()


class ActiveQuerySet(models.QuerySet):
    """For master data with an ``is_active`` / ``status`` column."""

    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)


class ActiveManager(models.Manager.from_queryset(ActiveQuerySet)):
    pass


class OwnedQuerySet(models.QuerySet):
    """For anything keyed by ``emp_id``.

    ``visible_to`` is the row-level security boundary: a supervisor sees
    everything, an employee sees only their own rows. Every list endpoint that
    returns per-employee data must go through it — an object-level permission
    class alone does not protect a list.
    """

    owner_field = "emp_id"

    def for_employee(self, emp_id: str):
        return self.filter(**{self.owner_field: emp_id})

    def visible_to(self, user):
        if user is None or not user.is_authenticated:
            return self.none()
        if user.is_super_admin:
            return self
        if user.is_project_admin or user.is_team_lead:
            projects = user.get_authorized_projects()
            if projects:
                from django.db.models import Q
                q_objs = Q()
                for p in projects:
                    q_objs |= Q(project__icontains=p)
                return self.filter(q_objs)
            return self.for_employee(user.emp_id)
        return self.for_employee(user.emp_id)


class DateRangeQuerySet(models.QuerySet):  # pragma: no cover — no concrete model uses this yet
    """Half-open date filtering on a configurable column."""

    date_field = "created_at"

    def on_day(self, day=None):
        start, end = day_bounds(day)
        return self.filter(**{f"{self.date_field}__gte": start,
                              f"{self.date_field}__lt": end})

    def between(self, start, end):
        """``end`` is inclusive of the whole day when a date is passed."""
        qs = self
        if start:
            qs = qs.filter(**{f"{self.date_field}__gte": start})
        if end:
            qs = qs.filter(**{f"{self.date_field}__lt": end})
        return qs
