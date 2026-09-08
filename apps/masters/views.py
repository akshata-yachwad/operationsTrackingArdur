"""Master data endpoints.

Read is open to every signed-in employee — every screen needs these lists.
Write is admin-only, which is the fix for "an employee can delete master data".
"""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.masters.models import ClientCode, Project, Shift, WorkType
from apps.masters.serializers import (
    ClientCodeSerializer,
    ProjectSerializer,
    ShiftSerializer,
    WorkTypeSerializer,
)
from apps.masters.services import (
    MasterDataService,
    active_client_codes,
    active_projects,
    active_shifts,
    active_work_types,
)
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly, IsAuthenticatedEmployee


class BaseMasterViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """CRUD wired to the matching MasterDataService subclass.

    ``?active=true`` filters to live rows; the default returns everything so
    an admin can see and restore what has been deactivated.
    """

    permission_classes = [IsAdminOrReadOnly]

    def get_service(self):
        return MasterDataService.for_model(self.queryset.model)(actor=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get("active") == "true":
            queryset = queryset.active()
        return queryset

    def perform_create(self, serializer):
        serializer.instance = self.get_service().create(dict(serializer.validated_data))

    def perform_update(self, serializer):
        serializer.instance = self.get_service().update(
            serializer.instance, dict(serializer.validated_data)
        )

    def perform_destroy(self, instance):
        self.get_service().deactivate(instance)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        instance = self.get_object()
        self.get_service().update(instance, {"is_active": True})
        return self.ok(self.get_serializer(instance).data)

    @action(detail=True, methods=["delete"], url_path="purge")
    def purge(self, request, pk=None):
        """Hard delete. Refused with 409 if anything references the row."""
        self.get_service().hard_delete(self.get_object())
        return self.ok({"detail": "Deleted."}, status=200)


class WorkTypeViewSet(BaseMasterViewSet):
    queryset = WorkType.objects.all()
    serializer_class = WorkTypeSerializer
    lookup_field = "wt_id"
    search_fields = ["work_type", "description"]
    ordering_fields = ["work_type", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_project_admin', False) and not getattr(user, 'is_super_admin', False):
            authorized = user.get_authorized_projects()
            if authorized:
                from apps.masters.models import Project
                from django.db.models import Q
                q_objs = Q()
                for p in authorized:
                    q_objs |= Q(project_id__iexact=p) | Q(project_name__iexact=p)
                projects = Project.objects.filter(q_objs)
                allowed_wt_names = set()
                for proj in projects:
                    if proj.worktypes:
                        allowed_wt_names.update([w.strip() for w in proj.worktypes.split("|") if w.strip()])
                if allowed_wt_names:
                    queryset = queryset.filter(work_type__in=allowed_wt_names)
                else:
                    queryset = queryset.none()
            else:
                queryset = queryset.none()
        return queryset

    @action(detail=False, methods=["get"], url_path="next-id")
    def next_id(self, request):
        """Return the next auto-generated wt_id (replaces /next_worktype_id)."""
        last = WorkType.objects.order_by("-id").values("wt_id").first()
        if last and last.get("wt_id"):
            num_part = "".join(filter(str.isdigit, last["wt_id"]))
            next_num = int(num_part) + 1 if num_part else 1
        else:
            next_num = 1
        return self.ok({"next_id": f"WT-{next_num:03d}"})


class ProjectViewSet(BaseMasterViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_field = "project_id"
    search_fields = ["project_name", "project_code", "client_name"]
    ordering_fields = ["project_name", "start_date", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_project_admin', False) and not getattr(user, 'is_super_admin', False):
            authorized = user.get_authorized_projects()
            if authorized:
                from django.db.models import Q
                q_objs = Q()
                for p in authorized:
                    q_objs |= Q(project_id__iexact=p) | Q(project_name__iexact=p)
                queryset = queryset.filter(q_objs)
            else:
                queryset = queryset.none()
        return queryset

    @action(detail=False, methods=["get"], url_path="next-id")
    def next_id(self, request):
        """Return the next auto-generated project_id (replaces /get_next_project_id)."""
        last = Project.objects.order_by("-id").values("project_id").first()
        if last and last.get("project_id"):
            num_part = "".join(filter(str.isdigit, last["project_id"]))
            next_num = int(num_part) + 1 if num_part else 1
        else:
            next_num = 1
        return self.ok({"next_project_id": f"PRO-{next_num:04d}"})


class ClientCodeViewSet(BaseMasterViewSet):
    queryset = ClientCode.objects.all()
    serializer_class = ClientCodeSerializer
    lookup_field = "cc_id"
    search_fields = ["client_code", "client_name", "project"]
    ordering_fields = ["client_code", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_project_admin', False) and not getattr(user, 'is_super_admin', False):
            authorized = user.get_authorized_projects()
            if authorized:
                from django.db.models import Q
                q_objs = Q()
                for p in authorized:
                    q_objs |= Q(project__icontains=p)
                queryset = queryset.filter(q_objs)
            else:
                queryset = queryset.none()
        return queryset

    @action(detail=False, methods=["get"], url_path="next-id")
    def next_id(self, request):
        """Return the next auto-generated cc_id (replaces /get_next_clientcode_id)."""
        last = ClientCode.objects.order_by("-id").values("cc_id").first()
        if last and last.get("cc_id"):
            num_part = "".join(filter(str.isdigit, str(last["cc_id"])))
            next_num = int(num_part) + 1 if num_part else 1
        else:
            next_num = 1
        next_id = f"CC-{next_num:04d}"
        return self.ok({"next_clientcode_id": next_id, "next_cc_id": next_id})

    @action(detail=False, methods=["post"], url_path="worktypes-for-clients")
    def worktypes_for_clients(self, request):
        """Return work types grouped by client code (replaces /get_worktypes_for_clients)."""
        client_codes = request.data.get("client_codes", [])
        if isinstance(client_codes, str):
            client_codes = [c.strip() for c in client_codes.split(",") if c.strip()]
        if not client_codes:
            return self.ok({})

        result = {}
        for cc in ClientCode.objects.filter(client_code__in=client_codes):
            wts = [w.strip() for w in (cc.worktypes or "").split("|") if w.strip()]
            result[cc.client_code] = wts
        return self.ok(result)


class ShiftViewSet(BaseMasterViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    search_fields = ["shift_name"]
    ordering_fields = ["start_time", "shift_name"]


class MasterBundleView(EnvelopeMixin, APIView):
    """GET /api/v1/masters/bundle/

    Every dropdown on a page in one cached request, instead of four.
    """

    permission_classes = [IsAuthenticatedEmployee]

    def get(self, request):
        return self.ok(
            {
                "work_types": active_work_types(),
                "projects": active_projects(),
                "client_codes": active_client_codes(),
                "shifts": active_shifts(),
            }
        )

class EmployeeSelectionsView(EnvelopeMixin, APIView):
    """GET /api/v1/masters/selections/ — Returns an employee's assigned selections."""
    
    permission_classes = [IsAuthenticatedEmployee]

    def get(self, request):
        emp_id = request.user.emp_id
        from apps.accounts.models import Employee
        from apps.masters.models import Project, ClientCode
        employee = Employee.objects.filter(employee_id=emp_id).first()
        if not employee:
            return self.error("Employee not found", status=404)
        
        project_ids = [p.strip() for p in (employee.project or '').split('|') if p.strip()]
        client_codes = [c.strip() for c in (employee.client_code or '').split('|') if c.strip()]
        work_types = [w.strip() for w in (employee.work_type or '').split('|') if w.strip()]
        
        project_names = {}
        if project_ids:
            projects = Project.objects.filter(project_id__in=project_ids)
            project_names = {p.project_id: p.project_name for p in projects}
            
        projects_with_names = [{"project_id": pid, "project_name": project_names.get(pid, "Unknown")} for pid in project_ids]
        
        return self.ok({
            'projects': projects_with_names,
            'client_codes': client_codes,
            'work_types': work_types
        })

class ClientCodesForProjectView(EnvelopeMixin, APIView):
    """GET /api/v1/masters/client_codes_for_project/?project=..."""
    permission_classes = [IsAuthenticatedEmployee]

    def get(self, request):
        project_name = request.GET.get('project')
        emp_id = request.user.emp_id
        
        from apps.accounts.models import Employee
        from apps.masters.models import Project
        
        projects = Project.objects.filter(project_id=project_name) | Project.objects.filter(project_name=project_name)
        project_client_codes = []
        for p in projects:
            if p.client_code:
                project_client_codes.extend([c.strip() for c in p.client_code.split('|') if c.strip()])
                
        employee = Employee.objects.filter(employee_id=emp_id).first()
        user_client_codes = [c.strip() for c in (employee.client_code or '').split('|') if c.strip()] if employee else []
        
        common = [c for c in project_client_codes if c in user_client_codes] if user_client_codes else project_client_codes
        return self.ok({'client_codes': common})

class WorkTypesForClientCodeView(EnvelopeMixin, APIView):
    """GET /api/v1/masters/work_types_for_client_code/?client_code=..."""
    permission_classes = [IsAuthenticatedEmployee]

    def get(self, request):
        client_code = request.GET.get('client_code')
        emp_id = request.user.emp_id
        
        from apps.accounts.models import Employee
        from apps.masters.models import ClientCode
        
        client_codes = ClientCode.objects.filter(client_code=client_code)
        cc_wts = []
        for c in client_codes:
            if c.worktypes:
                cc_wts.extend([w.strip() for w in c.worktypes.split('|') if w.strip()])
                
        employee = Employee.objects.filter(employee_id=emp_id).first()
        user_wts = [w.strip() for w in (employee.work_type or '').split('|') if w.strip()] if employee else []
        
        common = [w for w in cc_wts if w in user_wts] if user_wts else cc_wts
        return self.ok({'work_types': common})

class EmpGetProjectsView(EnvelopeMixin, APIView):
    """GET /api/v1/masters/emp_get_projects/"""
    permission_classes = [IsAuthenticatedEmployee]
    def get(self, request):
        projects = active_projects()
        user = request.user
        if getattr(user, 'is_project_admin', False) and not getattr(user, 'is_super_admin', False):
            authorized = set(user.get_authorized_projects())
            projects = [p for p in projects if p['project_id'] in authorized or p['project_name'] in authorized]
        return self.ok({"projects": projects})

class EmpGetClientCodesView(EnvelopeMixin, APIView):
    """POST /api/v1/masters/emp_get_client_codes/"""
    permission_classes = [IsAuthenticatedEmployee]
    def post(self, request):
        data = request.data
        projects = data.get("projects") or data.get("project_ids") or []
        if isinstance(projects, str):
            projects = [p.strip() for p in projects.split("|") if p.strip()]

        from apps.masters.models import Project
        qs = Project.objects.filter(project_id__in=projects) | Project.objects.filter(project_name__in=projects)

        codes_set = set()
        for p in qs:
            if p.client_code:
                codes_set.update([c.strip() for c in p.client_code.split("|") if c.strip()])
        return self.ok({"client_codes": sorted(list(codes_set))})

class EmpGetWorktypesView(EnvelopeMixin, APIView):
    """POST /api/v1/masters/emp_get_worktypes/"""
    permission_classes = [IsAuthenticatedEmployee]
    def post(self, request):
        data = request.data
        client_codes = data.get("client_code") or data.get("client_codes") or []
        if isinstance(client_codes, str):
            client_codes = [c.strip() for c in client_codes.split(",") if c.strip()]

        from apps.masters.models import ClientCode
        qs = ClientCode.objects.filter(client_code__in=client_codes)

        wts_set = set()
        for c in qs:
            if c.worktypes:
                wts_set.update([w.strip() for w in c.worktypes.split("|") if w.strip()])
        return self.ok({"work_types": sorted(list(wts_set)), "worktypes": sorted(list(wts_set))})

class EmpGetShiftsView(EnvelopeMixin, APIView):
    """GET /api/v1/masters/emp_get_shifts/"""
    permission_classes = [IsAuthenticatedEmployee]
    def get(self, request):
        from apps.masters.models import Shift
        shifts = Shift.objects.all().order_by("start_time")
        data = []
        for s in shifts:
            data.append({
                "shift": s.shift_name,
                "startedAt": s.start_time.strftime("%H:%M") if s.start_time else "",
                "endedAt": s.end_time.strftime("%H:%M") if s.end_time else ""
            })
        return self.ok(data)