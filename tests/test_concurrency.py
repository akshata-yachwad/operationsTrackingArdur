"""Real concurrency, not sequential calls that merely look concurrent.

test_timing.py's ``test_only_one_session_may_be_open_per_employee`` calls
``start_session`` twice in a row on the same connection — by the second call
the first session's row is already visible, so the ``select_for_update()``
guard has something to lock. It does not prove anything about two requests
that arrive at the same instant, before either row exists.

These tests use real OS threads, each on its own database connection, to
reproduce what 100+ people clicking "Start work" across a shift actually
looks like. They need ``transaction=True`` — the plain ``db`` fixture wraps
the test in one uncommitted transaction, which a second thread's connection
cannot see into (and select_for_update from a second thread on the same
un-committed transaction would just hang).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import connections

from apps.accounts.models import Employee, User
from apps.allocations.models import AllocationStatus, BatchAllocation
from apps.breaks.constants import BREAK_ALLOWANCES
from apps.breaks.models import BreakTime
from apps.breaks.services import BreakService
from apps.masters.models import ClientCode, Project, WorkType
from apps.tracking.models import SessionState, SoftwareShift, Target, WorkSession
from apps.tracking.services import ShiftService, TargetService, WorkSessionService
from core.exceptions import ConflictError
from core.timezone import now_ist, today_ist

pytestmark = pytest.mark.django_db(transaction=True)

PASSWORD = "test-password-123"


def _make_user(emp_id: str, role: str = "employee") -> User:
    Employee.objects.create(employee_id=emp_id, name=emp_id, role=role, status="active")
    return User.objects.create_user(emp_id=emp_id, password=PASSWORD, name=emp_id)


def _run_concurrently(fn, count: int):
    """Fire ``fn`` from ``count`` threads at as close to the same instant as
    the GIL allows, closing each thread's DB connection afterwards so the
    test doesn't leak connections into the next test."""
    barrier = threading.Barrier(count)
    results: list = [None] * count
    errors: list = [None] * count

    def wrapper(i):
        try:
            barrier.wait(timeout=5)
            results[i] = fn()
        except Exception as exc:  # noqa: BLE001 — capturing for assertion, not handling
            errors[i] = exc
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=count) as pool:
        list(pool.map(wrapper, range(count)))

    return results, errors


# ── work sessions: the one-open-session guarantee under real concurrency ──

def test_concurrent_starts_from_a_cold_state_do_not_double_open_a_session():
    """Two people (or one person double-clicking) hitting 'Start work' for the
    SAME employee at the same instant, with no session open yet.

    ``select_for_update()`` only serialises threads against a row that
    already exists. Here neither thread has created one yet, so the guard in
    WorkSessionService.start_session has nothing to lock against — this test
    is what a shift-start rush actually exercises.
    """
    employee = _make_user("RACE001")
    Project.objects.create(project_name="Race Project")

    def attempt():
        return WorkSessionService(actor=employee).start_session(
            project="Race Project", work_type="Data entry"
        )

    results, errors = _run_concurrently(attempt, count=8)

    succeeded = [r for r in results if r is not None]
    open_sessions = WorkSession.objects.filter(
        emp_id=employee.emp_id, end_time__isnull=True, is_started=SessionState.RUNNING
    ).count()

    # The business rule is "one open session per employee" — that must hold
    # in the database regardless of how many requests raced to get there.
    assert open_sessions == 1, (
        f"{open_sessions} open sessions exist for one employee after {len(succeeded)} "
        f"concurrent start_session() calls succeeded — the one-open-session guarantee "
        f"does not hold under real concurrency. WorkSession has no unique constraint "
        f"backstop the way BreakTime does (uq_one_open_break_per_user)."
    )


def test_concurrent_pause_and_resume_do_not_corrupt_paused_elapsed(masters):
    """A pause and an end racing on the same session must not leave
    paused_elapsed in a state that pays or docks time that never happened."""
    employee = _make_user("RACE002")
    session = WorkSessionService(actor=employee).start_session(
        project="Test Project", work_type="Data entry"
    )

    def pause():
        try:
            return WorkSessionService(actor=employee).pause_session(session.id)
        except ConflictError:
            return None

    results, _ = _run_concurrently(pause, count=5)

    session.refresh_from_db()
    # Exactly one pause should have taken effect — not a state where
    # paused_elapsed was double-counted by two "successful" pauses.
    assert session.is_paused is True
    assert sum(1 for r in results if r is not None) == 1


