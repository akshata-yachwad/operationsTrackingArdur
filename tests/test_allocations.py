"""Batch allocations ("orders"): assignment, progress, reassignment, history.

Found via a 140-concurrent-user load test: every detail action on
AllocationViewSet (status, reassign, cancel, history) 500'd on every single
call — 100% reproducible, not a race — because ``lookup_field =
"allocation_id"`` means the router passes that URL kwarg name, and the view
methods all declared ``pk=None``. DRF raises a TypeError before the view body
ever runs, so a single manual click through the UI would have caught it —
there was simply no test that ever POSTed to one of these URLs.
"""

from __future__ import annotations

import pytest

from apps.allocations.models import AllocationStatus, BatchAllocation, OrderHistory

pytestmark = pytest.mark.django_db


@pytest.fixture
def allocation(employee, supervisor) -> BatchAllocation:
    return BatchAllocation.objects.create(
        allocation_id="ALLOC-TEST-1", employee_id=employee.emp_id,
        employee_name=employee.name, project="Test Project", quantity=100,
        status=AllocationStatus.PENDING, allocated_by=supervisor.emp_id,
    )


# ── the bug: every detail action used the wrong URL kwarg ───────────

def test_set_status_over_http_does_not_500(as_employee, allocation):
    """This is the regression test for the load-test-discovered bug."""
    response = as_employee.post(
        f"/api/v1/allocations/{allocation.allocation_id}/status/",
        {"status": "in_progress"},
    )

    assert response.status_code == 200
    assert response.data["data"]["status"] == "in_progress"


def test_reassign_over_http_does_not_500(as_supervisor, allocation, other_employee):
    response = as_supervisor.post(
        f"/api/v1/allocations/{allocation.allocation_id}/reassign/",
        {"employee_id": other_employee.emp_id},
    )

    assert response.status_code == 200
    assert response.data["data"]["employee_id"] == other_employee.emp_id


def test_cancel_over_http_does_not_500(as_supervisor, allocation):
    response = as_supervisor.post(
        f"/api/v1/allocations/{allocation.allocation_id}/cancel/", {"reason": "Duplicate order"}
    )

    assert response.status_code == 200
    assert response.data["data"]["status"] == "cancelled"


def test_history_over_http_does_not_500(as_employee, allocation, supervisor):
    from apps.allocations.services import AllocationService

    AllocationService(actor=supervisor).update_status(allocation.pk, status="in_progress")

    response = as_employee.get(f"/api/v1/allocations/{allocation.allocation_id}/history/")

    assert response.status_code == 200
    actions = [row["action"] for row in response.data["data"]]
    assert "status_in_progress" in actions


def test_all_four_detail_actions_use_the_lookup_field_kwarg():
    """Structural guard: a future action added with `pk=None` reintroduces
    this exact bug. AllocationViewSet.lookup_field is 'allocation_id', so
    every @action(detail=True, ...) method must take that kwarg name."""
    import inspect

    from apps.allocations.views import AllocationViewSet

    assert AllocationViewSet.lookup_field == "allocation_id"

    detail_actions = [
        method
        for name, method in vars(AllocationViewSet).items()
        if getattr(method, "detail", None) is True
    ]
    assert detail_actions, "expected at least one @action(detail=True, ...) to check"

    for method in detail_actions:
        params = inspect.signature(method).parameters
        assert "allocation_id" in params, (
            f"{method.__name__} must accept an 'allocation_id' kwarg, not 'pk' — "
            "AllocationViewSet.lookup_field is 'allocation_id'."
        )


