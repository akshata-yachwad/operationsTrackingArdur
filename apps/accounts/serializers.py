"""Serializers for accounts.

Read and write serializers are separate on purpose. One class that does both
inevitably grows a field an attacker can set — ``role`` being the obvious one.
"""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import Employee, EmployeeType, LoginHistory, Role, Status, User
from core.validators import validate_emp_id, validate_non_blank


class LoginSerializer(serializers.Serializer):
    """Input only — never echo anything from here back to the client."""

    emp_id = serializers.CharField(max_length=20, validators=[validate_emp_id])
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)


class CurrentUserSerializer(serializers.ModelSerializer):
    """The signed-in user's own profile. Used by /auth/me/ and injected into
    every page as ``current_user``."""

    role = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    is_admin = serializers.BooleanField(read_only=True)
    is_supervisor = serializers.BooleanField(read_only=True)
    project = serializers.SerializerMethodField()
    shift = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "emp_id", "name", "display_name", "role",
            "is_admin", "is_supervisor", "status", "project", "shift", "last_login",
        ]
        read_only_fields = fields

    def get_project(self, obj) -> str:
        return obj.employee.project if obj.employee else ""

    def get_shift(self, obj) -> str:
        return obj.employee.shift if obj.employee else ""


class EmployeeSerializer(serializers.ModelSerializer):
    """Read shape for employee records."""

    has_login = serializers.SerializerMethodField()
    project_names = serializers.SerializerMethodField()
    client_code_names = serializers.SerializerMethodField()
    work_type_names = serializers.SerializerMethodField()

    # Legacy aliases for JS compatibility
    emp_id = serializers.CharField(source="employee_id", read_only=True)
    joining_date = serializers.DateField(source="date_of_joining", read_only=True)
    work_location = serializers.CharField(source="department", read_only=True)
    projects = serializers.CharField(source="project", read_only=True)
    shift_time = serializers.CharField(source="shift", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "employee_id", "emp_id", "name", "email", "phone", "alternate_phone", "role", "designation",
            "department", "project", "shift", "reporting_to", "date_of_joining",
            "status", "employee_type", "has_login", "created_at", "updated_at",
            "client_code", "work_type", "active_inactive_date",
            "joining_date", "work_location", "projects", "shift_time",
            "project_names", "client_code_names", "work_type_names"
        ]
        read_only_fields = fields

    def get_has_login(self, obj) -> bool:
        return User.objects.filter(emp_id=obj.employee_id).exists()

    def get_project_names(self, obj) -> list[str]:
        if not obj.project:
            return []
        p_ids = [p.strip() for p in (obj.project or "").split("|") if p.strip()]
        if not p_ids:
            return []
        from apps.masters.models import Project
        return list(Project.objects.filter(project_id__in=p_ids).values_list("project_name", flat=True))

    def get_client_code_names(self, obj) -> list[str]:
        return [c.strip() for c in obj.client_code.split("|") if c.strip()] if obj.client_code else []

    def get_work_type_names(self, obj) -> list[str]:
        return [w.strip() for w in obj.work_type.split("|") if w.strip()] if obj.work_type else []


class EmployeeWriteSerializer(serializers.ModelSerializer):
    """Create / update shape.

    ``max_length`` on every text field is matched to the column width, so an
    over-long value returns 400 instead of being silently truncated into a
    row nobody can find again.
    """

    employee_id = serializers.CharField(max_length=20, required=True, allow_blank=False)
    name = serializers.CharField(max_length=100, validators=[validate_non_blank])
    role = serializers.CharField(max_length=20, default=Role.EMPLOYEE)
    employee_type = serializers.CharField(max_length=50, default=EmployeeType.EMPLOYEE)
    status = serializers.CharField(max_length=10, default=Status.ACTIVE)
    # Optional: set a login password at creation time.
    password = serializers.CharField(
        max_length=128, write_only=True, required=False, allow_blank=True
    )

    def validate_employee_id(self, value: str) -> str:
        if value:
            validate_emp_id(value)
        return value
    
    # Legacy aliases for JS compatibility
    joining_date = serializers.DateField(source="date_of_joining", required=False, allow_null=True)
    work_location = serializers.CharField(source="department", max_length=100, required=False, allow_blank=True)
    projects = serializers.CharField(source="project", max_length=150, required=False, allow_blank=True)
    shift_time = serializers.CharField(source="shift", max_length=50, required=False, allow_blank=True)

    class Meta:
        model = Employee
        fields = [
            "employee_id", "name", "email", "phone", "alternate_phone", "role", "designation",
            "department", "project", "shift", "reporting_to", "date_of_joining",
            "status", "employee_type", "password", "client_code", "work_type", "active_inactive_date",
            "joining_date", "work_location", "projects", "shift_time"
        ]

    def validate_role(self, value: str) -> str:
        val = (value or "").strip().lower()
        if val in [r.value for r in Role]:
            return val
        return value

    def validate_status(self, value: str) -> str:
        val = (value or "").strip().lower()
        if val in [s.value for s in Status]:
            return val
        return value

    def validate_employee_id(self, value: str) -> str:
        qs = Employee.objects.filter(employee_id=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("An employee with this ID already exists.")
        return value

    def validate_password(self, value: str) -> str:
        if value:
            validate_password(value)
        return value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The two passwords do not match."}
            )
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError(
                {"new_password": "Choose a password you have not used here before."}
            )
        validate_password(attrs["new_password"])
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """Admin-driven reset. There is no email round-trip: an ops floor
    supervisor resets a password in person."""

    emp_id = serializers.CharField(max_length=20, validators=[validate_emp_id])
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value


class LoginHistorySerializer(serializers.ModelSerializer):
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = LoginHistory
        fields = [
            "id", "emp_id", "name", "date", "login_time", "logout_time",
            "duration_seconds", "ip_address",
        ]
        read_only_fields = fields


class CheckEmployeeSerializer(serializers.Serializer):
    emp_id = serializers.CharField(max_length=20, validators=[validate_emp_id])


class SignupSerializer(serializers.Serializer):
    emp_id = serializers.CharField(max_length=20, validators=[validate_emp_id])
    name = serializers.CharField(max_length=100, validators=[validate_non_blank])
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)

    def validate_password(self, value: str) -> str:
        if value:
            validate_password(value)
        return value
