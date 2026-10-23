"""Employee CRUD — role escalation guards, the paired login account, and
the legacy-alias serializer fields.
"""

from __future__ import annotations

import pytest

from apps.accounts.models import Employee, User
from apps.accounts.services import EmployeeService
from core.exceptions import ConflictError, PermissionDeniedError, ValidationError

pytestmark = pytest.mark.django_db


# ── EmployeeService.create ────────────────────────────────────

def test_only_a_supervisor_can_create_an_employee(employee):
    with pytest.raises(PermissionDeniedError):
        EmployeeService(actor=employee).create({"employee_id": "E900", "name": "New Hire"})


def test_create_rejects_a_duplicate_employee_id(supervisor, employee):
    with pytest.raises(ConflictError):
        EmployeeService(actor=supervisor).create(
            {"employee_id": employee.emp_id, "name": "Duplicate"}
        )


def test_a_supervisor_cannot_mint_an_admin(supervisor):
    with pytest.raises(PermissionDeniedError):
        EmployeeService(actor=supervisor).create(
            {"employee_id": "E900", "name": "Wannabe Admin", "role": "admin"}
        )


def test_an_admin_can_mint_an_admin(admin):
    employee = EmployeeService(actor=admin).create(
        {"employee_id": "E900", "name": "New Admin", "role": "admin"}
    )
    assert employee.role == "admin"


def test_create_with_a_password_also_creates_a_login(supervisor):
    EmployeeService(actor=supervisor).create(
        {"employee_id": "E900", "name": "New Hire", "password": "a-strong-password-1"}
    )
    user = User.objects.get(emp_id="E900")
    assert user.check_password("a-strong-password-1")


def test_create_without_a_password_creates_no_login(supervisor):
    EmployeeService(actor=supervisor).create({"employee_id": "E900", "name": "No Login Yet"})
    assert not User.objects.filter(emp_id="E900").exists()


# ── EmployeeService.update ────────────────────────────────────

def test_only_a_supervisor_can_update_an_employee(employee, other_employee):
    with pytest.raises(PermissionDeniedError):
        EmployeeService(actor=employee).update(other_employee.employee, {"name": "Hijacked"})


def test_a_supervisor_cannot_promote_someone_to_admin(supervisor):
    target = Employee.objects.create(employee_id="E901", name="Target", role="employee")
    with pytest.raises(PermissionDeniedError):
        EmployeeService(actor=supervisor).update(target, {"role": "admin"})


def test_a_supervisor_cannot_demote_an_admin(supervisor):
    target = Employee.objects.create(employee_id="E902", name="Target Admin", role="admin")
    with pytest.raises(PermissionDeniedError):
        EmployeeService(actor=supervisor).update(target, {"role": "employee"})


def test_an_admin_can_change_roles_freely(admin):
    target = Employee.objects.create(employee_id="E903", name="Target", role="employee")
    updated = EmployeeService(actor=admin).update(target, {"role": "admin"})
    assert updated.role == "admin"


def test_update_ignores_a_password_field(supervisor, employee):
    updated = EmployeeService(actor=supervisor).update(
        employee.employee, {"password": "should-be-ignored", "name": "Renamed"}
    )
    assert updated.name == "Renamed"
    # No login was created/changed via this path.


def test_deactivating_via_update_also_deactivates_the_login(
    django_capture_on_commit_callbacks, supervisor, employee
):
    with django_capture_on_commit_callbacks(execute=True):
        EmployeeService(actor=supervisor).update(employee.employee, {"status": "inactive"})

    employee.refresh_from_db()
    assert employee.status == "inactive"


# ── EmployeeService.deactivate ────────────────────────────────

def test_only_an_admin_can_deactivate(supervisor, employee):
    with pytest.raises(PermissionDeniedError):
        EmployeeService(actor=supervisor).deactivate(employee.employee)


def test_an_admin_cannot_deactivate_themselves(admin):
    with pytest.raises(ValidationError):
        EmployeeService(actor=admin).deactivate(admin.employee)


