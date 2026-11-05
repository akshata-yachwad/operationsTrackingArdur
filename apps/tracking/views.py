"""Work session and target endpoints."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db import connection
from django.db.models import Count, Q, Sum
from django.db.models.functions import Trim
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.accounts.models import Employee, LoginHistory
from apps.breaks.models import BreakTime
from apps.masters.models import Project, Shift
from apps.tracking.models import (
    Attendance,
    AttendanceStatus,
    SoftwareShift,
    Target,
    WorkSession,
)
from apps.tracking.serializers import (
    EndSessionSerializer,
    StartSessionSerializer,
    TargetSerializer,
    TargetWriteSerializer,
    WorkSessionSerializer,
)
from apps.tracking.services import ShiftService, TargetService, WorkSessionService
from core.mixins import EnvelopeMixin, ServiceMixin
from core.permissions import (
    IsAdminOrSupervisor,
    IsAuthenticatedEmployee,
    IsOwnerOrSupervisor,
)
from core.serializers import parse_date_range
from core.timezone import IST, day_bounds, now_ist, start_of_day, to_ist, today_ist


class WorkSessionViewSet(ServiceMixin, EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    """/api/v1/tracking/sessions/

    Read-only as a ModelViewSet: every mutation is an explicit, named action,
    because "update a work session" is not one operation — it is start, pause,
    resume or end, each with different rules.
    """

    serializer_class = WorkSessionSerializer
    service_class = WorkSessionService
    permission_classes = [IsOwnerOrSupervisor]
    owner_field = "emp_id"
    ordering = ["-start_time"]

    def get_queryset(self):
        # Row-level scoping. An object permission does not protect a list.
        queryset = WorkSession.objects.visible_to(self.request.user)

        params = self.request.query_params
        if emp_id := params.get("emp_id"):
            queryset = queryset.filter(emp_id=emp_id)
        if project := params.get("project"):
            queryset = queryset.filter(project=project)
        if params.get("open") == "true":
            queryset = queryset.open()
        if params.get("today") == "true":
            queryset = queryset.for_day()
        date_from, date_to = parse_date_range(params)
        if date_from:
            start_dt, _ = day_bounds(date_from)
            queryset = queryset.filter(start_time__gte=start_dt)
        if date_to:
            _, end_dt = day_bounds(date_to)
            queryset = queryset.filter(start_time__lt=end_dt)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = self.service.start_session(**serializer.validated_data)
        return self.ok(WorkSessionSerializer(session).data, status=201)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        session = self.service.pause_session(int(pk))
        return self.ok(WorkSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        session = self.service.resume_session(int(pk))
        return self.ok(WorkSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        serializer = EndSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = self.service.end_session(int(pk), **serializer.validated_data)
        return self.ok(WorkSessionSerializer(session).data)

    @action(detail=True, methods=["post"], url_path="indexing-submit")
    def indexing_submit(self, request, pk=None):
        units = request.data.get("units")
        if not units:
            return self.error("Number of units is required.", status=400)
        try:
            units = int(units)
        except ValueError:
            return self.error("Units must be an integer.", status=400)
            
        result = self.service.indexing_submit(int(pk), units)
        return self.ok({
            "ended_session": WorkSessionSerializer(result["ended_session"]).data,
            "new_session": WorkSessionSerializer(result["new_session"]).data,
            "units_submitted": result["units_submitted"]
        })

    def destroy(self, request, *args, **kwargs):
        self.service.delete_session(int(kwargs["pk"]))
        return self.ok({"detail": "Work session removed."})

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        """The caller's own open session, or null. Polled on page load only —
        after that, updates arrive over the websocket."""
        session = WorkSession.objects.filter(emp_id=request.user.emp_id).open().first()
        return self.ok(WorkSessionSerializer(session).data if session else None)

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """Everyone currently working — the supervisor floor view."""
        self.check_object_permissions(request, request.user)
        if not request.user.is_supervisor:
            from core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("Only a supervisor can see the floor view.")

        sessions = WorkSession.objects.active_now().order_by("emp_id")
        return self.ok(WorkSessionSerializer(sessions, many=True).data)


class DashboardSummaryView(EnvelopeMixin, APIView):
    """GET /api/v1/tracking/summary/ — one request for the dashboard header."""

    permission_classes = [IsAuthenticatedEmployee]

    def get(self, request):
        emp_id = request.query_params.get("emp_id") or request.user.emp_id

        # Looking at someone else's dashboard is a supervisor action.
        if emp_id != request.user.emp_id and not request.user.is_supervisor:
            from core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("You can only view your own dashboard.")

        today = WorkSession.objects.filter(emp_id=emp_id).for_day().completed()
        totals = today.aggregate(
            sessions=Count("id"), seconds=Sum("total_time")
        )

        open_session = WorkSession.objects.filter(emp_id=emp_id).open().first()
        target = Target.objects.filter(emp_id=emp_id, target_date=today_ist()).first()

        from apps.breaks.models import BreakTime
        from apps.accounts.models import LoginHistory
        from core.timezone import now_ist

        today_breaks = BreakTime.objects.filter(user_id=emp_id, start_time__date=today_ist())
        on_break = today_breaks.filter(end_time__isnull=True).exists()

        break_seconds = 0
        for b in today_breaks:
            end_val = b.end_time or now_ist()
            break_seconds += (end_val - b.start_time).total_seconds()
            
        login_record = LoginHistory.objects.filter(emp_id=emp_id, date=today_ist()).order_by('login_time').first()
        login_time = login_record.login_time if login_record else None
        logout_time = login_record.logout_time if login_record else None
        
        gross_seconds = 0
        if login_time:
            end_val = logout_time or now_ist()
            gross_seconds = (end_val - login_time).total_seconds()
            
        net_seconds = max(0, gross_seconds - break_seconds)

        return self.ok(
            {
                "emp_id": emp_id,
                "open_session": WorkSessionSerializer(open_session).data if open_session else None,
                "today_sessions": totals["sessions"] or 0,
                "today_seconds": round(totals["seconds"] or 0, 2),
                "target": TargetSerializer(target).data if target else None,
                "on_break": on_break,
                "attendance": {
                    "login_time": login_time.isoformat() if login_time else None,
                    "logout_time": logout_time.isoformat() if logout_time else None,
                    "break_seconds": round(break_seconds),
                    "net_seconds": round(net_seconds),
                }
            }
        )


class TargetViewSet(ServiceMixin, EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    """/api/v1/tracking/targets/ — read for all, write for supervisors."""

    serializer_class = TargetSerializer
    service_class = TargetService
    permission_classes = [IsAuthenticatedEmployee]
    ordering = ["-target_date"]

    def get_queryset(self):
        queryset = Target.objects.visible_to(self.request.user)
        if emp_id := self.request.query_params.get("emp_id"):
            queryset = queryset.filter(emp_id=emp_id)
        if self.request.query_params.get("today") == "true":
            queryset = queryset.for_day()
        return queryset

    def get_permissions(self):
        if self.action == "create":
            return [IsAdminOrSupervisor()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = TargetWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = self.service_class.assign_target(
            serializer.validated_data, request.user.emp_id
        )
        return self.created(TargetSerializer(target).data)


class MonthlyAttendanceView(EnvelopeMixin, APIView):
    """GET /api/v1/tracking/attendance-history/"""
    permission_classes = [IsAuthenticatedEmployee]

    def get(self, request):
        emp_id = request.query_params.get("emp_id") or request.user.emp_id
        if emp_id != request.user.emp_id and not request.user.is_supervisor:
            from core.exceptions import PermissionDeniedError
            raise PermissionDeniedError("You can only view your own attendance.")

        from apps.breaks.models import BreakTime
        from apps.accounts.models import LoginHistory
        from core.timezone import now_ist
        
        now = now_ist()
        start_date = now.replace(day=1).date()
        
        logins = LoginHistory.objects.filter(emp_id=emp_id, date__gte=start_date).order_by('date', 'login_time')
        breaks = BreakTime.objects.filter(user_id=emp_id, start_time__date__gte=start_date)
        
        daily_data = {}
        for b in breaks:
            b_date = b.start_time.date()
            if b_date not in daily_data:
                daily_data[b_date] = {'breaks': 0, 'login': None, 'logout': None}
            end_val = b.end_time or now
            daily_data[b_date]['breaks'] += (end_val - b.start_time).total_seconds()
            
        for l in logins:
            l_date = l.date
            if l_date not in daily_data:
                daily_data[l_date] = {'breaks': 0, 'login': None, 'logout': None}
            
            if not daily_data[l_date]['login']:
                daily_data[l_date]['login'] = l.login_time
            daily_data[l_date]['logout'] = l.logout_time
            
        results = []
        for d in sorted(daily_data.keys(), reverse=True):
            data = daily_data[d]
            login_time = data['login']
            logout_time = data['logout']
            break_secs = data['breaks']
            
            gross_secs = 0
            if login_time:
                end_val = logout_time or (now if d == now.date() else login_time)
                gross_secs = (end_val - login_time).total_seconds()
            net_secs = max(0, gross_secs - break_secs)
            
            results.append({
                "date": d.isoformat(),
                "login_time": login_time.isoformat() if login_time else None,
                "logout_time": logout_time.isoformat() if logout_time else None,
                "break_seconds": round(break_secs),
                "net_seconds": round(net_secs)
            })
            
        return self.ok(results)


class AttendanceViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticatedEmployee]

    @action(detail=False, methods=['get'], url_path='my-history')
    def my_history(self, request):
        attendance_qs = Attendance.objects.filter(emp_id=request.user.emp_id).order_by('-date')[:30]
        data = []
        for a in attendance_qs:
            data.append({
                'date': a.date.isoformat(),
                'status': a.status,
                'first_login': a.first_login.isoformat() if a.first_login else None,
                'last_logout': a.last_logout.isoformat() if a.last_logout else None,
                'total_break_time': a.total_break_time
            })
        return EnvelopeMixin().ok(data)

    @action(detail=False, methods=['post'], url_path='mark-leave')
    def mark_leave(self, request):
        date_str = request.data.get('date')
        if not date_str:
            return EnvelopeMixin().error('Date is required.', status=400)
        from datetime import datetime
        dt = datetime.strptime(date_str, '%Y-%m-%d').date()
        att, _ = Attendance.objects.get_or_create(emp_id=request.user.emp_id, date=dt)
        att.status = AttendanceStatus.LEAVE
        att.save()
        return EnvelopeMixin().ok({'detail': 'Leave marked successfully.'})

    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        from core.timezone import today_ist
        att = Attendance.objects.filter(emp_id=request.user.emp_id, date=today_ist()).first()
        is_active = False
        first_login = None
        if att and att.first_login and not att.last_logout:
            is_active = True
            first_login = att.first_login.isoformat()
        return EnvelopeMixin().ok({'is_active': is_active, 'first_login': first_login})

    @action(detail=False, methods=['post'], url_path='start-shift')
    def start_shift(self, request):
        att = ShiftService(actor=request.user).start_attendance()
        return EnvelopeMixin().ok({'detail': 'Shift started.', 'first_login': att.first_login.isoformat()})

    @action(detail=False, methods=['post'], url_path='end-shift')
    def end_shift(self, request):
        ShiftService(actor=request.user).end_attendance()
        return EnvelopeMixin().ok({'detail': 'Shift ended.'})

    @action(detail=False, methods=['get'], url_path='admin-report')
    def admin_report(self, request):
        if not request.user.is_supervisor:
            return EnvelopeMixin().error('Unauthorized', status=403)

        def parse_date(value):
            if not value:
                return None
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None

        date_from = parse_date(request.query_params.get("from"))
        date_to = parse_date(request.query_params.get("to"))
        if (request.query_params.get("from") and date_from is None) or (
            request.query_params.get("to") and date_to is None
        ):
            return EnvelopeMixin().error("Dates must use YYYY-MM-DD format.", status=400)
        if date_from is None and date_to is None:
            date_from = date_to = today_ist()
        elif date_from is None:
            date_from = date_to
        elif date_to is None:
            date_to = date_from
        if date_from > date_to:
            return EnvelopeMixin().error("The end date must not precede the start date.", status=400)

        projects = list(Project.objects.all())
        projects_by_key = {}
        for item in projects:
            for key in (item.project_id, item.project_name):
                if key:
                    projects_by_key[key.strip().casefold()] = item

        project_filter = (request.query_params.get("project") or "").strip()
        selected_project = projects_by_key.get(project_filter.casefold()) if project_filter else None
        if project_filter and selected_project is None:
            return EnvelopeMixin().error("Project not found.", status=400)

        authorized = {
            value.strip().casefold()
            for value in request.user.get_authorized_projects()
            if value.strip() and value != "*"
        }

        def employee_projects(employee):
            tokens = [value.strip() for value in (employee.project or "").split("|") if value.strip()]
            return [
                (projects_by_key.get(token.casefold()).project_name
                 if projects_by_key.get(token.casefold()) else token)
                for token in tokens
            ]

        def is_authorized(employee):
            if request.user.is_super_admin:
                return True
            for token in (employee.project or "").split("|"):
                token = token.strip().casefold()
                project_item = projects_by_key.get(token)
                if token in authorized or (
                    project_item
                    and any(
                        candidate and candidate.strip().casefold() in authorized
                        for candidate in (project_item.project_id, project_item.project_name)
                    )
                ):
                    return True
            return False

        employee_queryset = (
            Employee.objects.exclude(role__in=("project_admin", "super_admin"))
            .filter(Q(date_of_joining__isnull=True) | Q(date_of_joining__lte=date_to))
            .filter(
                Q(status="active")
                | Q(status="inactive", active_inactive_date__gte=date_from)
            )
        )
        search = (request.query_params.get("search") or request.query_params.get("emp_id") or "").strip()
        location_filter = (request.query_params.get("location") or "").strip()
        if search:
            employee_queryset = employee_queryset.filter(
                Q(employee_id__icontains=search) | Q(name__icontains=search)
            )
        if location_filter:
            employee_queryset = employee_queryset.annotate(
                attendance_location=Trim("department")
            ).filter(attendance_location__iexact=location_filter)
        employees = list(employee_queryset.order_by("name", "employee_id"))
        if selected_project:
            accepted = {
                selected_project.project_id.strip().casefold(),
                selected_project.project_name.strip().casefold(),
            }
            employees = [
                employee for employee in employees
                if any(
                    token.strip().casefold() in accepted
                    for token in (employee.project or "").split("|")
                    if token.strip()
                )
            ]
            if not request.user.is_super_admin and not any(
                value in authorized for value in accepted
            ):
                return EnvelopeMixin().error("Unauthorized for this project.", status=403)
        else:
            employees = [employee for employee in employees if is_authorized(employee)]

        employee_ids = [employee.employee_id for employee in employees]
        if not employee_ids:
            return EnvelopeMixin().ok([])

        day_count = (date_to - date_from).days + 1
        report_days = [date_from + timedelta(days=offset) for offset in range(day_count)]
        range_start = start_of_day(date_from)
        range_end = start_of_day(date_to + timedelta(days=1))
        now = now_ist()

        attendance_by_key = {
            (row.emp_id, row.date): row
            for row in Attendance.objects.filter(
                emp_id__in=employee_ids, date__range=(date_from, date_to)
            )
        }
        login_history = list(
            LoginHistory.objects.filter(
                emp_id__in=employee_ids,
                login_time__gte=range_start,
                login_time__lt=range_end,
            ).order_by("login_time", "id")
        )
        logins_by_key = {}
        for login in login_history:
            local_login = to_ist(login.login_time)
            if local_login is not None:
                logins_by_key.setdefault((login.emp_id, local_login.date()), []).append(login)

        breaks = list(
            BreakTime.objects.filter(
                user_id__in=employee_ids,
                start_time__lt=range_end,
            ).filter(Q(end_time__gt=range_start) | Q(end_time__isnull=True))
        )
        breaks_by_employee = {}
        for item in breaks:
            breaks_by_employee.setdefault(item.user_id, []).append(item)

        shifts_by_name = {
            shift.shift_name.strip().casefold(): shift
            for shift in Shift.objects.filter(is_active=True)
        }

        def union_intervals(intervals):
            merged = []
            for start, end in sorted(intervals):
                if end <= start:
                    continue
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            return merged

        def interval_seconds(intervals):
            return sum((end - start).total_seconds() for start, end in union_intervals(intervals))

        data = []
        employee_by_id = {employee.employee_id: employee for employee in employees}
        for day in report_days:
            day_start = start_of_day(day)
            day_end = start_of_day(day + timedelta(days=1))
            for emp_id in employee_ids:
                employee = employee_by_id[emp_id]
                if employee.date_of_joining and day < employee.date_of_joining:
                    continue
                if (
                    employee.status == "inactive"
                    and (
                        employee.active_inactive_date is None
                        or day > employee.active_inactive_date
                    )
                ):
                    continue
                attendance = attendance_by_key.get((emp_id, day))
                sessions = logins_by_key.get((emp_id, day), [])
                shift = shifts_by_name.get((employee.shift or "").strip().casefold())
                allowed_end = day_end
                if shift and shift.is_overnight:
                    allowed_end = datetime.combine(
                        day + timedelta(days=1), shift.end_time, tzinfo=IST
                    )

                intervals = []
                logins = []
                logouts = []
                is_in_progress = False
                for session in sessions:
                    start = to_ist(session.login_time)
                    if start is None:
                        continue
                    logins.append(start)
                    end = to_ist(session.logout_time)
                    if end is None:
                        if day != today_ist():
                            continue
                        is_in_progress = True
                        end = now
                    elif end <= start:
                        continue
                    elif end > allowed_end or end > now:
                        continue
                    else:
                        logouts.append(end)
                    start = max(start, day_start)
                    end = min(end, allowed_end, now if day == today_ist() else allowed_end)
                    if end > start:
                        intervals.append((start, end))

                if attendance and attendance.first_login:
                    first = to_ist(attendance.first_login)
                    if first and not logins:
                        logins.append(first)
                        if attendance.last_logout:
                            last = to_ist(attendance.last_logout)
                            if last and first < last <= allowed_end and last <= now:
                                logouts.append(last)
                                intervals.append((max(first, day_start), last))
                        elif day == today_ist():
                            is_in_progress = True
                            intervals.append((max(first, day_start), min(now, allowed_end)))

                work_intervals = union_intervals(intervals)
                break_intervals = []
                for item in breaks_by_employee.get(emp_id, []):
                    start = max(to_ist(item.start_time), day_start)
                    end_value = to_ist(item.end_time) if item.end_time else (
                        now if day == today_ist() else None
                    )
                    if end_value is not None:
                        end = min(end_value, allowed_end, now if day == today_ist() else allowed_end)
                        if end > start:
                            break_intervals.append((start, end))
                merged_breaks = union_intervals(break_intervals)
                gross_seconds = interval_seconds(work_intervals)
                break_seconds = sum(
                    max(0, (min(work_end, break_end) - max(work_start, break_start)).total_seconds())
                    for work_start, work_end in work_intervals
                    for break_start, break_end in merged_breaks
                )
                net_seconds = max(0, round(gross_seconds - break_seconds))

                first_login = min(logins) if logins else None
                last_logout = max(logouts) if logouts else None
                if attendance:
                    recorded_first = to_ist(attendance.first_login)
                    recorded_last = to_ist(attendance.last_logout)
                    if recorded_first and (first_login is None or recorded_first < first_login):
                        first_login = recorded_first
                    if recorded_last and recorded_last <= allowed_end and (
                        last_logout is None or recorded_last > last_logout
                    ):
                        last_logout = recorded_last
                    if attendance.first_login and not attendance.last_logout and day == today_ist():
                        is_in_progress = True
                        last_logout = None

                if attendance and attendance.status == AttendanceStatus.LEAVE:
                    status = "On Leave"
                    net_seconds = 0
                    first_login = last_logout = None
                elif is_in_progress:
                    status = "In Progress"
                    last_logout = None
                elif sessions or (attendance and attendance.first_login):
                    status = "Present"
                elif attendance and attendance.status == AttendanceStatus.ABSENT:
                    status = "Absent"
                elif attendance and attendance.status == AttendanceStatus.PRESENT:
                    status = "Present"
                else:
                    status = "No Record"

                assigned = employee_projects(employee)
                if selected_project:
                    project_name = selected_project.project_name
                else:
                    project_name = ", ".join(assigned) or "-"
                data.append({
                    "date": day.isoformat(),
                    "emp_id": emp_id,
                    "emp_name": employee.name or emp_id,
                    "location": (employee.department or "").strip() or "-",
                    "project": project_name,
                    "status": status,
                    "first_login": first_login.isoformat() if first_login else None,
                    "last_logout": last_logout.isoformat() if last_logout else None,
                    "total_break_time": round(break_seconds),
                    "net_working_seconds": net_seconds,
                    "net_working_hours": round(net_seconds / 3600, 2),
                })

        return EnvelopeMixin().ok(data)

class SoftwareShiftViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticatedEmployee]

    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        from core.timezone import today_ist
        from apps.tracking.models import SoftwareShift
        today = today_ist()
        incomplete_summary = self._incomplete_shift_summary(request.user.emp_id, today)
        shift = SoftwareShift.objects.filter(emp_id=request.user.emp_id, date=today).first()
        
        if not shift:
            return EnvelopeMixin().ok({'status': 'UNSTARTED', **incomplete_summary})
            
        if shift.is_ended:
            return EnvelopeMixin().ok({
                'status': 'ENDED',
                'total_time': shift.total_time,
                **incomplete_summary,
            })
            
        from core.timezone import now_ist
        if shift.is_paused:
            current_active_seconds = shift.accumulated_seconds
            status_str = 'PAUSED'
        else:
            now = now_ist()
            current_active_seconds = shift.accumulated_seconds + (now - shift.updated_at).total_seconds()
            status_str = 'RUNNING'
            
        return EnvelopeMixin().ok({
            'status': status_str,
            'accumulated_seconds': current_active_seconds,
            'start_time': shift.start_time.isoformat() if shift.start_time else None,
            **incomplete_summary,
        })

    @action(detail=False, methods=['post'], url_path='start-shift')
    def start_shift(self, request):
        shift = ShiftService(actor=request.user).start_software_shift()
        if shift.is_ended:
            return EnvelopeMixin().error('Shift already ended for today.')
            
        return EnvelopeMixin().ok({'detail': 'Shift started.'})

    @action(detail=False, methods=['post'], url_path='pause')
    def pause(self, request):
        if not ShiftService(actor=request.user).pause_software_shift():
            return EnvelopeMixin().ok({'detail': 'Already paused or ended.'})
        return EnvelopeMixin().ok({'detail': 'Paused.'})

    @action(detail=False, methods=['post'], url_path='resume')
    def resume(self, request):
        if not ShiftService(actor=request.user).resume_software_shift():
            return EnvelopeMixin().ok({'detail': 'Already running or ended.'})
        return EnvelopeMixin().ok({'detail': 'Resumed.'})

    @action(detail=False, methods=['post'], url_path='end-shift')
    def end_shift(self, request):
        if not ShiftService(actor=request.user).end_software_shift():
            return EnvelopeMixin().ok({'detail': 'Already ended.'})
        return EnvelopeMixin().ok({'detail': 'Shift ended.'})

    @staticmethod
    def _incomplete_shift_summary(emp_id, today):
        queryset = SoftwareShift.objects.filter(
            emp_id=emp_id,
            date__lt=today,
            is_ended=False,
        ).order_by("-date")
        count = queryset.count()
        shifts = queryset.values("id", "date", "start_time")[:20]
        return {
            "incomplete_shift_count": count,
            "incomplete_shifts": [
                {
                    "id": shift["id"],
                    "date": shift["date"].isoformat(),
                    "start_time": shift["start_time"].isoformat()
                    if shift["start_time"]
                    else None,
                }
                for shift in shifts
            ],
        }
        
    def list(self, request):
        if not request.user.is_supervisor:
            return EnvelopeMixin().error('Unauthorized', status=403)
            
        qs = SoftwareShift.objects.all()
        from apps.tracking.models import Attendance, AttendanceStatus
        leave_qs = Attendance.objects.filter(status=AttendanceStatus.LEAVE)

        date_from, date_to = parse_date_range(request.query_params)
        if date_from:
            qs = qs.filter(date__gte=date_from)
            leave_qs = leave_qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
            leave_qs = leave_qs.filter(date__lte=date_to)
            
        from apps.accounts.models import Employee
        emps = {e.employee_id: e for e in Employee.objects.all()}
        
        data = []
        for shift in qs:
            emp = emps.get(shift.emp_id)
            if not emp:
                continue
                
            # Filter authorized projects for supervisor
            if not getattr(request.user, 'is_super_admin', False):
                authorized = request.user.get_authorized_projects()
                emp_projs = [p.strip().lower() for p in (emp.project or "").split("|") if p.strip()]
                if not any(p in [auth.lower() for auth in authorized] for p in emp_projs):
                    continue
                    
            data.append({
                'id': f"softshift_{shift.id}",
                'emp_id': shift.emp_id,
                'name': emp.name,
                'project_name': shift.project_name,
                'client_code': "",
                'work_type': "",
                'batch': "",
                'units_completed': 0,
                'start_time': "",
                'end_time': "",
                'date': shift.date.isoformat(),
                'total_time': shift.total_time,
                'work_location': emp.department,
                'is_paused': False,
                'type': 'software_shift',
                'status': 'Present',
                'recovery_status': (
                    'needs_review'
                    if shift.date < today_ist() and not shift.is_ended
                    else None
                ),
            })
            
        from apps.masters.models import Project
        simplified_projs = [p.project_name.lower() for p in Project.objects.filter(is_simplified_project=True)]
        if not simplified_projs:
            simplified_projs = ['software']
            
        for att in leave_qs:
            emp = emps.get(att.emp_id)
            if not emp:
                continue
                
            # Filter authorized projects for supervisor
            emp_projs = [p.strip().lower() for p in (emp.project or "").split("|") if p.strip()]
            if not getattr(request.user, 'is_super_admin', False):
                authorized = request.user.get_authorized_projects()
                if not any(p in [auth.lower() for auth in authorized] for p in emp_projs):
                    continue
                    
            # Only include if employee is assigned to a simplified project
            matching_simplified = [p for p in emp_projs if p in simplified_projs]
            if not matching_simplified:
                continue
                
            proj_name = matching_simplified[0].upper()
            
            data.append({
                'id': f"leave_{att.id}",
                'emp_id': att.emp_id,
                'name': emp.name,
                'project_name': proj_name,
                'client_code': "",
                'work_type': "",
                'batch': "",
                'units_completed': 0,
                'start_time': "",
                'end_time': "",
                'date': att.date.isoformat(),
                'total_time': "00:00:00",
                'work_location': "",
                'is_paused': False,
                'type': 'software_shift',
                'status': 'Leave'
            })
            
        return EnvelopeMixin().ok(data)

def run_migrations(request):
    sql = """
    CREATE TABLE IF NOT EXISTS `ot_software_shifts` (
        `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, 
        `emp_id` varchar(20) NOT NULL, 
        `date` date NOT NULL, 
        `total_time` varchar(20) NOT NULL, 
        `project_name` varchar(150) NOT NULL, 
        `created_at` datetime(6) NOT NULL, 
        `updated_at` datetime(6) NOT NULL, 
        `accumulated_seconds` double precision DEFAULT 0.0 NOT NULL,
        `end_time` datetime(6) NULL,
        `is_ended` bool DEFAULT 0 NOT NULL,
        `is_paused` bool DEFAULT 0 NOT NULL,
        `pause_start` datetime(6) NULL,
        `start_time` datetime(6) NULL,
        CONSTRAINT `uq_software_shift_emp_day` UNIQUE (`emp_id`, `date`)
    );
    """
    
    alter_statements = [
        "ALTER TABLE `ot_software_shifts` ADD COLUMN `accumulated_seconds` double precision NOT NULL DEFAULT 0.0;",
        "ALTER TABLE `ot_software_shifts` ADD COLUMN `end_time` datetime(6) NULL;",
        "ALTER TABLE `ot_software_shifts` ADD COLUMN `is_ended` bool NOT NULL DEFAULT 0;",
        "ALTER TABLE `ot_software_shifts` ADD COLUMN `is_paused` bool NOT NULL DEFAULT 0;",
        "ALTER TABLE `ot_software_shifts` ADD COLUMN `pause_start` datetime(6) NULL;",
        "ALTER TABLE `ot_software_shifts` ADD COLUMN `start_time` datetime(6) NULL;",
    ]

    try:
        with connection.cursor() as cursor:
            # 1. Try to create the table (if it doesn't exist at all)
            cursor.execute(sql)
            
            # 2. If it did exist, try to add the missing columns one by one
            # (We ignore errors if the column already exists)
            for stmt in alter_statements:
                try:
                    cursor.execute(stmt)
                except Exception:
                    pass
                    
        return HttpResponse("Database updated successfully with raw SQL! You can now use the new timer.")
    except Exception as e:
        return HttpResponse(f"Error updating database: {e}")
