"""Work sessions and daily targets — the core of the tracking domain.

test_timing.py already pins down server-side clocking (end_time, pause/resume
accounting, one-open-session). This file covers the rest of the surface:
deletion rules, the current/active/summary endpoints, list scoping and
filters, target roll-up, and the read serializer's derived fields.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from apps.tracking.models import SessionState, SoftwareShift, Target, WorkSession
from apps.tracking.services import TargetService, WorkSessionService
from core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from core.timezone import now_ist, start_of_day, today_ist

pytestmark = pytest.mark.django_db


# ── starting a session ───────────────────────────────────────

def test_start_session_records_allocation_and_batch(employee, masters):
    service = WorkSessionService(actor=employee)

    session = service.start_session(
        project="Test Project", work_type="Data entry",
        client_code="TST-001", batch="BATCH-7", allocation_id="ALLOC-9",
    )

    assert session.allocation_id == "ALLOC-9"
    assert session.batch == "BATCH-7"
    assert session.client_code == "TST-001"
    assert session.is_started == SessionState.RUNNING
    assert session.name == employee.display_name


def test_start_session_requires_an_actor(masters):
    with pytest.raises(PermissionDeniedError):
        WorkSessionService(actor=None).start_session(project="Test Project", work_type="Data entry")


def test_ad_hoc_work_has_no_allocation(employee, masters):
    """allocation_id is nullable and optional — work not against any batch."""
    session = WorkSessionService(actor=employee).start_session(
        project="Test Project", work_type="Data entry"
    )
    assert session.allocation_id is None


# ── deleting a session ───────────────────────────────────────

def test_owner_can_delete_their_own_open_session(employee, masters):
    service = WorkSessionService(actor=employee)
    session = service.start_session(project="Test Project", work_type="Data entry")

    service.delete_session(session.id)

    assert not WorkSession.objects.filter(pk=session.id).exists()


def test_owner_cannot_delete_their_own_completed_session(employee, masters):
    """Only a supervisor may remove a finished session — its hours may
    already have been reviewed."""
    service = WorkSessionService(actor=employee)
    session = service.start_session(project="Test Project", work_type="Data entry")
    service.end_session(session.id)

    with pytest.raises(ConflictError):
        service.delete_session(session.id)

    assert WorkSession.objects.filter(pk=session.id).exists()


def test_supervisor_can_delete_a_completed_session(supervisor, employee, masters):
    session = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        is_started=SessionState.COMPLETED, end_time=now_ist(),
    )

    WorkSessionService(actor=supervisor).delete_session(session.id)

    assert not WorkSession.objects.filter(pk=session.id).exists()


def test_employee_cannot_delete_someone_elses_session(employee, other_employee, masters):
    session = WorkSession.objects.create(
        emp_id=other_employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
    )

    with pytest.raises(PermissionDeniedError):
        WorkSessionService(actor=employee).delete_session(session.id)


def test_deleting_a_nonexistent_session_is_a_404(employee):
    with pytest.raises(NotFoundError):
        WorkSessionService(actor=employee).delete_session(999999)


def test_deleting_a_session_over_http(as_employee, employee, masters):
    session = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
    )

    response = as_employee.delete(f"/api/v1/tracking/sessions/{session.id}/")

    assert response.status_code == 200
    assert not WorkSession.objects.filter(pk=session.id).exists()


# ── ending a session: validation ─────────────────────────────

def test_ending_an_already_ended_session_is_not_found(employee, masters):
    """_locked_open_session filters end_time__isnull=True, so a second `end`
    call finds nothing rather than double-billing the session."""
    service = WorkSessionService(actor=employee)
    session = service.start_session(project="Test Project", work_type="Data entry")
    service.end_session(session.id)

    with pytest.raises(NotFoundError):
        service.end_session(session.id)


def test_resuming_a_session_that_is_not_paused_is_a_conflict(employee, masters):
    service = WorkSessionService(actor=employee)
    session = service.start_session(project="Test Project", work_type="Data entry")

    with pytest.raises(ConflictError):
        service.resume_session(session.id)


# ── the current/active endpoints ─────────────────────────────

def test_current_returns_null_when_nothing_is_open(as_employee):
    response = as_employee.get("/api/v1/tracking/sessions/current/")

    assert response.status_code == 200
    assert response.data["data"] is None


def test_current_returns_the_callers_own_open_session(as_employee, employee, masters):
    session = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
    )

    response = as_employee.get("/api/v1/tracking/sessions/current/")

    assert response.data["data"]["id"] == session.id


def test_current_never_returns_someone_elses_session(as_employee, other_employee, masters):
    WorkSession.objects.create(
        emp_id=other_employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
    )

    response = as_employee.get("/api/v1/tracking/sessions/current/")
    assert response.data["data"] is None


def test_active_is_the_supervisor_floor_view(as_supervisor, employee, other_employee, masters):
    WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
        is_paused=False,
    )
    WorkSession.objects.create(
        emp_id=other_employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
        is_paused=True,  # paused — not "currently working"
    )

    response = as_supervisor.get("/api/v1/tracking/sessions/active/")

    emp_ids = {row["emp_id"] for row in response.data["data"]}
    assert emp_ids == {employee.emp_id}


def test_active_is_forbidden_to_a_plain_employee(as_employee):
    response = as_employee.get("/api/v1/tracking/sessions/active/")
    assert response.status_code == 403


# ── list scoping and filters ─────────────────────────────────

def test_employee_only_sees_their_own_sessions_in_the_list(
    as_employee, employee, other_employee, masters
):
    mine = WorkSession.objects.create(emp_id=employee.emp_id, project="Test Project")
    WorkSession.objects.create(emp_id=other_employee.emp_id, project="Test Project")

    response = as_employee.get("/api/v1/tracking/sessions/")
    ids = [row["id"] for row in response.data["data"]]

    assert ids == [mine.id]


def test_supervisor_can_filter_the_list_by_emp_id(as_supervisor, employee, other_employee, masters):
    mine = WorkSession.objects.create(emp_id=employee.emp_id, project="Test Project")
    WorkSession.objects.create(emp_id=other_employee.emp_id, project="Test Project")

    response = as_supervisor.get("/api/v1/tracking/sessions/", {"emp_id": employee.emp_id})
    ids = [row["id"] for row in response.data["data"]]

    assert ids == [mine.id]


def test_open_filter_excludes_completed_sessions(as_employee, employee, masters):
    open_session = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
    )
    WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        is_started=SessionState.COMPLETED, end_time=now_ist(),
    )

    response = as_employee.get("/api/v1/tracking/sessions/", {"open": "true"})
    ids = [row["id"] for row in response.data["data"]]

    assert ids == [open_session.id]


def test_date_range_filter(as_employee, employee, masters):
    old = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        start_time=now_ist() - timedelta(days=10),
    )
    recent = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", start_time=now_ist(),
    )

    response = as_employee.get(
        "/api/v1/tracking/sessions/", {"from": str(today_ist() - timedelta(days=1))}
    )
    ids = {row["id"] for row in response.data["data"]}

    assert recent.id in ids
    assert old.id not in ids


def test_session_date_range_includes_both_selected_days(as_employee, employee, masters):
    first_day = today_ist() - timedelta(days=2)
    last_day = today_ist() - timedelta(days=1)
    included_start = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        start_time=start_of_day(first_day),
    )
    included_end = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        start_time=start_of_day(last_day),
    )
    excluded_before = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        start_time=start_of_day(first_day) - timedelta(microseconds=1),
    )
    excluded_after = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        start_time=start_of_day(last_day + timedelta(days=1)),
    )

    response = as_employee.get(
        "/api/v1/tracking/sessions/",
        {"from": first_day.isoformat(), "to": last_day.isoformat()},
    )

    assert response.status_code == 200
    rows = response.data["data"]
    assert {row["id"] for row in rows} == {included_start.id, included_end.id}
    assert excluded_before.id not in {row["id"] for row in rows}
    assert excluded_after.id not in {row["id"] for row in rows}


@pytest.mark.parametrize(
    "params",
    [
        {"from": "not-a-date", "to": "2026-10-23"},
        {"from": "2026-10-23", "to": "2026-10-22"},
    ],
)
@pytest.mark.parametrize(
    "endpoint",
    ["/api/v1/tracking/sessions/", "/api/v1/allocations/indexing/"],
)
def test_report_source_endpoints_reject_invalid_date_ranges(
    as_employee, endpoint, params
):
    response = as_employee.get(endpoint, params)

    assert response.status_code == 400
    assert response.data["ok"] is False


def test_software_shift_date_range_includes_both_selected_days(api, employee):
    from apps.accounts.models import Employee, Role, User
    from tests.conftest import PASSWORD

    first_day = today_ist() - timedelta(days=2)
    last_day = today_ist() - timedelta(days=1)
    included_start = SoftwareShift.objects.create(
        emp_id=employee.emp_id, date=first_day, start_time=start_of_day(first_day),
    )
    included_end = SoftwareShift.objects.create(
        emp_id=employee.emp_id, date=last_day, start_time=start_of_day(last_day),
    )
    SoftwareShift.objects.create(
        emp_id=employee.emp_id, date=first_day - timedelta(days=1),
        start_time=start_of_day(first_day - timedelta(days=1)),
    )
    SoftwareShift.objects.create(
        emp_id=employee.emp_id, date=last_day + timedelta(days=1),
        start_time=start_of_day(last_day + timedelta(days=1)),
    )
    admin_employee = Employee.objects.create(
        employee_id="REPORT-SUPER", name="Report Super Admin", role=Role.SUPER_ADMIN,
    )
    admin = User.objects.create_user(
        emp_id=admin_employee.employee_id, name=admin_employee.name, password=PASSWORD,
    )
    api.force_authenticate(user=admin)

    response = api.get(
        "/api/v1/tracking/software-shifts/",
        {"from": first_day.isoformat(), "to": last_day.isoformat()},
    )

    assert response.status_code == 200
    rows = response.data["data"]
    assert {row["id"] for row in rows} == {
        f"softshift_{included_start.id}",
        f"softshift_{included_end.id}",
    }


# ── the read serializer's derived fields ─────────────────────

def test_serializer_reports_a_human_readable_state(as_employee, employee, masters):
    WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", is_started=SessionState.ALLOCATED,
    )

    response = as_employee.get("/api/v1/tracking/sessions/")
    assert response.data["data"][0]["state"] == "allocated"


def test_live_elapsed_seconds_freezes_while_paused(employee, masters):
    session = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        start_time=now_ist() - timedelta(minutes=10),
        is_started=SessionState.RUNNING, is_paused=True,
        paused_at=now_ist() - timedelta(minutes=2),
    )

    first = session.live_elapsed_seconds
    # Even "later", a paused session's elapsed time must not keep climbing.
    second = session.live_elapsed_seconds
    assert first == second
    assert 470 < first < 490  # ~8 minutes of real work before the pause


def test_only_a_supervisor_can_set_a_target(employee):
    with pytest.raises(PermissionDeniedError):
        TargetService(actor=employee).set_target(
            emp_id=employee.emp_id, target_date=today_ist(), target_units=10
        )


def test_a_negative_target_is_rejected(supervisor, employee):
    with pytest.raises(ValidationError):
        TargetService(actor=supervisor).set_target(
            emp_id=employee.emp_id, target_date=today_ist(), target_units=-5
        )


def test_setting_a_target_twice_for_the_same_day_updates_it(supervisor, employee):
    service = TargetService(actor=supervisor)
    service.set_target(emp_id=employee.emp_id, target_date=today_ist(), target_units=10)
    updated = service.set_target(emp_id=employee.emp_id, target_date=today_ist(), target_units=150)

    assert Target.objects.filter(emp_id=employee.emp_id, target_date=today_ist()).count() == 1
    assert updated.target_units == 150


def test_target_create_over_http_requires_a_supervisor(as_employee, employee):
    response = as_employee.post(
        "/api/v1/tracking/targets/",
        {"emp_id": employee.emp_id, "target_date": str(today_ist()), "target_units": 50},
    )
    assert response.status_code == 403


def test_ending_a_session_rolls_up_into_todays_target(supervisor, employee, masters):
    TargetService(actor=supervisor).set_target(
        emp_id=employee.emp_id, project="Test Project", target_date=today_ist(), target_units=20
    )

    service = WorkSessionService(actor=employee)
    session = service.start_session(project="Test Project", work_type="Data entry")
    service.end_session(session.id)

    target = Target.objects.get(emp_id=employee.emp_id, project="Test Project", target_date=today_ist())
    assert target.achieved_units == 1
    assert target.is_met is False


def test_hitting_the_target_notifies_the_employee(
    django_capture_on_commit_callbacks, supervisor, employee, masters
):
    """The notification fires from transaction.on_commit(), which the plain
    `db` fixture never executes — its transaction is rolled back, not
    committed. django_capture_on_commit_callbacks is what actually runs the
    deferred callback, the same way a real request/response cycle would."""
    from apps.notifications.models import Notification

    TargetService(actor=supervisor).set_target(
        emp_id=employee.emp_id, project="Test Project", target_date=today_ist(), target_units=1
    )

    service = WorkSessionService(actor=employee)
    session = service.start_session(project="Test Project", work_type="Data entry")

    with django_capture_on_commit_callbacks(execute=True):
        service.end_session(session.id)

    assert Notification.objects.filter(
        recipient_emp_id=employee.emp_id, notif_type="work.target_met"
    ).exists()


def test_target_completion_percent_is_capped(employee):
    target = Target.objects.create(
        emp_id=employee.emp_id, target_date=today_ist(), target_units=1, achieved_units=100,
    )
    assert target.completion_percent <= 999


def test_target_without_units_has_zero_completion(employee):
    target = Target.objects.create(emp_id=employee.emp_id, target_date=today_ist(), target_units=0)
    assert target.completion_percent == 0.0
    assert target.is_met is False


# ── the dashboard summary endpoint ───────────────────────────

def test_dashboard_summary_shape(as_employee, employee, masters):
    response = as_employee.get("/api/v1/tracking/summary/")

    assert response.status_code == 200
    body = response.data["data"]
    assert set(body) == {
        "emp_id", "open_session", "today_sessions",
        "today_seconds", "target", "on_break",
    }


def test_dashboard_summary_totals_only_todays_completed_sessions(as_employee, employee, masters):
    WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project",
        total_time=100, is_started=SessionState.COMPLETED, end_time=now_ist(),
    )
    WorkSession.objects.create(  # yesterday — must not be counted
        emp_id=employee.emp_id, project="Test Project",
        total_time=999, is_started=SessionState.COMPLETED, end_time=now_ist(),
        start_time=now_ist() - timedelta(days=1),
    )

    response = as_employee.get("/api/v1/tracking/summary/")
    body = response.data["data"]

    assert body["today_sessions"] == 1
def test_dashboard_summary_reports_on_break(as_employee, employee):
    from apps.breaks.services import BreakService

    BreakService(actor=employee).start_break("Tea break 1")

    response = as_employee.get("/api/v1/tracking/summary/")
    assert response.data["data"]["on_break"] is True


def test_supervisor_can_view_someone_elses_dashboard(as_supervisor, employee):
    response = as_supervisor.get("/api/v1/tracking/summary/", {"emp_id": employee.emp_id})
    assert response.status_code == 200
    assert response.data["data"]["emp_id"] == employee.emp_id


# ── remaining list filters ────────────────────────────────────

def test_session_project_filter(as_employee, employee, masters):
    mine = WorkSession.objects.create(emp_id=employee.emp_id, project="Alpha")
    WorkSession.objects.create(emp_id=employee.emp_id, project="Beta")

    response = as_employee.get("/api/v1/tracking/sessions/", {"project": "Alpha"})
    ids = [row["id"] for row in response.data["data"]]
    assert ids == [mine.id]


def test_session_today_filter(as_employee, employee, masters):
    today = WorkSession.objects.create(emp_id=employee.emp_id, project="P")
    old = WorkSession.objects.create(
        emp_id=employee.emp_id, project="P", start_time=now_ist() - timedelta(days=5),
    )

    response = as_employee.get("/api/v1/tracking/sessions/", {"today": "true"})
    ids = {row["id"] for row in response.data["data"]}
    assert today.id in ids
    assert old.id not in ids


def test_session_date_to_filter(as_employee, employee, masters):
    recent = WorkSession.objects.create(emp_id=employee.emp_id, project="P")
    future_dated = WorkSession.objects.create(
        emp_id=employee.emp_id, project="P", start_time=now_ist() + timedelta(days=5),
    )

    response = as_employee.get(
        "/api/v1/tracking/sessions/", {"to": str(today_ist())}
    )
    ids = {row["id"] for row in response.data["data"]}
    assert recent.id in ids
    assert future_dated.id not in ids


def test_target_emp_id_filter(as_supervisor, employee, other_employee):
    mine = Target.objects.create(emp_id=employee.emp_id, target_date=today_ist(), target_units=1)
    Target.objects.create(emp_id=other_employee.emp_id, target_date=today_ist(), target_units=1)

    response = as_supervisor.get("/api/v1/tracking/targets/", {"emp_id": employee.emp_id})
    ids = [row["id"] for row in response.data["data"]]
    assert ids == [mine.id]


def test_target_today_filter(as_employee, employee):
    from datetime import timedelta as td

    today_target = Target.objects.create(
        emp_id=employee.emp_id, target_date=today_ist(), target_units=1
    )
    Target.objects.create(
        emp_id=employee.emp_id, target_date=today_ist() - td(days=1), target_units=1
    )

    response = as_employee.get("/api/v1/tracking/targets/", {"today": "true"})
    ids = [row["id"] for row in response.data["data"]]
    assert ids == [today_target.id]


# ── the HTTP surface of pause/resume/end/target-create ────────

def test_pause_and_resume_over_http(as_employee, employee, masters):
    session = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
    )

    paused = as_employee.post(f"/api/v1/tracking/sessions/{session.id}/pause/")
    assert paused.status_code == 200
    assert paused.data["data"]["is_paused"] is True

    resumed = as_employee.post(f"/api/v1/tracking/sessions/{session.id}/resume/")
    assert resumed.status_code == 200
    assert resumed.data["data"]["is_paused"] is False


def test_end_over_http(as_employee, employee, masters):
    session = WorkSession.objects.create(
        emp_id=employee.emp_id, project="Test Project", is_started=SessionState.RUNNING,
    )
    response = as_employee.post(
        f"/api/v1/tracking/sessions/{session.id}/end/", {}
    )
    assert response.status_code == 200
    assert response.data["data"]["state"] == "completed"


def test_target_create_over_http_succeeds_for_a_supervisor(as_supervisor, employee):
    response = as_supervisor.post(
        "/api/v1/tracking/targets/",
        {"emp_id": employee.emp_id, "target_date": str(today_ist()), "target_units": 100},
    )
    assert response.status_code == 201
    assert response.data["data"]["target_units"] == 100


# ── model plumbing ─────────────────────────────────────────────

def test_work_session_str(employee, masters):
    session = WorkSession.objects.create(emp_id=employee.emp_id, project="P", work_type="WT")
    assert employee.emp_id in str(session)
    assert "WT" in str(session)


def test_target_str(employee):
    target = Target.objects.create(
        emp_id=employee.emp_id, target_date=today_ist(), target_units=1, achieved_units=4,
    )
    assert "4/1" in str(target)


def test_work_session_between_queryset(employee, masters):
    in_range = WorkSession.objects.create(emp_id=employee.emp_id, project="P")
    out_of_range = WorkSession.objects.create(
        emp_id=employee.emp_id, project="P", start_time=now_ist() - timedelta(days=10),
    )

    results = WorkSession.objects.between(now_ist() - timedelta(days=1), now_ist() + timedelta(days=1))
    ids = {r.id for r in results}
    assert in_range.id in ids
    assert out_of_range.id not in ids