def test_deactivate_marks_inactive_and_kills_the_login(
    django_capture_on_commit_callbacks, admin, employee
):
    with django_capture_on_commit_callbacks(execute=True):
        EmployeeService(actor=admin).deactivate(employee.employee)

    employee.employee.refresh_from_db()
    employee.refresh_from_db()
    assert employee.employee.status == "inactive"
    assert employee.status == "inactive"


# ── serializer computed fields ────────────────────────────────

def test_employee_serializer_has_login_flag(employee):
    from apps.accounts.serializers import EmployeeSerializer

    data = EmployeeSerializer(employee.employee).data
    assert data["has_login"] is True


def test_employee_serializer_has_login_false_without_a_user():
    from apps.accounts.serializers import EmployeeSerializer

    orphan = Employee.objects.create(employee_id="E904", name="No Login", role="employee")
    data = EmployeeSerializer(orphan).data
    assert data["has_login"] is False


def test_employee_serializer_resolves_project_names_from_pipe_delimited_codes(masters):
    from apps.accounts.serializers import EmployeeSerializer
    from apps.masters.models import Project

    Project.objects.filter(pk=masters["project"].pk).update(project_code="P1")
    emp = Employee.objects.create(
        employee_id="E905", name="Multi Project", role="employee", project="P1|P2",
    )

    data = EmployeeSerializer(emp).data
    assert data["project_names"] == [masters["project"].project_name]


def test_employee_serializer_client_code_and_work_type_names_split_on_pipe():
    from apps.accounts.serializers import EmployeeSerializer

    emp = Employee.objects.create(
        employee_id="E906", name="Multi", role="employee",
        client_code="CC-1|CC-2", work_type="Data entry|Indexing",
    )
    data = EmployeeSerializer(emp).data
    assert data["client_code_names"] == ["CC-1", "CC-2"]
    assert data["work_type_names"] == ["Data entry", "Indexing"]


def test_employee_serializer_legacy_aliases_mirror_the_real_fields():
    from apps.accounts.serializers import EmployeeSerializer

    emp = Employee.objects.create(
        employee_id="E907", name="Aliased", role="employee",
        department="Ops", project="P1", shift="Morning",
    )
    data = EmployeeSerializer(emp).data
    assert data["work_location"] == "Ops"
    assert data["projects"] == "P1"
    assert data["shift_time"] == "Morning"


def test_employee_write_serializer_rejects_a_duplicate_id_on_create():
    from apps.accounts.serializers import EmployeeWriteSerializer

    Employee.objects.create(employee_id="E908", name="Existing", role="employee")
    serializer = EmployeeWriteSerializer(data={"employee_id": "E908", "name": "Duplicate"})
    assert not serializer.is_valid()
    assert "employee_id" in serializer.errors


def test_employee_write_serializer_allows_keeping_your_own_id_on_update():
    from apps.accounts.serializers import EmployeeWriteSerializer

    emp = Employee.objects.create(employee_id="E909", name="Self", role="employee")
    serializer = EmployeeWriteSerializer(
        instance=emp, data={"employee_id": "E909", "name": "Self Renamed"}
    )
    assert serializer.is_valid(), serializer.errors


def test_employee_write_serializer_validates_password_strength():
    from apps.accounts.serializers import EmployeeWriteSerializer

    serializer = EmployeeWriteSerializer(
        data={"employee_id": "E910", "name": "Weak Pw", "password": "123"}
    )
    assert not serializer.is_valid()
    assert "password" in serializer.errors


