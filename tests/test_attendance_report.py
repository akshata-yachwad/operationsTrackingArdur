from __future__ import annotations

from datetime import timedelta

import pytest

from apps.accounts.models import Employee, LoginHistory, Role, User
from apps.masters.models import Project, Shift
from core.timezone import start_of_day, today_ist


@pytest.fixture
def attendance_admin(db):
    employee = Employee.objects.create(
        employee_id="ATT-ADMIN",
        name="Attendance Admin",
        role=Role.SUPER_ADMIN,
        status="active",
    )
    return User.objects.create_user(
        emp_id=employee.employee_id,
        name=employee.name,
        password="test-password-123",
    )


def _report(api, user, **params):
    api.force_authenticate(user=user)
    return api.get("/api/v1/tracking/attendance/admin-report/", params)


@pytest.mark.django_db
def test_report_defaults_to_all_projects_and_supports_combined_filters(api, attendance_admin):
    Project.objects.create(project_id="P-1", project_name="Project One")
    Project.objects.create(project_id="P-2", project_name="Project Two")
    employee = Employee.objects.create(
        employee_id="AT0051",
        name="Nikita Sharma",
        project="P-1",
        department=" Operations ",
        status="active",
    )
    Employee.objects.create(
        employee_id="AT0052",
        name="Nikita Rao",
        project="P-2",
        department="Remote",
        status="active",
    )

    all_projects = _report(api, attendance_admin)
    filtered = _report(
        api,
        attendance_admin,
        **{
            "from": today_ist().isoformat(),
            "to": today_ist().isoformat(),
            "project": "P-1",
            "location": "Operations",
            "search": "nikita",
        },
    )
    id_filtered = _report(
        api,
        attendance_admin,
        **{"from": today_ist().isoformat(), "search": "at0051"},
    )

    assert all_projects.status_code == filtered.status_code == id_filtered.status_code == 200
    assert {row["emp_id"] for row in all_projects.data["data"]} == {"AT0051", "AT0052"}
    assert {row["date"] for row in all_projects.data["data"]} == {today_ist().isoformat()}
    assert len(filtered.data["data"]) == 1
    assert filtered.data["data"][0]["emp_id"] == employee.employee_id
    assert filtered.data["data"][0]["location"] == "Operations"
    assert filtered.data["data"][0]["status"] == "No Record"
    assert [row["emp_id"] for row in id_filtered.data["data"]] == ["AT0051"]


@pytest.mark.django_db
def test_report_merges_duplicate_sessions_and_rejects_next_day_logout(api, attendance_admin):
    Project.objects.create(project_id="P-1", project_name="Project One")
    employee = Employee.objects.create(
        employee_id="AT0051",
        name="Nikita Sharma",
        project="P-1",
        status="active",
    )
    day = today_ist() - timedelta(days=3)
    day_start = start_of_day(day)
    sessions = [
        (day_start + timedelta(hours=9), day_start + timedelta(hours=10)),
        (day_start + timedelta(hours=9, minutes=30), day_start + timedelta(hours=10, minutes=30)),
        (day_start + timedelta(hours=17), day_start + timedelta(hours=18)),
        (day_start + timedelta(hours=19), day_start + timedelta(days=1, hours=19)),
    ]
    for login_time, logout_time in sessions:
        LoginHistory.objects.create(
            emp_id=employee.employee_id,
            date=day,
            login_time=login_time,
            logout_time=logout_time,
        )

    response = _report(
        api,
        attendance_admin,
        **{"from": day.isoformat(), "to": day.isoformat()},
    )

    assert response.status_code == 200
    row = response.data["data"][0]
    assert row["emp_id"] == employee.employee_id
    assert row["net_working_seconds"] == 9_000
    assert row["net_working_hours"] == 2.5


@pytest.mark.django_db
def test_report_supports_configured_overnight_shift(api, attendance_admin):
    Project.objects.create(project_id="P-1", project_name="Project One")
    employee = Employee.objects.create(
        employee_id="AT0051",
        name="Nikita Sharma",
        project="P-1",
        shift="Night",
        status="active",
    )
    Shift.objects.create(shift_name="Night", start_time="22:00", end_time="06:00")
    day = today_ist() - timedelta(days=3)
    start = start_of_day(day) + timedelta(hours=22)
    LoginHistory.objects.create(
        emp_id=employee.employee_id,
        date=day,
        login_time=start,
        logout_time=start + timedelta(hours=8),
    )

    response = _report(
        api,
        attendance_admin,
        **{"from": day.isoformat(), "to": day.isoformat()},
    )

    assert response.status_code == 200
    assert response.data["data"][0]["net_working_seconds"] == 28_800


@pytest.mark.django_db
def test_open_current_login_is_in_progress_and_uses_server_time(api, attendance_admin, monkeypatch):
    Project.objects.create(project_id="P-1", project_name="Project One")
    employee = Employee.objects.create(
        employee_id="AT0051",
        name="Nikita Sharma",
        project="P-1",
        status="active",
    )
    day = today_ist()
    start = start_of_day(day) + timedelta(hours=9)
    server_now = start_of_day(day) + timedelta(hours=12)
    LoginHistory.objects.create(
        emp_id=employee.employee_id,
        date=day,
        login_time=start,
    )
    monkeypatch.setattr("apps.tracking.views.now_ist", lambda: server_now)

    response = _report(
        api,
        attendance_admin,
        **{"from": day.isoformat(), "to": day.isoformat()},
    )

    assert response.status_code == 200
    row = response.data["data"][0]
    assert row["status"] == "In Progress"
    assert row["net_working_seconds"] == 10_800
    assert row["last_logout"] is None
