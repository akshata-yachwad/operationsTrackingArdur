"""Allocation endpoints."""

from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action

from apps.allocations.models import BatchAllocation, OrderHistory, OrderRate
from apps.allocations.serializers import (
    AllocationSerializer,
    AllocationStatusSerializer,
    AllocationWriteSerializer,
    OrderHistorySerializer,
    OrderRateSerializer,
    ReassignSerializer,
)
from apps.allocations.services import AllocationService
from core.mixins import EnvelopeMixin, ServiceMixin
from core.permissions import IsAdminOrSupervisor, IsAuthenticatedEmployee, IsManager


class AllocationViewSet(ServiceMixin, EnvelopeMixin, viewsets.ModelViewSet):
    """/api/v1/allocations/

    Employees see and progress their own work. Creating, reassigning and
    cancelling are supervisor actions.
    """

    serializer_class = AllocationSerializer
    service_class = AllocationService
    permission_classes = [IsAuthenticatedEmployee]
    search_fields = ["allocation_id", "order_id", "batch", "employee_id", "project"]
    ordering_fields = ["allocated_at", "due_at", "priority", "status"]
    ordering = ["-allocated_at"]
    lookup_field = "allocation_id"

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy",
                           "reassign", "cancel"):
            return [IsManager()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AllocationWriteSerializer
        return AllocationSerializer

    def get_queryset(self):
        queryset = BatchAllocation.objects.visible_to(self.request.user)

        params = self.request.query_params
        if emp_id := params.get("emp_id"):
            queryset = queryset.filter(employee_id=emp_id)
        if status_value := params.get("status"):
            queryset = queryset.filter(status=status_value)
        if params.get("open") == "true":
            queryset = queryset.open()
        if params.get("overdue") == "true":
            queryset = queryset.overdue()
        if project := params.get("project"):
            queryset = queryset.filter(project=project)
        date_val = params.get("date")
        print(f"DEBUG: Received date_val = {date_val!r}, Total orders before filter = {queryset.count()}")
        if date_val:
            queryset = queryset.filter(allocated_at__startswith=date_val)
            print(f"DEBUG: Orders after filter = {queryset.count()}")
        return queryset

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        
        # Handle uploaded document(s) sent from the frontend
        # documents = self.request.FILES.getlist('documents[]')
        # if documents:
        #     # We currently only support saving one document in the BatchAllocation model.
        #     data['document_file'] = documents[0]
        #     data['document_name'] = documents[0].name
            
        serializer.instance = self.service.create(data)

    def perform_destroy(self, instance):
        self.service.cancel(instance, reason="Cancelled by supervisor")

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, allocation_id=None):
        """The URL kwarg is ``allocation_id`` (lookup_field above), not
        ``pk`` — every detail action here takes that kwarg name, not the
        DRF default, or the router 500s with a TypeError before the view
        body ever runs."""
        serializer = AllocationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocation = self.service.update_status(self.get_object().pk, **serializer.validated_data)
        return self.ok(AllocationSerializer(allocation).data)

    @action(detail=True, methods=["post"])
    def reassign(self, request, allocation_id=None):
        serializer = ReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ReassignSerializer's wire field is "employee_id" (consistent with
        # AllocationWriteSerializer), but AllocationService.reassign() takes
        # "new_employee_id" — map explicitly rather than **kwargs-splatting
        # a mismatch into a TypeError.
        allocation = self.service.reassign(
            self.get_object(),
            new_employee_id=serializer.validated_data["employee_id"],
            employee_name=serializer.validated_data.get("employee_name", ""),
        )
        return self.ok(AllocationSerializer(allocation).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, allocation_id=None):
        allocation = self.service.cancel(
            self.get_object(), reason=request.data.get("reason", "")
        )
        return self.ok(AllocationSerializer(allocation).data)

    # @action(detail=True, methods=["get"])
    # def download(self, request, allocation_id=None):
    #     allocation = self.get_object()
    #     
    #     doc_type = request.query_params.get("doc", "document")
    #     if doc_type == "chain_sheet":
    #         file_field = allocation.chain_sheet
    #         file_name = allocation.chain_sheet_name or f"order_{allocation.allocation_id}_chain_sheet.bin"
    #     elif doc_type == "search_package":
    #         file_field = allocation.search_package
    #         file_name = allocation.search_package_name or f"order_{allocation.allocation_id}_search_package.bin"
    #     elif doc_type == "report":
    #         file_field = allocation.report
    #         file_name = allocation.report_name or f"order_{allocation.allocation_id}_report.bin"
    #     else:
    #         file_field = allocation.document_file
    #         file_name = allocation.document_name or f"order_{allocation.allocation_id}_document.bin"
    #         
    #     if not file_field:
    #         from core.exceptions import NotFoundError
    #         raise NotFoundError("No document attached to this order.")
    #         
    #     try:
    #         from django.http import FileResponse
    #         response = FileResponse(file_field.open('rb'), as_attachment=True, filename=file_name)
    #         return response
    #     except Exception as e:
    #         from core.exceptions import NotFoundError
    #         import logging
    #         logger = logging.getLogger(__name__)
    #         logger.error(f"Error opening file {getattr(file_field, 'name', 'unknown')}: {e}")
    #         raise NotFoundError("The attached document could not be found on the server.")

    @action(detail=True, methods=["get"])
    def history(self, request, allocation_id=None):
        allocation = self.get_object()
        rows = OrderHistory.objects.filter(allocation_id=allocation.allocation_id)
        return self.ok(OrderHistorySerializer(rows, many=True).data)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        """The caller's actionable allocations, based on their role."""
        from django.db.models import Q
        
        emp_id = request.user.emp_id
        base_qs = BatchAllocation.objects.open_or_completed_today()
        
        # User is the searcher
        cond_searcher = Q(employee_id=emp_id)
        
        # User is the QC person, only show when it reaches QC or later
        from apps.allocations.models import AllocationStatus
        cond_qc = Q(qc_id=emp_id) & Q(status__in=[
            AllocationStatus.READY_FOR_QC,
            AllocationStatus.QC_IN_PROGRESS,
            AllocationStatus.COMPLETED,
        ])
        
        queryset = base_qs.filter(cond_searcher | cond_qc).exclude(status=AllocationStatus.DISPATCH)
        return self.ok(AllocationSerializer(queryset, many=True).data)

    @action(detail=False, methods=["get"], url_path="next_ar_number")
    def next_ar_number(self, request):
        """Return the next auto-generated ar_number."""
        return self.ok({"next_ar_number": BatchAllocation.generate_ar_number()})

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Returns client-wise aggregation of order statuses for a given date."""
        from django.db.models import Count, Q
        from apps.allocations.models import AllocationStatus
        
        queryset = self.get_queryset()
        
        # We assume get_queryset already applied the date filter (if provided)
        # However, get_queryset limits date using `startswith`, we might want to group by client_code.
        summary_data = queryset.values('client_code').annotate(
            total=Count('id'),
            assigned=Count('id', filter=Q(employee_id__gt='')),
            not_assigned=Count('id', filter=Q(employee_id='')),
            search_completed=Count('id', filter=Q(status__in=[
                AllocationStatus.READY_FOR_QC, 
                AllocationStatus.QC_IN_PROGRESS, 
                AllocationStatus.COMPLETED, 
                AllocationStatus.DISPATCH
            ])),
            qc_completed=Count('id', filter=Q(status__in=[
                AllocationStatus.COMPLETED, 
                AllocationStatus.DISPATCH
            ])),
            dispatched=Count('id', filter=Q(status=AllocationStatus.DISPATCH)),
            cancelled_hold=Count('id', filter=Q(status__in=[
                AllocationStatus.CANCELLED,
                AllocationStatus.ON_HOLD
            ]))
        ).order_by('client_code')
        
        # Now fetch client names
        from apps.masters.models import ClientCode
        client_codes = [s['client_code'] for s in summary_data]
        clients = {c.client_code: c.client_name for c in ClientCode.objects.filter(client_code__in=client_codes)}
        
        for item in summary_data:
            item['client_name'] = clients.get(item['client_code'], item['client_code'])
            
        return self.ok(list(summary_data))

class OrderHistoryViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    """/api/v1/allocations/history/ — the audit trail, supervisors only."""

    serializer_class = OrderHistorySerializer
    permission_classes = [IsAdminOrSupervisor]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = OrderHistory.objects.all()
        if allocation_id := self.request.query_params.get("allocation_id"):
            queryset = queryset.filter(allocation_id=allocation_id)
        if emp_id := self.request.query_params.get("emp_id"):
            queryset = queryset.filter(employee_id=emp_id)
        return queryset


class OrderRateViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    """/api/v1/allocations/rates/ — vendor rates and slas."""
    
    serializer_class = OrderRateSerializer
    permission_classes = [IsAuthenticatedEmployee]
    search_fields = ["order_type", "state", "county"]

    def get_queryset(self):
        queryset = OrderRate.objects.all()
        if order_type := self.request.query_params.get("order_type"):
            queryset = queryset.filter(order_type=order_type)
        if state := self.request.query_params.get("state"):
            queryset = queryset.filter(state=state)
        if county := self.request.query_params.get("county"):
            queryset = queryset.filter(county=county)
        return queryset

    @action(detail=False, methods=["get"])
    def order_types(self, request):
        # OrderRate.Meta.ordering is ["order_type", "state", "county"] —
        # without clearing it, Django pulls state/county into the SELECT to
        # satisfy the implicit ORDER BY, and distinct() then dedupes on the
        # (order_type, state, county) tuple instead of order_type alone. The
        # same "Full Search" for two different counties would come back
        # twice. order_by() with no args drops the default ordering.
        types = (
            OrderRate.objects.exclude(order_type__isnull=True).exclude(order_type="")
            .order_by().values_list("order_type", flat=True).distinct()
        )
        return self.ok(
            sorted(types) or ["Current Owner", "Two Owner", "Full Search", "Update Search", "Document Retrieval"]
        )

    @action(detail=False, methods=["get"], url_path="states/(?P<order_type>[^/.]+)")
    def states(self, request, order_type=None):
        states = (
            OrderRate.objects.filter(order_type=order_type)
            .exclude(state__isnull=True).exclude(state="")
            .order_by().values_list("state", flat=True).distinct()
        )
        return self.ok(sorted(states))

    @action(detail=False, methods=["get"], url_path="counties/(?P<order_type>[^/.]+)/(?P<state>[^/.]+)")
    def counties(self, request, order_type=None, state=None):
        counties = (
            OrderRate.objects.filter(order_type=order_type, state=state)
            .exclude(county__isnull=True).exclude(county="")
            .order_by().values_list("county", flat=True).distinct()
        )
        return self.ok(sorted(counties))


from apps.allocations.models import TitleIndexingSession
from apps.allocations.serializers import TitleIndexingSessionSerializer
from rest_framework.decorators import action
from datetime import datetime
from core.timezone import now_ist
from core.mixins import EnvelopeMixin
from rest_framework import viewsets, status
from rest_framework.response import Response

class TitleIndexingSessionViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    """API for managing Title Indexing Sessions."""
    queryset = TitleIndexingSession.objects.all()
    serializer_class = TitleIndexingSessionSerializer
    permission_classes = [IsAuthenticatedEmployee]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_team_lead:
            return qs
        return qs.filter(employee_id=self.request.user.emp_id)

    @action(detail=False, methods=["post"], url_path="start")
    def start_session(self, request):
        """Starts a new Title Indexing session."""
        emp_id = request.user.emp_id
        
        # Check if there's already an in-progress session
        active_session = TitleIndexingSession.objects.filter(
            employee_id=emp_id, status='IN_PROGRESS'
        ).first()
        
        if active_session:
            return Response({"error": "An active indexing session is already running."}, status=status.HTTP_400_BAD_REQUEST)

        client_code = request.data.get("client_code", "")
        work_type = request.data.get("work_type", "")
        
        if not client_code or not work_type:
            return Response({"error": "Client code and Work type are required."}, status=status.HTTP_400_BAD_REQUEST)

        session = TitleIndexingSession.objects.create(
            employee_id=emp_id,
            client_code=client_code,
            work_type=work_type,
            status='IN_PROGRESS'
        )
        
        try:
            from apps.presence.services import PresenceService
            PresenceService().recompute(emp_id)
        except Exception:
            pass

        return self.ok(TitleIndexingSessionSerializer(session).data)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit_session(self, request, pk=None):
        """Submits the session with completed work units."""
        session = self.get_object()
        
        if session.status == 'COMPLETED':
            return Response({"error": "Session is already completed."}, status=status.HTTP_400_BAD_REQUEST)

        work_units = request.data.get("work_units_completed")
        if work_units is None:
            return Response({"error": "work_units_completed is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            work_units = int(work_units)
        except ValueError:
            return Response({"error": "work_units_completed must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        session.work_units_completed = work_units
        session.completed_at = now_ist()
        session.status = 'COMPLETED'
        
        # Calculate time taken
        diff = session.completed_at - session.started_at
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        session.time_taken = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        session.save()

        try:
            from apps.presence.services import PresenceService
            PresenceService().recompute(session.employee_id)
        except Exception:
            pass

        return self.ok(TitleIndexingSessionSerializer(session).data)

    @action(detail=False, methods=["get"], url_path="my_active")
    def my_active(self, request):
        """Returns the currently active session for the employee, if any."""
        session = TitleIndexingSession.objects.filter(
            employee_id=request.user.emp_id, status='IN_PROGRESS'
        ).first()
        
        if session:
            return self.ok(TitleIndexingSessionSerializer(session).data)
        return self.ok(None)