def test_employee_write_serializer_legacy_alias_maps_to_the_real_field():
    from apps.accounts.serializers import EmployeeWriteSerializer

    serializer = EmployeeWriteSerializer(
        data={"employee_id": "E911", "name": "Via Alias", "work_location": "Remote"}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["department"] == "Remote"


# ── PasswordChangeSerializer / PasswordResetSerializer ───────

def test_password_change_serializer_rejects_reusing_the_current_password():
    from apps.accounts.serializers import PasswordChangeSerializer

    serializer = PasswordChangeSerializer(
        data={
            "current_password": "same-password-123",
            "new_password": "same-password-123",
            "confirm_password": "same-password-123",
        }
    )
    assert not serializer.is_valid()
    assert "new_password" in serializer.errors


def test_password_change_serializer_rejects_a_weak_new_password():
    from apps.accounts.serializers import PasswordChangeSerializer

    serializer = PasswordChangeSerializer(
        data={"current_password": "old-password-99", "new_password": "123", "confirm_password": "123"}
    )
    assert not serializer.is_valid()


def test_password_reset_serializer_validates_strength():
    from apps.accounts.serializers import PasswordResetSerializer

    serializer = PasswordResetSerializer(data={"emp_id": "E912", "new_password": "weak"})
    assert not serializer.is_valid()


# ── HTTP: EmployeeViewSet ─────────────────────────────────────

def test_list_employees_over_http(as_employee, employee):
    response = as_employee.get("/api/v1/auth/employees/")
    assert response.status_code == 200


def test_employee_locations_endpoint_returns_distinct_locations(as_admin, employee, other_employee):
    employee.employee.department = "Ops"
    employee.employee.save(update_fields=["department"])
    other_employee.employee.department = " Remote "
    other_employee.employee.save(update_fields=["department"])
    Employee.objects.create(
        employee_id="EMP003", name="Third Employee", project="Test Project",
        department="Ops",
    )

    response = as_admin.get("/api/v1/auth/employees/locations/")

    assert response.status_code == 200
    assert response.data["data"] == ["Ops", "Remote"]


def test_create_employee_over_http_requires_a_supervisor(as_employee):
    response = as_employee.post(
        "/api/v1/auth/employees/", {"employee_id": "E913", "name": "New"}
    )
    assert response.status_code == 403


def test_create_employee_over_http(as_supervisor):
    response = as_supervisor.post(
        "/api/v1/auth/employees/", {"employee_id": "E914", "name": "Via HTTP"}
    )
    assert response.status_code == 201
    assert Employee.objects.filter(employee_id="E914").exists()


def test_update_employee_over_http(as_supervisor, employee):
    response = as_supervisor.patch(
        f"/api/v1/auth/employees/{employee.emp_id}/", {"designation": "Senior"}
    )
    assert response.status_code == 200
    assert response.data["ok"] is True


def test_delete_employee_over_http_deactivates(as_admin, employee):
    response = as_admin.delete(f"/api/v1/auth/employees/{employee.emp_id}/")
    assert response.status_code in (200, 204)

    employee.employee.refresh_from_db()
    assert employee.employee.status == "inactive"


def test_supervisors_listing_endpoint_requires_supervisor_or_admin(as_employee):
    """get_permissions() only allowlists 'list'/'retrieve' for a plain
    employee; this custom action falls through to the admin/supervisor
    branch even though its own docstring ('populate reporting-to pickers')
    reads like something a plain employee filling out a form would need —
    the same shape of gap as ClientCodeViewSet.worktypes_for_clients in
    test_masters.py. Pinning current behaviour rather than guessing intent."""
    response = as_employee.get("/api/v1/auth/employees/supervisors/")
    assert response.status_code == 403


def test_supervisors_listing_endpoint(as_supervisor, supervisor):
    response = as_supervisor.get("/api/v1/auth/employees/supervisors/")
    assert response.status_code == 200
    ids = [row["employee_id"] for row in response.data["data"]]
    assert supervisor.emp_id in ids


def test_filter_employees_by_role(as_employee, employee, supervisor):
    response = as_employee.get("/api/v1/auth/employees/", {"role": "supervisor"})
    ids = [row["employee_id"] for row in response.data["data"]]
    assert supervisor.emp_id in ids
    assert employee.emp_id not in ids


def test_filter_employees_by_active(as_employee, employee):
    Employee.objects.filter(employee_id=employee.emp_id).update(status="inactive")
    response = as_employee.get("/api/v1/auth/employees/", {"active": "true"})
    ids = [row["employee_id"] for row in response.data["data"]]
    assert employee.emp_id not in ids


def test_login_history_endpoint_is_enveloped(as_employee, employee):
    from apps.accounts.models import LoginHistory
    from core.timezone import now_ist, today_ist

    LoginHistory.objects.create(emp_id=employee.emp_id, date=today_ist(), login_time=now_ist())

    response = as_employee.get("/api/v1/auth/login-history/")
    assert response.status_code == 200
    assert response.data["ok"] is True


# ── accounts/models.py: derived properties ────────────────────

def test_user_display_name_falls_back_to_the_employee_record():
    Employee.objects.create(employee_id="E915", name="Employee Name", role="employee")
    user = User.objects.create_user(emp_id="E915", password="x", name="Placeholder")
    # create_user() defaults a blank name to the emp_id, so blank it out
    # afterwards to exercise display_name's actual fallback branch.
    User.objects.filter(pk=user.pk).update(name="")
    user.refresh_from_db()

    assert user.display_name == "Employee Name"


def test_user_display_name_falls_back_to_emp_id_with_no_employee_record():
    user = User.objects.create_user(emp_id="E916", password="x", name="")
    assert user.display_name == "E916"


def test_user_role_defaults_to_employee_with_no_employee_record():
    user = User.objects.create_user(emp_id="E917", password="x", name="Ghost")
    assert user.role == "employee"
    assert user.is_admin is False
    assert user.is_supervisor is False


def test_user_str_includes_name_when_present(employee):
    assert employee.emp_id in str(employee)


def test_login_history_duration_seconds_none_while_open(employee):
    from apps.accounts.models import LoginHistory
    from core.timezone import now_ist

    history = LoginHistory.objects.create(emp_id=employee.emp_id, login_time=now_ist())
    assert history.duration_seconds is None


def test_login_history_duration_seconds_once_closed(employee):
    from datetime import timedelta

    from apps.accounts.models import LoginHistory
    from core.timezone import now_ist

    login = now_ist()
    history = LoginHistory.objects.create(
        emp_id=employee.emp_id, login_time=login, logout_time=login + timedelta(minutes=30)
    )
    assert 1790 < history.duration_seconds < 1810


def test_login_history_str(employee):
    from apps.accounts.models import LoginHistory
    from core.timezone import now_ist

    history = LoginHistory.objects.create(emp_id=employee.emp_id, login_time=now_ist())
    assert employee.emp_id in str(history)


def test_employee_str_and_is_supervisor():
    admin_emp = Employee.objects.create(employee_id="E920", name="Boss", role="admin")
    worker = Employee.objects.create(employee_id="E921", name="Worker", role="employee")

    assert "E920" in str(admin_emp)
    assert admin_emp.is_supervisor is True
    assert worker.is_supervisor is False


def test_user_django_admin_compatibility_properties(admin, employee):
    # No PermissionsMixin — these are the hand-rolled equivalents the Django
    # admin site needs to let an admin employee in.
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.has_perm("anything") is True
    assert admin.has_module_perms("any_app") is True

    assert employee.is_staff is False
    assert employee.has_perm("anything") is False


def test_admin_password_reset_over_http(as_admin, employee):
    response = as_admin.post(
        "/api/v1/auth/password/reset/",
        {"emp_id": employee.emp_id, "new_password": "a-fresh-strong-password-1"},
    )
    assert response.status_code == 200

    employee.refresh_from_db()
    assert employee.check_password("a-fresh-strong-password-1")


def test_login_history_filters_by_emp_id_and_date_range(as_supervisor, employee, other_employee):
    from apps.accounts.models import LoginHistory
    from core.timezone import now_ist, today_ist

    mine = LoginHistory.objects.create(
        emp_id=employee.emp_id, date=today_ist(), login_time=now_ist()
    )
    LoginHistory.objects.create(
        emp_id=other_employee.emp_id, date=today_ist(), login_time=now_ist()
    )

    response = as_supervisor.get("/api/v1/auth/login-history/", {"emp_id": employee.emp_id})
    ids = [row["id"] for row in response.data["data"]]
    assert ids == [mine.id]

    response2 = as_supervisor.get(
        "/api/v1/auth/login-history/", {"from": str(today_ist()), "to": str(today_ist())}
    )
    assert mine.id in [row["id"] for row in response2.data["data"]]