def test_indexing_report_applies_inclusive_date_range(as_employee, employee):
    from datetime import timedelta

    from apps.accounts.models import Employee
    from apps.allocations.models import TitleIndexingSession
    from core.timezone import day_bounds, today_ist

    date_from = today_ist() - timedelta(days=1)
    date_to = today_ist()
    Employee.objects.filter(employee_id=employee.emp_id).update(department="Ops")
    start, _ = day_bounds(date_from)
    _, end = day_bounds(date_to)
    included_start = TitleIndexingSession.objects.create(
        employee_id=employee.emp_id, client_code="C1", work_type="INDEXING",
        started_at=start,
    )
    included_end = TitleIndexingSession.objects.create(
        employee_id=employee.emp_id, client_code="C1", work_type="INDEXING",
        started_at=end - timedelta(microseconds=1),
    )
    TitleIndexingSession.objects.create(
        employee_id=employee.emp_id, client_code="C1", work_type="INDEXING",
        started_at=start - timedelta(microseconds=1),
    )
    TitleIndexingSession.objects.create(
        employee_id=employee.emp_id, client_code="C1", work_type="INDEXING",
        started_at=end,
    )

    response = as_employee.get(
        "/api/v1/allocations/indexing/",
        {"from": date_from.isoformat(), "to": date_to.isoformat()},
    )

    assert response.status_code == 200
    rows = response.data["data"]
    assert {row["id"] for row in rows} == {included_start.id, included_end.id}
    assert all(row["work_location"] == "Ops" for row in rows)


# ── the underlying business rules, over HTTP ─────────────────────────

def test_employee_can_progress_their_own_allocation(as_employee, allocation):
    response = as_employee.post(
        f"/api/v1/allocations/{allocation.allocation_id}/status/",
        {"status": "in_progress", "completed_quantity": 40},
    )
    assert response.status_code == 200
    assert response.data["data"]["completed_quantity"] == 40


def test_employee_cannot_progress_someone_elses_allocation(as_employee, other_employee, supervisor):
    other_alloc = BatchAllocation.objects.create(
        allocation_id="ALLOC-TEST-2", employee_id=other_employee.emp_id,
        quantity=50, status=AllocationStatus.PENDING, allocated_by=supervisor.emp_id,
    )

    response = as_employee.post(
        f"/api/v1/allocations/{other_alloc.allocation_id}/status/", {"status": "in_progress"}
    )
    # get_queryset() scopes to the caller's own allocations (visible_to()),
    # so someone else's allocation_id resolves to "not found" rather than
    # "found but forbidden" — the same pattern test_permissions.py uses for
    # feedback. Either code is an acceptable way to not leak the row.
    assert response.status_code in (403, 404)
    other_alloc.refresh_from_db()
    assert other_alloc.status == AllocationStatus.PENDING


def test_employee_cannot_reassign_or_cancel(as_employee, allocation, other_employee):
    assert as_employee.post(
        f"/api/v1/allocations/{allocation.allocation_id}/reassign/",
        {"employee_id": other_employee.emp_id},
    ).status_code == 403
    assert as_employee.post(
        f"/api/v1/allocations/{allocation.allocation_id}/cancel/"
    ).status_code == 403


def test_a_completed_allocation_cannot_be_reassigned(as_supervisor, allocation, other_employee):
    allocation.status = AllocationStatus.COMPLETED
    allocation.save(update_fields=["status"])

    response = as_supervisor.post(
        f"/api/v1/allocations/{allocation.allocation_id}/reassign/",
        {"employee_id": other_employee.emp_id},
    )
    assert response.status_code == 409


def test_completed_allocation_cannot_be_cancelled(as_supervisor, allocation):
    allocation.status = AllocationStatus.COMPLETED
    allocation.save(update_fields=["status"])

    response = as_supervisor.post(f"/api/v1/allocations/{allocation.allocation_id}/cancel/")
    assert response.status_code == 409


def test_creating_an_allocation_records_order_history(as_supervisor, employee):
    response = as_supervisor.post(
        "/api/v1/allocations/",
        {"allocation_id": "ALLOC-TEST-3", "employee_id": employee.emp_id, "quantity": 10},
    )
    assert response.status_code == 201

    assert OrderHistory.objects.filter(allocation_id="ALLOC-TEST-3", action="allocated").exists()


def test_mine_only_returns_the_callers_open_allocations(as_employee, employee, other_employee):
    mine = BatchAllocation.objects.create(
        allocation_id="ALLOC-MINE-1", employee_id=employee.emp_id, quantity=10,
        status=AllocationStatus.PENDING,
    )
    BatchAllocation.objects.create(
        allocation_id="ALLOC-MINE-2", employee_id=other_employee.emp_id, quantity=10,
        status=AllocationStatus.PENDING,
    )

    response = as_employee.get("/api/v1/allocations/mine/")
    ids = [row["allocation_id"] for row in response.data["data"]]

    assert ids == [mine.allocation_id]


