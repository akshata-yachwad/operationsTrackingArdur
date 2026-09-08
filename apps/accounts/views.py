"""Account endpoints. Views parse and render; AuthService decides."""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.accounts.models import Employee, LoginHistory
from apps.accounts.serializers import (
    CurrentUserSerializer,
    EmployeeSerializer,
    EmployeeWriteSerializer,
    LoginHistorySerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
)
from apps.accounts.services import AuthService, EmployeeService
from core.mixins import EnvelopeMixin, ServiceMixin
from core.permissions import (
    AllowAnyPublic,
    IsAdmin,
    IsAdminOrSupervisor,
    IsAuthenticatedEmployee,
)
from core.throttling import LoginThrottle


class LoginView(EnvelopeMixin, APIView):
    """POST /api/v1/auth/login/"""

    permission_classes = [AllowAnyPublic]
    authentication_classes = []
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = AuthService().login(
            request,
            emp_id=serializer.validated_data["emp_id"],
            password=serializer.validated_data["password"],
        )
        return self.ok(CurrentUserSerializer(user).data)


class LogoutView(EnvelopeMixin, APIView):
    """POST /api/v1/auth/logout/"""

    permission_classes = [IsAuthenticatedEmployee]

    def post(self, request):
        AuthService().logout(request)
        return self.ok({"detail": "Signed out."})


class CurrentUserView(EnvelopeMixin, APIView):
    """GET /api/v1/auth/me/ — the client bootstraps from this on page load."""

    permission_classes = [IsAuthenticatedEmployee]

    def get(self, request):
        return self.ok(CurrentUserSerializer(request.user).data)


class PasswordChangeView(EnvelopeMixin, APIView):
    """POST /api/v1/auth/password/change/ — changes your own password."""

    permission_classes = [IsAuthenticatedEmployee]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService(actor=request.user).change_password(
            request.user,
            serializer.validated_data["current_password"],
            serializer.validated_data["new_password"],
        )
        return self.ok({"detail": "Password updated."})


class PasswordResetView(EnvelopeMixin, APIView):
    """POST /api/v1/auth/password/reset/ — an admin resets someone else's."""

    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService(actor=request.user).reset_password(
            serializer.validated_data["emp_id"],
            serializer.validated_data["new_password"],
        )
        return self.ok({"detail": "Password reset."})


class ForceLogoutView(EnvelopeMixin, APIView):
    """POST /api/v1/auth/force-logout/<emp_id>/ — admin force logouts a user."""

    permission_classes = [IsAdmin]

    def post(self, request, emp_id):
        AuthService(actor=request.user).force_logout(emp_id)
        return self.ok({"detail": "User forcibly logged out."})


class EmployeeViewSet(ServiceMixin, EnvelopeMixin, viewsets.ModelViewSet):
    """/api/v1/auth/employees/

    Everyone signed in can read the roster (the app needs names everywhere);
    only supervisors and admins can change it.
    """

    queryset = Employee.objects.all()
    service_class = EmployeeService
    lookup_field = "employee_id"
    search_fields = ["employee_id", "name", "email", "project", "designation"]
    ordering_fields = ["name", "employee_id", "role", "date_of_joining"]
    ordering = ["name"]
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedEmployee()]
        return [IsAdminOrSupervisor()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return EmployeeWriteSerializer
        return EmployeeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user.is_super_admin:
            projects = user.get_authorized_projects()
            if projects:
                from django.db.models import Q
                q_objs = Q()
                for p in projects:
                    q_objs |= Q(project__icontains=p)
                queryset = queryset.filter(q_objs)
            else:
                # If no authorized projects (e.g. basic employee), only see themselves
                queryset = queryset.filter(employee_id=user.emp_id)

        if self.request.query_params.get("active") == "true":
            queryset = queryset.active()
        if role := self.request.query_params.get("role"):
            queryset = queryset.filter(role=role)
        if project := self.request.query_params.get("project"):
            queryset = queryset.filter(project__icontains=project)
        return queryset



    def perform_create(self, serializer):
        serializer.instance = self.service.create(dict(serializer.validated_data))

    def perform_update(self, serializer):
        serializer.instance = self.service.update(
            serializer.instance, dict(serializer.validated_data)
        )

    def perform_destroy(self, instance):
        self.service.deactivate(instance)

    @action(detail=False, methods=["get"], url_path="supervisors")
    def supervisors(self, request):
        """Used to populate 'reporting to' pickers."""
        queryset = Employee.objects.supervisors()
        return self.ok(EmployeeSerializer(queryset, many=True).data)


class LoginHistoryViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    """/api/v1/auth/login-history/

    Employees see their own rows; supervisors see everyone's. The scoping is
    on the queryset, not only on object permissions — a list endpoint is not
    protected by has_object_permission.
    """

    serializer_class = LoginHistorySerializer
    permission_classes = [IsAuthenticatedEmployee]
    ordering = ["-login_time"]

    def get_queryset(self):
        queryset = LoginHistory.objects.visible_to(self.request.user)
        if emp_id := self.request.query_params.get("emp_id"):
            queryset = queryset.filter(emp_id=emp_id)
        if date_from := self.request.query_params.get("from"):
            queryset = queryset.filter(date__gte=date_from)
        if date_to := self.request.query_params.get("to"):
            queryset = queryset.filter(date__lte=date_to)
        return queryset


class CheckEmployeeView(EnvelopeMixin, APIView):
    """POST /api/v1/auth/check-employee/ — Used by signup page to autofill names."""

    permission_classes = [AllowAnyPublic]
    authentication_classes = []

    def post(self, request):
        from apps.accounts.serializers import CheckEmployeeSerializer
        from core.exceptions import NotFoundError

        serializer = CheckEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emp_id = serializer.validated_data["emp_id"]

        employee = Employee.objects.filter(employee_id=emp_id, status__iexact="active").first()
        if not employee:
            raise NotFoundError("Employee ID not found.")
        return self.ok({"name": employee.name})


class SignupView(EnvelopeMixin, APIView):
    """POST /api/v1/auth/signup/ — sets a password for an employee HR already added."""

    permission_classes = [AllowAnyPublic]
    authentication_classes = []

    def post(self, request):
        from apps.accounts.serializers import SignupSerializer

        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = AuthService().signup(**serializer.validated_data)
        return self.ok({"emp_id": user.emp_id, "message": "Account created. You can log in now."},
                        status=201)