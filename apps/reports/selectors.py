"""Read-only query objects.

Selectors own reads; services own writes. Keeping them apart means a report
can be optimised, cached or moved to a replica without anyone worrying about
what it might mutate — because it provably mutates nothing.

Each selector returns a list of plain dicts, so exporters and API responses
consume the same shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db.models import Avg, Count, Q, Sum, Subquery, OuterRef

from apps.allocations.models import BatchAllocation
from apps.breaks.models import BreakTime
from apps.feedback.models import Feedback
from apps.tracking.models import SessionState, WorkSession
from core.timezone import day_bounds, today_ist, now_ist
from apps.accounts.models import Employee


@dataclass
class ReportFilters:
    """Every report takes the same filter shape."""

    date_from: date | None = None
    date_to: date | None = None
    emp_ids: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    work_types: list[str] = field(default_factory=list)

    @classmethod
    def from_params(cls, params: dict) -> ReportFilters:
        def as_list(value):
            if not value:
                return []
            return value if isinstance(value, list) else [v for v in str(value).split(",") if v]

        return cls(
            date_from=params.get("date_from") or None,
            date_to=params.get("date_to") or None,
            emp_ids=as_list(params.get("emp_ids") or params.get("emp_id")),
            projects=as_list(params.get("projects") or params.get("project")),
            work_types=as_list(params.get("work_types") or params.get("work_type")),
        )

    def scoped_to(self, user) -> ReportFilters:
        """Force an employee's own id onto the filter.

        A report endpoint that an employee can call must not be able to return
        another employee's rows just because the emp_ids parameter was omitted.
        """
        if user and not user.is_supervisor:
            self.emp_ids = [user.emp_id]
        return self


class BaseSelector:
    """Applies the shared filters, so each report only writes its own logic."""

    date_field = "start_time"
    emp_field = "emp_id"
    project_field = "project"
    work_type_field = "work_type"

    def __init__(self, filters: ReportFilters):
        self.filters = filters

    def base_queryset(self, queryset):
        f = self.filters

        if f.date_from:
            start, _ = day_bounds(f.date_from)
            queryset = queryset.filter(**{f"{self.date_field}__gte": start})
        if f.date_to:
            _, end = day_bounds(f.date_to)
            queryset = queryset.filter(**{f"{self.date_field}__lt": end})
        if f.emp_ids:
            queryset = queryset.filter(**{f"{self.emp_field}__in": f.emp_ids})
        if f.projects and self.project_field:
            queryset = queryset.filter(**{f"{self.project_field}__in": f.projects})
        if f.work_types and self.work_type_field:
            queryset = queryset.filter(**{f"{self.work_type_field}__in": f.work_types})

        return queryset


class ProductivitySelector(BaseSelector):
    """Sessions, hours and rate per employee."""

    columns = [
        ("emp_id", "Employee ID"),
        ("name", "Name"),
        ("project", "Project"),
        ("sessions", "Sessions"),
        ("total_hours", "Hours"),
    ]

    def base_queryset(self, queryset):
        f = self.filters
        if f.emp_ids:
            queryset = queryset.filter(emp_id__in=f.emp_ids)
        if f.projects:
            queryset = queryset.filter(project__in=f.projects)
        if f.work_types:
            queryset = queryset.filter(work_type__in=f.work_types)

        if not f.date_from and not f.date_to:
            return queryset

        q_date = Q()
        if f.date_from:
            start, _ = day_bounds(f.date_from)
            q_date &= Q(start_time__gte=start)
        if f.date_to:
            _, end = day_bounds(f.date_to)
            q_date &= Q(start_time__lt=end)

        is_current = True
        if f.date_to and f.date_to < today_ist():
            is_current = False

        if is_current:
            q_running = Q(end_time__isnull=True, is_started=SessionState.RUNNING)
            return queryset.filter(q_date | q_running)

        return queryset.filter(q_date)

    def rows(self) -> list[dict]:
        from apps.allocations.models import TitleIndexingSession
        from apps.accounts.models import Employee
        
        queryset = self.base_queryset(WorkSession.objects.exclude(is_started=SessionState.ALLOCATED))

        rows_dict = {}
        for session in queryset:
            key = (session.emp_id, session.name, session.project)
            if key not in rows_dict:
                rows_dict[key] = {"sessions": 0, "total_seconds": 0}
            
            rows_dict[key]["sessions"] += 1
            rows_dict[key]["total_seconds"] += session.live_elapsed_seconds or 0
            
        # Add Title Indexing Sessions
        idx_qs = TitleIndexingSession.objects.all()
        f = self.filters
        if f.emp_ids:
            idx_qs = idx_qs.filter(employee_id__in=f.emp_ids)
        if f.projects:
            idx_qs = idx_qs.filter(project__in=f.projects)
        if f.work_types:
            idx_qs = idx_qs.filter(work_type__in=f.work_types)
            
        if f.date_from:
            start, _ = day_bounds(f.date_from)
            idx_qs = idx_qs.filter(started_at__gte=start)
        if f.date_to:
            _, end = day_bounds(f.date_to)
            idx_qs = idx_qs.filter(started_at__lt=end)
            
        employee_cache = {}
        
        for session in idx_qs:
            emp_id = session.employee_id
            if emp_id not in employee_cache:
                emp = Employee.objects.filter(emp_id=emp_id).first()
                employee_cache[emp_id] = emp.name if emp else emp_id
                
            name = employee_cache[emp_id]
            project = session.project
            key = (emp_id, name, project)
            
            if key not in rows_dict:
                rows_dict[key] = {"sessions": 0, "total_seconds": 0}
                
            rows_dict[key]["sessions"] += 1
            
            # calculate seconds if completed, else use current time
            if session.status == 'COMPLETED' and session.completed_at:
                diff = session.completed_at - session.started_at
                rows_dict[key]["total_seconds"] += int(diff.total_seconds())
            else:
                diff = now_ist() - session.started_at
                rows_dict[key]["total_seconds"] += int(diff.total_seconds())

        rows = []
        for (emp_id, name, project), data in rows_dict.items():
            seconds = data["total_seconds"]
            hours = seconds / 3600
            rows.append(
                {
                    "emp_id": emp_id,
                    "name": name,
                    "project": project,
                    "sessions": data["sessions"],
                    "total_hours": round(hours, 2),
                }
            )
        
        rows.sort(key=lambda x: x["sessions"], reverse=True)
        return rows


class SummarySelector(BaseSelector):
    """One row per work session — the detail report."""

    columns = [
        ("id", "ID"),
        ("emp_id", "Employee ID"),
        ("name", "Name"),
        ("project", "Project"),
        ("client_code", "Client code"),
        ("work_type", "Work type"),
        ("batch", "Order No."),
        ("start_time", "Start"),
        ("end_time", "End"),
        ("total_time", "Seconds"),
        ("work_location", "Location"),
        ("is_paused", "Is paused"),
    ]

    def base_queryset(self, queryset):
        f = self.filters
        if f.emp_ids:
            queryset = queryset.filter(emp_id__in=f.emp_ids)
        if f.projects:
            queryset = queryset.filter(project__in=f.projects)
        if f.work_types:
            queryset = queryset.filter(work_type__in=f.work_types)

        if not f.date_from and not f.date_to:
            return queryset

        q_date = Q()
        if f.date_from:
            start, _ = day_bounds(f.date_from)
            q_date &= Q(start_time__gte=start)
        if f.date_to:
            _, end = day_bounds(f.date_to)
            q_date &= Q(start_time__lt=end)

        is_current = True
        if f.date_to and f.date_to < today_ist():
            is_current = False

        if is_current:
            q_running = Q(end_time__isnull=True, is_started=SessionState.RUNNING)
            return queryset.filter(q_date | q_running)

        return queryset.filter(q_date)

    def rows(self) -> list[dict]:
        location_subquery = Employee.objects.filter(employee_id=OuterRef('emp_id')).values('department')[:1]
        queryset = self.base_queryset(
            WorkSession.objects.exclude(is_started=SessionState.ALLOCATED)
        ).annotate(work_location=Subquery(location_subquery)).order_by("-start_time")
        
        results = []
        for session in queryset:
            results.append({
                "id": session.id,
                "emp_id": session.emp_id,
                "name": session.name,
                "project": session.project,
                "client_code": session.client_code,
                "work_type": session.work_type,
                "batch": session.batch,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "total_time": session.live_elapsed_seconds,
                "work_location": getattr(session, "work_location", None),
                "is_paused": getattr(session, "is_paused", False),
            })
        return results


class BreakSelector(BaseSelector):
    """Break usage and overruns per employee."""

    date_field = "start_time"
    emp_field = "user_id"
    project_field = None
    work_type_field = None

    columns = [
        ("emp_id", "Employee ID"),
        ("name", "Name"),
        ("break_type", "Break type"),
        ("count", "Times taken"),
        ("total_minutes", "Total minutes"),
        ("allotted_minutes", "Allowed minutes"),
        ("overruns", "Overruns"),
    ]

    def rows(self) -> list[dict]:
        queryset = self.base_queryset(BreakTime.objects.closed())

        aggregated = (
            queryset.values("user_id", "user_name", "break_type")
            .annotate(
                count=Count("id"),
                total_seconds=Sum("total_time"),
                allotted_seconds=Sum("allotted_time"),
                overruns=Count("id", filter=Q(is_overrun=True)),
            )
            .order_by("user_id", "break_type")
        )

        return [
            {
                "emp_id": row["user_id"],
                "name": row["user_name"],
                "break_type": row["break_type"],
                "count": row["count"],
                "total_minutes": round((row["total_seconds"] or 0) / 60, 1),
                "allotted_minutes": round((row["allotted_seconds"] or 0) / 60, 1),
                "overruns": row["overruns"],
            }
            for row in aggregated
        ]


class AuditSelector(BaseSelector):
    """Quality feedback and accuracy per employee."""

    date_field = "created_at"
    emp_field = "emp_id"
    work_type_field = None

    columns = [
        ("emp_id", "Employee ID"),
        ("name", "Name"),
        ("feedback_count", "Feedback items"),
        ("total_errors", "Errors"),
        ("total_sampled", "Sampled"),
        ("accuracy_percent", "Accuracy %"),
        ("critical_count", "Critical"),
        ("unacknowledged", "Unacknowledged"),
    ]

    def rows(self) -> list[dict]:
        queryset = self.base_queryset(Feedback.objects.all())

        aggregated = (
            queryset.values("emp_id", "emp_name")
            .annotate(
                feedback_count=Count("id"),
                total_errors=Sum("error_count"),
                total_sampled=Sum("sample_size"),
                critical_count=Count("id", filter=Q(severity="critical")),
                unacknowledged=Count("id", filter=Q(acknowledged_at__isnull=True)),
            )
            .order_by("-total_errors")
        )

        rows = []
        for row in aggregated:
            sampled = row["total_sampled"] or 0
            errors = row["total_errors"] or 0
            rows.append(
                {
                    "emp_id": row["emp_id"],
                    "name": row["emp_name"],
                    "feedback_count": row["feedback_count"],
                    "total_errors": errors,
                    "total_sampled": sampled,
                    "accuracy_percent": round((1 - errors / sampled) * 100, 2) if sampled else None,
                    "critical_count": row["critical_count"],
                    "unacknowledged": row["unacknowledged"],
                }
            )
        return rows


class AllocationSelector(BaseSelector):
    """Allocation throughput and overdue counts."""

    date_field = "allocated_at"
    emp_field = "employee_id"
    work_type_field = None

    columns = [
        ("emp_id", "Employee ID"),
        ("name", "Name"),
        ("total", "Allocated"),
        ("completed", "Completed"),
        ("in_progress", "In progress"),
        ("pending", "Pending"),
        ("overdue", "Overdue"),
        ("total_quantity", "Total quantity"),
        ("completed_quantity", "Completed quantity"),
    ]

    def rows(self) -> list[dict]:
        from core.timezone import now_ist

        queryset = self.base_queryset(BatchAllocation.objects.all())

        aggregated = (
            queryset.values("employee_id", "employee_name")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                in_progress=Count("id", filter=Q(status="in_progress")),
                pending=Count("id", filter=Q(status="pending")),
                overdue=Count(
                    "id",
                    filter=Q(status__in=("pending", "in_progress"), due_at__lt=now_ist()),
                ),
                total_quantity=Sum("quantity"),
                completed_quantity=Sum("completed_quantity"),
            )
            .order_by("-total")
        )

        return [
            {
                "emp_id": row["employee_id"],
                "name": row["employee_name"],
                "total": row["total"],
                "completed": row["completed"],
                "in_progress": row["in_progress"],
                "pending": row["pending"],
                "overdue": row["overdue"],
                "total_quantity": row["total_quantity"] or 0,
                "completed_quantity": row["completed_quantity"] or 0,
            }
            for row in aggregated
        ]


class AttendanceSelector(BaseSelector):
    """Login/logout hours per employee per day."""

    date_field = "login_time"
    emp_field = "emp_id"
    project_field = None
    work_type_field = None

    columns = [
        ("emp_id", "Employee ID"),
        ("name", "Name"),
        ("date", "Date"),
        ("first_login", "First login"),
        ("last_logout", "Last logout"),
        ("logins", "Logins"),
    ]

    def rows(self) -> list[dict]:
        from django.db.models import Max, Min

        from apps.accounts.models import LoginHistory

        queryset = self.base_queryset(LoginHistory.objects.all())

        aggregated = (
            queryset.values("emp_id", "name", "date")
            .annotate(
                first_login=Min("login_time"),
                last_logout=Max("logout_time"),
                logins=Count("id"),
            )
            .order_by("-date", "emp_id")
        )
        return list(aggregated)


# The report catalogue. Adding a report is adding one entry.
REPORT_REGISTRY = {
    "productivity": ProductivitySelector,
    "summary": SummarySelector,
    "breaks": BreakSelector,
    "audit": AuditSelector,
    "allocations": AllocationSelector,
    "attendance": AttendanceSelector,
}


def get_selector(report_key: str, filters: ReportFilters) -> BaseSelector:
    try:
        return REPORT_REGISTRY[report_key](filters)
    except KeyError:
        from core.exceptions import ValidationError

        raise ValidationError(
            f"Unknown report '{report_key}'. Available: {', '.join(sorted(REPORT_REGISTRY))}"
        ) from None


def dashboard_metrics(user) -> dict:
    """The headline numbers on the supervisor dashboard."""
    start, end = day_bounds(today_ist())

    today_sessions = WorkSession.objects.filter(start_time__gte=start, start_time__lt=end)
    totals = today_sessions.filter(is_started=2).aggregate(
        seconds=Sum("total_time"), sessions=Count("id")
    )

    return {
        "date": str(today_ist()),
        "active_now": WorkSession.objects.active_now().count(),
        "on_break_now": BreakTime.objects.open().count(),
        "sessions_today": totals["sessions"] or 0,
        "hours_today": round((totals["seconds"] or 0) / 3600, 1),
        "open_allocations": BatchAllocation.objects.open().count(),
        "overdue_allocations": BatchAllocation.objects.overdue().count(),
        "unacknowledged_feedback": Feedback.objects.filter(acknowledged_at__isnull=True).count(),
    }