# ── list filters ──────────────────────────────────────────────

def test_filter_by_emp_id(as_supervisor, employee, other_employee):
    mine = BatchAllocation.objects.create(
        allocation_id="F-EMP-1", employee_id=employee.emp_id, quantity=10
    )
    BatchAllocation.objects.create(
        allocation_id="F-EMP-2", employee_id=other_employee.emp_id, quantity=10
    )

    response = as_supervisor.get("/api/v1/allocations/", {"emp_id": employee.emp_id})
    ids = [row["allocation_id"] for row in response.data["data"]]
    assert ids == [mine.allocation_id]


def test_filter_by_status(as_supervisor, employee):
    BatchAllocation.objects.create(
        allocation_id="F-ST-1", employee_id=employee.emp_id, quantity=10,
        status=AllocationStatus.COMPLETED,
    )
    pending = BatchAllocation.objects.create(
        allocation_id="F-ST-2", employee_id=employee.emp_id, quantity=10,
        status=AllocationStatus.PENDING,
    )

    response = as_supervisor.get("/api/v1/allocations/", {"status": "pending"})
    ids = [row["allocation_id"] for row in response.data["data"]]
    assert ids == [pending.allocation_id]


def test_filter_by_open(as_supervisor, employee):
    open_alloc = BatchAllocation.objects.create(
        allocation_id="F-OPEN-1", employee_id=employee.emp_id, quantity=10,
        status=AllocationStatus.IN_PROGRESS,
    )
    BatchAllocation.objects.create(
        allocation_id="F-OPEN-2", employee_id=employee.emp_id, quantity=10,
        status=AllocationStatus.COMPLETED,
    )

    response = as_supervisor.get("/api/v1/allocations/", {"open": "true"})
    ids = [row["allocation_id"] for row in response.data["data"]]
    assert ids == [open_alloc.allocation_id]


def test_filter_by_overdue(as_supervisor, employee):
    from datetime import timedelta

    from core.timezone import now_ist

    overdue = BatchAllocation.objects.create(
        allocation_id="F-OD-1", employee_id=employee.emp_id, quantity=10,
        status=AllocationStatus.PENDING, due_at=now_ist() - timedelta(days=1),
    )
    BatchAllocation.objects.create(
        allocation_id="F-OD-2", employee_id=employee.emp_id, quantity=10,
        status=AllocationStatus.PENDING, due_at=now_ist() + timedelta(days=1),
    )

    response = as_supervisor.get("/api/v1/allocations/", {"overdue": "true"})
    ids = [row["allocation_id"] for row in response.data["data"]]
    assert ids == [overdue.allocation_id]


def test_filter_by_project(as_supervisor, employee):
    matching = BatchAllocation.objects.create(
        allocation_id="F-PR-1", employee_id=employee.emp_id, quantity=10, project="Alpha",
    )
    BatchAllocation.objects.create(
        allocation_id="F-PR-2", employee_id=employee.emp_id, quantity=10, project="Beta",
    )

    response = as_supervisor.get("/api/v1/allocations/", {"project": "Alpha"})
    ids = [row["allocation_id"] for row in response.data["data"]]
    assert ids == [matching.allocation_id]


# ── destroy = cancel ──────────────────────────────────────────

def test_destroy_over_http_cancels_rather_than_deletes(as_supervisor, allocation):
    response = as_supervisor.delete(f"/api/v1/allocations/{allocation.allocation_id}/")
    assert response.status_code in (200, 204)

    allocation.refresh_from_db()
    assert allocation.status == AllocationStatus.CANCELLED
    assert BatchAllocation.objects.filter(pk=allocation.pk).exists()  # not hard-deleted


# ── OrderHistoryViewSet ───────────────────────────────────────

def test_order_history_endpoint_requires_a_supervisor(as_employee):
    assert as_employee.get("/api/v1/allocations/history/").status_code == 403


