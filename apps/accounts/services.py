"""Authentication and employee management.

The logout path here is the fix for "logout does not invalidate the session":
Django's server-side sessions make the replayed-cookie case impossible, and
``_revoke_sockets`` closes the WebSocket that authenticated at handshake and
would otherwise keep streaming to a signed-out user.
"""

from __future__ import annotations

import logging

from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from apps.accounts.models import Employee, LoginHistory, User
from core.events import publish
from core.exceptions import AuthenticationError, ConflictError, ValidationError
from core.services import BaseService
from core.timezone import now_ist, today_ist

logger = logging.getLogger("opstracking.auth")


class AuthService(BaseService):
    """Login, logout, password changes."""

    def login(self, request, emp_id: str, password: str) -> User:
        user = authenticate(request, username=emp_id, password=password)

        if user is None:
            # One message for "no such user" and "wrong password" — a
            # distinguishable response is a free employee-ID oracle.
            logger.warning("failed login for %r from %s", emp_id, _client_ip(request))
            raise AuthenticationError("Incorrect employee ID or password.")

        if not user.is_active:
            raise AuthenticationError("This account has been deactivated. Contact your supervisor.")

        # Rotates the session key, which invalidates any pre-login session and
        # closes the session-fixation hole.
        django_login(request, user)

        User.objects.filter(pk=user.pk).update(
            last_login=now_ist(), session_id=request.session.session_key
        )

        LoginHistory.objects.create(
            emp_id=user.emp_id,
            name=user.display_name,
            date=today_ist(),
            login_time=now_ist(),
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            session_key=request.session.session_key or "",
        )

        self.actor = user
        self.log("login", emp_id=user.emp_id)
        transaction.on_commit(lambda: self._announce_online(user.emp_id))
        return user

    def logout(self, request) -> None:
        user = request.user
        if not user.is_authenticated:
            return

        emp_id = user.emp_id
        session_key = request.session.session_key

        LoginHistory.objects.filter(emp_id=emp_id, logout_time__isnull=True).update(
            logout_time=now_ist()
        )
        User.objects.filter(pk=user.pk).update(session_id=None)

        # Deletes the django_session row. A replayed cookie now resolves to
        # nothing and the next request is anonymous.
        django_logout(request)

        self.actor = user
        self.log("logout", emp_id=emp_id)

        # Invalidating the HTTP session does NOT close an already-open
        # WebSocket — it authenticated once, at handshake. Without this, a
        # signed-out user keeps receiving pushes.
        self._revoke_sockets(emp_id, session_key)

    def force_logout(self, emp_id: str) -> None:
        """Administrative force logout for a stuck or unattended session."""
        self.require_admin("Only an administrator can force logout an employee.")
        
        user = self.require_found(
            User.objects.filter(emp_id=emp_id).first(),
            f"No login exists for employee {emp_id}.",
        )
        
        session_key = user.session_id
        
        # Close open login history
        LoginHistory.objects.filter(emp_id=emp_id, logout_time__isnull=True).update(
            logout_time=now_ist()
        )
        
        # Clear their session
        User.objects.filter(pk=user.pk).update(session_id=None)
        
        if session_key:
            try:
                from django.contrib.sessions.models import Session
                Session.objects.filter(session_key=session_key).delete()
            except Exception:
                pass
                
        self.log("force_logout", target=emp_id)
        self._revoke_sockets(emp_id, session_key)
        
        try:
            from apps.presence.services import PresenceService
            PresenceService().set_manual(emp_id, "offline", "Forced logout")
        except Exception:
            pass
            
        # Try stopping any active tracking session they might have left running
        try:
            from apps.tracking.services import TrackingService
            from apps.tracking.models import WorkSession
            active = WorkSession.objects.filter(emp_id=emp_id).active_now().first()
            if active:
                TrackingService(actor=self.actor).stop_session(active.id)
        except Exception:
            pass
            
        # Try stopping any active Title Indexing Session
        try:
            from apps.allocations.models import TitleIndexingSession
            active_idx = TitleIndexingSession.objects.filter(employee_id=emp_id, status='IN_PROGRESS').first()
            if active_idx:
                active_idx.status = 'COMPLETED'
                active_idx.completed_at = now_ist()
                
                # Calculate time taken
                diff = active_idx.completed_at - active_idx.started_at
                total_seconds = int(diff.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                active_idx.time_taken = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
                active_idx.save()
        except Exception:
            pass

        # Try stopping any active BreakTime
        try:
            from apps.breaks.services import BreakService
            from apps.breaks.models import BreakTime
            brk = BreakTime.objects.filter(user_id=emp_id, end_time__isnull=True).first()
            if brk:
                BreakService(actor=self.actor).force_end_break(brk.id)
        except Exception:
            pass

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not user.check_password(current_password):
            raise AuthenticationError("Your current password is not correct.")

        user.password = make_password(new_password)
        user.save(update_fields=["password"])
        self.log("password_changed", emp_id=user.emp_id)

    def signup(self, emp_id: str, name: str, password: str) -> User:
        """Self-service account creation for an employee HR has already added.

        Deliberately does not create the ``Employee`` row — that stays an
        admin/supervisor action via ``EmployeeService.create``. Without the
        existence check below, anyone could invent an emp_id and sign in as
        an "employee" with no real Employee record behind it.
        """
        employee = self.require_found(
            Employee.objects.filter(employee_id=emp_id, status__iexact="active").first(),
            "No active employee record found for that ID. Ask your supervisor to add you first.",
        )

        if User.objects.filter(emp_id=emp_id).exists():
            raise ConflictError(f"An account for {emp_id} already exists. Try logging in instead.")

        validate_password(password)
        user = User.objects.create_user(emp_id=emp_id, password=password, name=name or employee.name)

        self.log("signup", emp_id=emp_id)
        return user

    def reset_password(self, emp_id: str, new_password: str) -> User:
        """Administrative reset — the admin check is the caller's job via
        permission_classes, and re-asserted here for non-HTTP callers."""
        self.require_admin("Only an administrator can reset a password.")

        user = self.require_found(
            User.objects.filter(emp_id=emp_id).first(),
            f"No login exists for employee {emp_id}.",
        )
        user.password = make_password(new_password)
        user.save(update_fields=["password"])

        self.log("password_reset", target=emp_id)
        # Force them to sign in again everywhere with the new credentials.
        self._revoke_sockets(emp_id, None)
        return user

    # ── internals ────────────────────────────────────────────

    @staticmethod
    def _revoke_sockets(emp_id: str, session_key: str | None) -> None:
        from apps.realtime.groups import user_group

        publish(
            group=user_group(emp_id),
            event="session.revoked",
            data={"session_key": session_key},
            durable=False,
        )

    @staticmethod
    def _announce_online(emp_id: str) -> None:
        from apps.presence.services import PresenceService

        PresenceService().recompute(emp_id)


class EmployeeService(BaseService):
    """CRUD for employee records, plus the paired login account."""

    @transaction.atomic
    def create(self, data: dict) -> Employee:
        self.require_project_admin("Only a project admin or super admin can add an employee.")

        if self.actor and not self.actor.is_super_admin:
            projects = [p.strip() for p in data.get("project", "").split("|") if p.strip()]
            for p in projects:
                self.require_project_access(p, f"You cannot assign employees to project {p}.")

        password = data.pop("password", None)
        employee_id = data.get("employee_id")
        
        if not employee_id:
            raise ValidationError("Employee ID is required.")

        if Employee.objects.filter(employee_id=employee_id).exists():
            raise ConflictError(f"An employee with ID {employee_id} already exists.")

        # Only a super admin may mint a super admin or project admin.
        # Without this a project admin can escalate to super admin.
        if data.get("role") in ("super_admin", "project_admin"):
            self.require_super_admin("Only a super admin can create a project admin or super admin.")

        employee = Employee.objects.create(**data)

        if password:
            User.objects.create_user(
                emp_id=employee_id, password=password, name=employee.name
            )

        self.log("employee_created", employee_id=employee_id)
        return employee

    @transaction.atomic
    def update(self, employee: Employee, data: dict) -> Employee:
        self.require_project_admin("Only a project admin or super admin can change an employee record.")

        if self.actor and not self.actor.is_super_admin:
            # Must have access to the employee's existing projects
            existing_projects = [p.strip() for p in employee.project.split("|") if p.strip()]
            for p in existing_projects:
                self.require_project_access(p, f"You cannot modify employees in project {p}.")
            
            # Must have access to the new projects
            new_projects = [p.strip() for p in data.get("project", "").split("|") if p.strip()]
            for p in new_projects:
                self.require_project_access(p, f"You cannot assign employees to project {p}.")

        new_role = data.get("role")
        if new_role and new_role != employee.role and ("super_admin" in (new_role, employee.role) or "project_admin" in (new_role, employee.role)):
            self.require_super_admin("Only a super admin can change an admin's role.")

        data.pop("password", None)  # password changes go through AuthService
        for field, value in data.items():
            setattr(employee, field, value)
        employee.updated_at = now_ist()
        employee.save()

        # Deactivating an employee must also end their live sessions.
        if employee.status != "active":
            User.objects.filter(emp_id=employee.employee_id).update(status="inactive")
            AuthService()._revoke_sockets(employee.employee_id, None)

        self.log("employee_updated", employee_id=employee.employee_id)
        return employee

    @transaction.atomic
    def deactivate(self, employee: Employee) -> Employee:
        """Deactivate rather than delete.

        Hard-deleting an employee orphans every work session, break and
        feedback row that references their emp_id, and silently changes last
        month's reports.
        """
        self.require_project_admin("Only a project admin or super admin can deactivate an employee.")

        if self.actor and not self.actor.is_super_admin:
            existing_projects = [p.strip() for p in employee.project.split("|") if p.strip()]
            for p in existing_projects:
                self.require_project_access(p, f"You cannot deactivate employees in project {p}.")

        if self.actor and employee.employee_id == self.actor.emp_id:
            raise ValidationError("You cannot deactivate your own account.")

        employee.status = "inactive"
        employee.updated_at = now_ist()
        employee.save(update_fields=["status", "updated_at"])

        User.objects.filter(emp_id=employee.employee_id).update(status="inactive")
        AuthService()._revoke_sockets(employee.employee_id, None)

        self.log("employee_deactivated", employee_id=employee.employee_id)
        return employee


def _client_ip(request) -> str | None:
    """Prefer X-Forwarded-For's first hop — Apache proxies to 127.0.0.1, so
    REMOTE_ADDR alone would log every user as localhost."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45] or None
    return request.META.get("REMOTE_ADDR")
