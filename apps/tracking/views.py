"""Work session and target endpoints."""

from __future__ import annotations

from django.db.models import Count, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.tracking.models import Target, WorkSession
from apps.tracking.serializers import (
    EndSessionSerializer,
    StartSessionSerializer,
    TargetSerializer,
    TargetWriteSerializer,
    WorkSessionSerializer,
)
from apps.tracking.services import TargetService, WorkSessionService
from core.mixins import EnvelopeMixin, ServiceMixin
from core.permissions import (
    IsAdminOrSupervisor,
    IsAuthenticatedEmployee,
    IsOwnerOrSupervisor,
)
from core.timezone import today_ist


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
        if date_from := params.get("from"):
            from datetime import datetime
            from core.timezone import start_of_day
            dt = datetime.strptime(date_from, "%Y-%m-%d").date()
            queryset = queryset.filter(start_time__gte=start_of_day(dt))
        if date_to := params.get("to"):
            from datetime import datetime
            from core.timezone import day_bounds
            dt = datetime.strptime(date_to, "%Y-%m-%d").date()
            _, end_dt = day_bounds(dt)
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


from apps.tracking.models import Attendance, AttendanceStatus

class AttendanceViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticatedEmployee]



from apps.tracking.models import Attendance, AttendanceStatus

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
        from core.timezone import today_ist, now_ist
        att, _ = Attendance.objects.get_or_create(emp_id=request.user.emp_id, date=today_ist())
        if not att.first_login:
            att.first_login = now_ist()
            att.status = AttendanceStatus.PRESENT
            att.save()
        return EnvelopeMixin().ok({'detail': 'Shift started.', 'first_login': att.first_login.isoformat()})

    @action(detail=False, methods=['post'], url_path='end-shift')
    def end_shift(self, request):
        from core.timezone import today_ist, now_ist
        att = Attendance.objects.filter(emp_id=request.user.emp_id, date=today_ist()).first()
        if att and not att.last_logout:
            att.last_logout = now_ist()
            att.save()
        return EnvelopeMixin().ok({'detail': 'Shift ended.'})

    @action(detail=False, methods=['get'], url_path='admin-report')
    def admin_report(self, request):
        if not request.user.is_supervisor:
            return EnvelopeMixin().error('Unauthorized', status=403)
        
        project = request.query_params.get('project')
        emp_id_filter = request.query_params.get('emp_id')
        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')

        if not project:
            return EnvelopeMixin().error('Project is required.', status=400)
            
        from apps.masters.models import Project
        
        # The frontend passes the project name, but authorized projects are IDs
        proj_obj = Project.objects.filter(project_name__iexact=project).first()
        proj_id = proj_obj.project_id if proj_obj else project
        
        # Verify the supervisor is authorized for this project
        if not getattr(request.user, 'is_super_admin', False):
            authorized = request.user.get_authorized_projects()
            if not authorized or proj_id.lower() not in [p.lower() for p in authorized]:
                return EnvelopeMixin().error('Unauthorized for this project.', status=403)

        from apps.accounts.models import Employee, LoginHistory
        from apps.breaks.models import BreakTime
        from django.db.models import Q, Min, Max, Count
        from datetime import datetime
        from core.timezone import now_ist
        
        # Find all employees under this project
        emps = Employee.objects.filter(Q(project__icontains=proj_id))
        emps = emps.exclude(role='project_admin').exclude(role='super_admin')
        if emp_id_filter:
            emps = emps.filter(employee_id__icontains=emp_id_filter)
            
        emp_ids = list(emps.values_list('employee_id', flat=True))
        
        queryset = LoginHistory.objects.filter(emp_id__in=emp_ids)
        if date_from:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(date__gte=dt_from)
        if date_to:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(date__lte=dt_to)
            
        # Aggregate login history
        aggregated = queryset.values('emp_id', 'date').annotate(
            first_login=Min('login_time'),
            last_logout=Max('logout_time'),
            active_sessions=Count('id', filter=Q(logout_time__isnull=True))
        ).order_by('-date', 'emp_id')
        
        # Pre-fetch breaks for these employees in the given date range
        breaks = BreakTime.objects.filter(user_id__in=emp_ids)
        if date_from:
            breaks = breaks.filter(start_time__date__gte=dt_from)
        if date_to:
            breaks = breaks.filter(start_time__date__lte=dt_to)
            
        # Build dictionary of breaks: (emp_id, date) -> total_break_seconds
        break_dict = {}
        for b in breaks:
            if not b.start_time:
                continue
            b_date = b.start_time.date()
            key = (b.user_id, b_date)
            
            duration = 0
            if b.end_time:
                duration = (b.end_time - b.start_time).total_seconds()
            else:
                duration = (now_ist() - b.start_time).total_seconds()
                
            break_dict[key] = break_dict.get(key, 0) + duration

        # Build a mapping of emp_id to name
        emp_names = {e.employee_id: e.name for e in emps}

        data = []
        for a in aggregated:
            first_login = a['first_login']
            last_logout = a['last_logout']
            emp_id = a['emp_id']
            row_date = a['date']
            is_active = a.get('active_sessions', 0) > 0
            
            if is_active:
                last_logout = None
            
            total_break_sec = break_dict.get((emp_id, row_date), 0)
            net_hours = 0.0
            
            if first_login:
                end_time = last_logout
                if not end_time:
                    end_time = now_ist()
                
                total_sec = (end_time - first_login).total_seconds()
                net_sec = max(0, total_sec - total_break_sec)
                net_hours = round(net_sec / 3600.0, 2)
                
            data.append({
                'date': row_date.isoformat() if row_date else None,
                'emp_id': emp_id,
                'emp_name': emp_names.get(emp_id, emp_id),
                'status': 'Currently Logged In' if not last_logout else 'Logged Out',
                'first_login': first_login.isoformat() if first_login else None,
                'last_logout': last_logout.isoformat() if last_logout else None,
                'net_working_hours': net_hours
            })
            
        return EnvelopeMixin().ok(data)