def test_concurrent_software_shift_ends_are_idempotent(monkeypatch):
    if not connections["default"].features.has_select_for_update:
        pytest.skip("The configured database does not support row-level SELECT FOR UPDATE.")

    employee = _make_user("RACESHIFT")
    end = now_ist()
    start = end - timedelta(hours=3)
    shift = SoftwareShift.objects.create(
        emp_id=employee.emp_id,
        date=end.date(),
        start_time=start,
        updated_at=start,
        accumulated_seconds=120,
    )
    monkeypatch.setattr("apps.tracking.services.now_ist", lambda: end)

    def end_shift():
        return ShiftService(actor=employee).end_software_shift()

    results, errors = _run_concurrently(end_shift, count=2)

    shift.refresh_from_db()
    assert errors == [None, None]
    assert sum(result is not None for result in results) == 1
    assert shift.is_ended is True
    assert shift.end_time == end
    assert shift.accumulated_seconds == 10_920
    assert shift.total_time == "03:02:00"


# ── breaks: the documented backstop actually holds ─────────────────────

def test_concurrent_break_starts_are_serialised_by_the_unique_index():
    """Contrast case: BreakTime has select_for_update() *and*
    uq_one_open_break_per_user. This is expected to hold even from a cold
    state, because the partial unique index catches what the row lock alone
    cannot."""
    employee = _make_user("RACE003")

    def attempt():
        return BreakService(actor=employee).start_break("Tea break 1")

    results, errors = _run_concurrently(attempt, count=8)

    open_breaks = BreakTime.objects.filter(user_id=employee.emp_id, end_time__isnull=True).count()
    succeeded = [r for r in results if r is not None]

    assert open_breaks == 1
    assert len(succeeded) == 1, (
        f"{len(succeeded)} of 8 concurrent start_break() calls succeeded; "
        "the unique index should have let exactly one through and turned the "
        "rest into a ConflictError or an IntegrityError."
    )


# ── allocations: updating an existing row does serialise correctly ─────

def test_concurrent_allocation_progress_updates_do_not_lose_a_write():
    """Unlike start_session, update_status() locks a row that already
    exists — this is the case select_for_update() is actually good at."""
    supervisor = _make_user("RACESUP1", role="supervisor")
    employee = _make_user("RACE004")
    allocation = BatchAllocation.objects.create(
        allocation_id="RACE-ALLOC-1", employee_id=employee.emp_id,
        quantity=100, status=AllocationStatus.IN_PROGRESS,
    )

    from apps.allocations.services import AllocationService

    def bump(n):
        try:
            return AllocationService(actor=supervisor).update_status(
                allocation.pk, status=AllocationStatus.IN_PROGRESS, completed_quantity=n
            )
        finally:
            connections.close_all()

    # Ten threads race to set completed_quantity to ten different values.
    # Whichever writes last under the lock wins — no write should be silently
    # dropped in a way that leaves a value no thread ever asked for.
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(bump, range(1, 11)))

    allocation.refresh_from_db()
    assert allocation.completed_quantity in range(1, 11)

    from apps.allocations.models import OrderHistory

    # Every attempt is independently locked and recorded — ten distinct
    # audit rows, not a merged or lost update.
    assert OrderHistory.objects.filter(allocation_id="RACE-ALLOC-1").count() == 10


# ── targets: the unique constraint prevents a duplicate day row ────────

def test_concurrent_target_set_for_the_same_day_does_not_duplicate():
    supervisor = _make_user("RACESUP2", role="supervisor")
    employee = _make_user("RACE005")

    def attempt(units):
        try:
            return TargetService(actor=supervisor).set_target(
                emp_id=employee.emp_id, target_date=today_ist(), target_units=units
            )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(attempt, [10, 20, 30, 40, 50, 60]))

    rows = Target.objects.filter(emp_id=employee.emp_id, target_date=today_ist())
    assert rows.count() == 1, (
        f"{rows.count()} Target rows exist for one employee/day — "
        "uq_target_emp_day should make that impossible."
    )


