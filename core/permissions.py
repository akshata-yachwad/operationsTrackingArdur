"""DRF permission classes.

``IsAuthenticatedEmployee`` is the project-wide default (see
settings.REST_FRAMEWORK). A view that declares nothing is closed, not open.

Roles come from ot_employees, which is the business source of truth. There is
no second copy of "who is an admin" anywhere in this codebase.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAuthenticatedEmployee(BasePermission):
    """Signed in, and the account has not been deactivated.

    ``is_active`` is checked on every request rather than only at login, so
    deactivating an employee takes effect on their next click instead of
    whenever their session happens to expire.
    """

    message = "You need to be signed in to do that."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_active)


class IsAdmin(IsAuthenticatedEmployee):
    message = "Only an administrator can do that."

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.is_admin


class IsProjectAdmin(IsAuthenticatedEmployee):
    message = "Only a project admin or super admin can do that."

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.is_project_admin


class IsManager(IsAuthenticatedEmployee):
    """SuperAdmin, ProjectAdmin, or TeamLead."""
    message = "Only a manager can do that."

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.is_team_lead

# Alias for backward compatibility during migration
IsAdminOrSupervisor = IsProjectAdmin


class IsAdminOrReadOnly(IsAuthenticatedEmployee):
    """Everyone signed in may read; only admins may write.

    This is the right shape for master data — every screen needs the list of
    projects, but an employee must not be able to delete one.
    """

    message = "Only an administrator can change this."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin


class IsSupervisorOrReadOnly(IsAuthenticatedEmployee):
    message = "Only a supervisor or administrator can change this."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_supervisor


class IsOwnerOrSupervisor(IsAuthenticatedEmployee):
    """Object-level ownership.

    The ViewSet declares which attribute carries the owner's employee id::

        class FeedbackViewSet(ModelViewSet):
            permission_classes = [IsOwnerOrSupervisor]
            owner_field = "emp_id"

    Object permissions only run when the view calls
    ``get_object()``. A list endpoint must additionally scope its queryset —
    ``ScopedQuerysetMixin`` in core/mixins.py does that.
    """

    message = "That record belongs to someone else."
    default_owner_field = "emp_id"

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_supervisor:
            return True
        owner_field = getattr(view, "owner_field", self.default_owner_field)
        return getattr(obj, owner_field, None) == request.user.emp_id


class IsSelfOrAdmin(IsAuthenticatedEmployee):
    """For /accounts/ endpoints where the object *is* a user."""

    message = "You can only change your own account."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_admin:
            return True
        return getattr(obj, "emp_id", None) == request.user.emp_id


class AllowAnyPublic(BasePermission):
    """Explicitly public.

    Used only by login and the health probes. Named verbosely on purpose:
    ``permission_classes = [AllowAnyPublic]`` in a diff is a deliberate,
    reviewable decision in a way that ``[AllowAny]`` is not.
    """

    def has_permission(self, request, view) -> bool:
        return True
