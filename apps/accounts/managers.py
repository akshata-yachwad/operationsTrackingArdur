"""Managers for the account models."""

from __future__ import annotations

from django.contrib.auth.hashers import make_password
from django.db import models


class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="active")


class UserManager(models.Manager.from_queryset(UserQuerySet)):
    """Django's auth machinery calls get_by_natural_key() to resolve a login.

    Filtering on ``status="active"`` here means a deactivated employee cannot
    authenticate at all — the check happens before the password is even
    compared, so there is no path that skips it.
    """

    use_in_migrations = False

    def get_by_natural_key(self, emp_id: str):
        return self.get(emp_id=emp_id, status="active")

    def create_user(self, emp_id: str, password: str, name: str = "", **extra):
        if not emp_id:
            raise ValueError("emp_id is required.")
        user = self.model(emp_id=emp_id, name=name or emp_id, **extra)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, emp_id: str, password: str, name: str = "", **extra):
        """A superuser here is an employee whose ot_employees role is 'admin'.

        Roles live in ot_employees, which is the business source of truth —
        there is no is_superuser column to set, because a second copy of "who
        is an admin" is a second thing to get out of sync.
        """
        extra.setdefault("status", "active")
        user = self.create_user(emp_id, password, name, **extra)

        from apps.accounts.models import Employee

        Employee.objects.update_or_create(
            employee_id=emp_id,
            defaults={"name": name or emp_id, "role": "super_admin", "status": "active"},
        )
        return user


class EmployeeQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status="active")

    def supervisors(self):
        return self.filter(role__in=("admin", "supervisor"), status="active")

    def admins(self):
        return self.filter(role="admin", status="active")

    def for_project(self, project: str):
        return self.filter(project=project)


class EmployeeManager(models.Manager.from_queryset(EmployeeQuerySet)):
    pass


class LoginHistoryQuerySet(models.QuerySet):
    def open_sessions(self):
        """Rows where the user logged in but never logged out."""
        return self.filter(logout_time__isnull=True)

    def for_employee(self, emp_id: str):
        return self.filter(emp_id=emp_id)

    def visible_to(self, user):
        if user is None or not user.is_authenticated:
            return self.none()
        if user.is_supervisor:
            return self
        return self.for_employee(user.emp_id)


class LoginHistoryManager(models.Manager.from_queryset(LoginHistoryQuerySet)):
    pass