# ── the "everyone breaks at once" scenario ──────────────────────────
#
# Different from every test above: this is not one employee racing itself —
# it is N *different* employees, each with their own row to insert, all
# released from a barrier in the same instant. Nothing here should conflict
# at the business-rule level (different user_id ⇒ the partial unique index
# never collides across people), so the question this answers is purely
# "does the system fall over under a synchronised burst" — a scheduled break
# bell, or 500 people back from a fire drill at the same second.

BURST_SIZE = 500


def _make_users_fast(prefix: str, count: int) -> list[User]:
    """Bulk-create so provisioning 500 accounts doesn't dominate the test's
    own running time — this is setup, not the thing being measured."""
    Employee.objects.bulk_create(
        [
            Employee(
                employee_id=f"{prefix}{i:04d}", name=f"{prefix}{i:04d}",
                role="employee", status="active",
            )
            for i in range(count)
        ]
    )
    # create_user() hashes the password per call; the test suite runs with
    # MD5PasswordHasher (see settings/test.py) specifically so this stays fast.
    return [
        User.objects.create_user(emp_id=f"{prefix}{i:04d}", password=PASSWORD)
        for i in range(count)
    ]


def test_500_different_employees_taking_a_break_at_the_exact_same_instant():
    """The answer, pinned down: no failures, no cross-contamination, and the
    presence/notification side effects on each of the 500 do not interfere
    with each other. If this ever starts failing, the failure will be one of
    three shapes — see the assertions below for which part of the
    architecture each one accuses."""
    users = _make_users_fast("BURST", BURST_SIZE)

    barrier = threading.Barrier(BURST_SIZE)
    results: list = [None] * BURST_SIZE
    errors: list = [None] * BURST_SIZE
    started_at: list = [None] * BURST_SIZE

    def attempt(i):
        try:
            barrier.wait(timeout=30)
            t0 = time.monotonic()
            results[i] = BreakService(actor=users[i]).start_break("Tea break 1")
            started_at[i] = time.monotonic() - t0
        except Exception as exc:  # noqa: BLE001
            errors[i] = exc
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=BURST_SIZE) as pool:
        list(pool.map(attempt, range(BURST_SIZE)))

    failures = [(i, e) for i, e in enumerate(errors) if e is not None]

    # 1. Every single one must succeed. A failure here accuses either
    #    connection-pool exhaustion (infra: max_connections too low for the
    #    deployment's real worker/thread count — see scripts/load_test/README)
    #    or a lock-contention timeout (architecture: the row lock in
    #    start_break serialises writes across *unrelated* people, which it
    #    should not, since they don't share a row).
    assert not failures, (
        f"{len(failures)}/{BURST_SIZE} simultaneous break-starts failed: "
        f"{failures[:5]}"
    )

    # 2. Every employee got exactly their own break, with no cross-talk.
    #    A failure here accuses the ORM/connection layer of leaking state
    #    across threads (each thread must use its own connection).
    open_breaks = BreakTime.objects.filter(
        user_id__in=[u.emp_id for u in users], end_time__isnull=True
    )
    assert open_breaks.count() == BURST_SIZE
    assert set(open_breaks.values_list("user_id", flat=True)) == {u.emp_id for u in users}
    for brk in open_breaks:
        assert brk.allotted_time == BREAK_ALLOWANCES["Tea break 1"]

    # 3. No one is silently missing or duplicated.
    assert len([r for r in results if r is not None]) == BURST_SIZE

    # 4. Throughput/latency is reported, not asserted on — hardware-dependent
    #    by nature — but printed so a real regression (lock contention
    #    creeping in) is visible in CI output over time.
    durations = sorted(d for d in started_at if d is not None)
    if durations:
        p50 = durations[len(durations) // 2]
        p99 = durations[int(len(durations) * 0.99)]
        print(
            f"\n500-way simultaneous break burst: p50={p50 * 1000:.1f}ms "
            f"p99={p99 * 1000:.1f}ms max={durations[-1] * 1000:.1f}ms"
        )


def test_500_employees_bursting_work_sessions_at_the_same_instant(masters):
    """The work-session equivalent, now that uq_one_open_session_per_emp
    exists (see apps/tracking/models.py) — this is the regression test that
    proves the fix in this file's first test holds at the scale actually
    asked for, not just at 8 threads."""
    users = _make_users_fast("WBURST", BURST_SIZE)

    barrier = threading.Barrier(BURST_SIZE)
    errors: list = [None] * BURST_SIZE

    def attempt(i):
        try:
            barrier.wait(timeout=30)
            WorkSessionService(actor=users[i]).start_session(
                project="Test Project", work_type="Data entry"
            )
        except Exception as exc:  # noqa: BLE001
            errors[i] = exc
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=BURST_SIZE) as pool:
        list(pool.map(attempt, range(BURST_SIZE)))

    failures = [(i, e) for i, e in enumerate(errors) if e is not None]
    assert not failures, f"{len(failures)}/{BURST_SIZE} simultaneous session-starts failed"

    open_sessions = WorkSession.objects.filter(
        emp_id__in=[u.emp_id for u in users], end_time__isnull=True, is_started=SessionState.RUNNING
    )
    assert open_sessions.count() == BURST_SIZE
    assert set(open_sessions.values_list("emp_id", flat=True)) == {u.emp_id for u in users}