def test_order_history_endpoint_filters_by_allocation_and_emp_id(as_supervisor, allocation, employee):
    from apps.allocations.models import OrderHistory

    OrderHistory.objects.create(
        allocation_id=allocation.allocation_id, employee_id=employee.emp_id, action="allocated",
    )
    OrderHistory.objects.create(
        allocation_id="SOME-OTHER-ALLOC", employee_id="OTHERPERSON", action="allocated",
    )

    response = as_supervisor.get(
        "/api/v1/allocations/history/", {"allocation_id": allocation.allocation_id}
    )
    assert len(response.data["data"]) == 1

    response2 = as_supervisor.get("/api/v1/allocations/history/", {"emp_id": employee.emp_id})
    assert len(response2.data["data"]) == 1


# ── OrderRateViewSet ──────────────────────────────────────────

def test_order_rates_list_and_filters(as_employee):
    from apps.allocations.models import OrderRate

    OrderRate.objects.create(order_type="Full Search", state="TX", county="Travis")
    OrderRate.objects.create(order_type="Full Search", state="CA", county="Orange")

    response = as_employee.get("/api/v1/allocations/rates/", {"order_type": "Full Search", "state": "TX"})
    assert len(response.data["data"]) == 1

    response2 = as_employee.get("/api/v1/allocations/rates/", {"county": "Orange"})
    assert len(response2.data["data"]) == 1


def test_order_types_endpoint_falls_back_to_a_default_list_when_empty(as_employee):
    response = as_employee.get("/api/v1/allocations/rates/order_types/")
    assert "Full Search" in response.data["data"]


def test_order_types_endpoint_returns_distinct_real_values(as_employee):
    from apps.allocations.models import OrderRate

    OrderRate.objects.create(order_type="Custom Type", state="TX", county="Travis")
    OrderRate.objects.create(order_type="Custom Type", state="CA", county="Orange")

    response = as_employee.get("/api/v1/allocations/rates/order_types/")
    assert response.data["data"] == ["Custom Type"]


def test_states_endpoint(as_employee):
    from apps.allocations.models import OrderRate

    OrderRate.objects.create(order_type="Full Search", state="TX", county="Travis")

    response = as_employee.get("/api/v1/allocations/rates/states/Full Search/")
    assert response.data["data"] == ["TX"]


def test_counties_endpoint(as_employee):
    from apps.allocations.models import OrderRate

    OrderRate.objects.create(order_type="Full Search", state="TX", county="Travis")

    response = as_employee.get("/api/v1/allocations/rates/counties/Full Search/TX/")
    assert response.data["data"] == ["Travis"]


# ── model plumbing ─────────────────────────────────────────────

def test_allocation_str_and_progress_percent():
    alloc = BatchAllocation.objects.create(
        allocation_id="A-STR", employee_id="E1", quantity=100, completed_quantity=40,
    )
    assert "A-STR" in str(alloc)
    assert alloc.progress_percent == 40.0


def test_allocation_progress_percent_zero_quantity():
    alloc = BatchAllocation.objects.create(allocation_id="A-ZERO", employee_id="E1", quantity=0)
    assert alloc.progress_percent == 0.0


def test_allocation_pending_and_due_within_querysets():
    from datetime import timedelta

    from core.timezone import now_ist

    BatchAllocation.objects.create(
        allocation_id="A-PEND", employee_id="E1", quantity=10, status=AllocationStatus.PENDING,
    )
    due_soon = BatchAllocation.objects.create(
        allocation_id="A-DUE", employee_id="E1", quantity=10, status=AllocationStatus.PENDING,
        due_at=now_ist() + timedelta(hours=2),
    )

    assert "A-PEND" in [a.allocation_id for a in BatchAllocation.objects.pending()]
    assert due_soon in BatchAllocation.objects.due_within(hours=4)


def test_order_history_and_order_rate_str():
    from apps.allocations.models import OrderHistory, OrderRate

    history = OrderHistory.objects.create(allocation_id="A-1", action="allocated")
    rate = OrderRate.objects.create(order_type="Full Search", state="TX", county="Travis")

    assert "A-1" in str(history)
    assert "Full Search" in str(rate)