from apps.tracking.models import SoftwareShift

class SoftwareShiftViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticatedEmployee]

    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        from core.timezone import today_ist
        from apps.tracking.models import SoftwareShift
        shift = SoftwareShift.objects.filter(emp_id=request.user.emp_id, date=today_ist()).first()
        
        if not shift:
            return EnvelopeMixin().ok({'status': 'UNSTARTED'})
            
        if shift.is_ended:
            return EnvelopeMixin().ok({'status': 'ENDED', 'total_time': shift.total_time})
            
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
            'start_time': shift.start_time.isoformat() if shift.start_time else None
        })

    @action(detail=False, methods=['post'], url_path='start-shift')
    def start_shift(self, request):
        from core.timezone import today_ist, now_ist
        from apps.tracking.models import SoftwareShift, Attendance, AttendanceStatus
        now = now_ist()
        
        att, _ = Attendance.objects.get_or_create(emp_id=request.user.emp_id, date=today_ist())
        if not att.first_login:
            att.first_login = now
            att.status = AttendanceStatus.PRESENT
            att.save()
            
        shift, created = SoftwareShift.objects.get_or_create(
            emp_id=request.user.emp_id, date=today_ist(),
            defaults={'start_time': now, 'updated_at': now, 'accumulated_seconds': 0}
        )
        if not created and shift.is_ended:
            return EnvelopeMixin().error('Shift already ended for today.')
            
        return EnvelopeMixin().ok({'detail': 'Shift started.'})

    @action(detail=False, methods=['post'], url_path='pause')
    def pause(self, request):
        from core.timezone import today_ist, now_ist
        from apps.tracking.models import SoftwareShift
        shift = SoftwareShift.objects.filter(emp_id=request.user.emp_id, date=today_ist()).first()
        
        if not shift or shift.is_ended or shift.is_paused:
            return EnvelopeMixin().ok({'detail': 'Already paused or ended.'})
            
        now = now_ist()
        shift.accumulated_seconds += (now - shift.updated_at).total_seconds()
        shift.is_paused = True
        shift.pause_start = now
        shift.updated_at = now
        shift.save()
        return EnvelopeMixin().ok({'detail': 'Paused.'})

    @action(detail=False, methods=['post'], url_path='resume')
    def resume(self, request):
        from core.timezone import today_ist, now_ist
        from apps.tracking.models import SoftwareShift
        shift = SoftwareShift.objects.filter(emp_id=request.user.emp_id, date=today_ist()).first()
        
        if not shift or shift.is_ended or not shift.is_paused:
            return EnvelopeMixin().ok({'detail': 'Already running or ended.'})
            
        now = now_ist()
        shift.is_paused = False
        shift.pause_start = None
        shift.updated_at = now
        shift.save()
        return EnvelopeMixin().ok({'detail': 'Resumed.'})

    @action(detail=False, methods=['post'], url_path='end-shift')
    def end_shift(self, request):
        from core.timezone import today_ist, now_ist
        from apps.tracking.models import SoftwareShift, Attendance
        now = now_ist()
        
        shift = SoftwareShift.objects.filter(emp_id=request.user.emp_id, date=today_ist()).first()
        if not shift or shift.is_ended:
            return EnvelopeMixin().ok({'detail': 'Already ended.'})
            
        if not shift.is_paused:
            shift.accumulated_seconds += (now - shift.updated_at).total_seconds()
            
        shift.is_paused = False
        shift.is_ended = True
        shift.end_time = now
        shift.updated_at = now
        
        total_sec = shift.accumulated_seconds
        hrs = int(total_sec // 3600)
        mins = int((total_sec % 3600) // 60)
        secs = int(total_sec % 60)
        shift.total_time = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        shift.save()
        
        att = Attendance.objects.filter(emp_id=request.user.emp_id, date=today_ist()).first()
        if att:
            att.last_logout = now
            att.save()
            
        return EnvelopeMixin().ok({'detail': 'Shift ended.'})
        
    def list(self, request):
        if not request.user.is_supervisor:
            return EnvelopeMixin().error('Unauthorized', status=403)
            
        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')
        
        from datetime import datetime
        qs = SoftwareShift.objects.all()
        from apps.tracking.models import Attendance, AttendanceStatus
        leave_qs = Attendance.objects.filter(status=AttendanceStatus.LEAVE)
        
        if date_from:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            qs = qs.filter(date__gte=dt_from)
            leave_qs = leave_qs.filter(date__gte=dt_from)
        if date_to:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            qs = qs.filter(date__lte=dt_to)
            leave_qs = leave_qs.filter(date__lte=dt_to)
            
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
                'work_location': "",
                'is_paused': False,
                'type': 'software_shift',
                'status': 'Present'
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

from django.db import connection
from django.http import HttpResponse

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