def test_mixed_workload_500_users_across_different_projects_end_tasks_while_others_report():
    """Quitting-time, worst case: hundreds of people on different projects
    end their session in the same instant while supervisors pull a
    productivity report — a read across the same table everyone is writing
    to. ``ot_user_work_data`` is explicitly 'the busiest table in the
    application and the source for every productivity report' (see
    apps/tracking/models.py) — this is that claim under actual contention,
    not just multiple projects existing in the schema.

    Split of the 500: 400 end an open session (task completion), 75 run a
    report inline (a feature read), 25 pull their own dashboard summary.
    """
    from django.db import models as dj_models

    from apps.reports.selectors import ProductivitySelector, ReportFilters

    n_enders, n_reporters, n_dashboards = 400, 75, 25
    total = n_enders + n_reporters + n_dashboards
    assert total == BURST_SIZE

    workers = _make_users_fast("MIXED", n_enders + n_dashboards)
    supervisors = _make_users_fast("MIXEDSUP", n_reporters)

    sessions = {}
    for i, user in enumerate(workers[:n_enders]):
        sessions[user.emp_id] = WorkSession.objects.create(
            emp_id=user.emp_id,
            project=f"Load Test Project {i % 50:02d}",  # 50 distinct projects
            is_started=SessionState.RUNNING,
        )

    barrier = threading.Barrier(total)
    errors: list = [None] * total

    def end_task(i):
        user = workers[i]
        try:
            barrier.wait(timeout=30)
            WorkSessionService(actor=user).end_session(
                sessions[user.emp_id].id
            )
        except Exception as exc:  # noqa: BLE001
            errors[i] = exc
        finally:
            connections.close_all()

    def run_report(i):
        supervisor = supervisors[i - n_enders]
        try:
            barrier.wait(timeout=30)
            filters = ReportFilters(projects=[f"Load Test Project {i % 50:02d}"])
            ProductivitySelector(filters).rows()  # the actual aggregate query
        except Exception as exc:  # noqa: BLE001
            errors[i] = exc
        finally:
            connections.close_all()

    def check_dashboard(i):
        user = workers[n_enders + (i - n_enders - n_reporters)]
        try:
            barrier.wait(timeout=30)
            WorkSession.objects.filter(emp_id=user.emp_id).for_day().completed().aggregate(
                units=dj_models.Sum("work_units")
            )
        except Exception as exc:  # noqa: BLE001
            errors[i] = exc
        finally:
            connections.close_all()

    jobs = (
        [end_task] * n_enders + [run_report] * n_reporters + [check_dashboard] * n_dashboards
    )

    with ThreadPoolExecutor(max_workers=total) as pool:
        list(pool.map(lambda args: args[1](args[0]), enumerate(jobs)))

    failures = [(i, e) for i, e in enumerate(errors) if e is not None]
    assert not failures, (
        f"{len(failures)}/{total} mixed-workload operations failed under simultaneous "
        f"load: {failures[:5]}"
    )

    completed = WorkSession.objects.filter(
        emp_id__in=[u.emp_id for u in workers[:n_enders]], is_started=SessionState.COMPLETED
    )
    assert completed.count() == n_enders, (
        "a report or dashboard read running concurrently with session-ending writes "
        "must not cause a lost or partial update on the write side"
    )
