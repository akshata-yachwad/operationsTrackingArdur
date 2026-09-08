"""Batch allocation and order history models."""

from __future__ import annotations

from django.db import models

from core.managers import OwnedQuerySet
from core.models import legacy_managed
from core.timezone import now_ist


class AllocationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SEARCH_IN_PROGRESS = "search_in_progress", "Search In Progress"
    READY_FOR_QC = "ready_for_qc", "Ready for QC"
    QC_IN_PROGRESS = "qc_in_progress", "QC In Progress"
    COMPLETED = "completed", "Completed"
    DISPATCH = "dispatch", "Dispatch"
    ON_HOLD = "on_hold", "On hold"
    CANCELLED = "cancelled", "Cancelled"


class Priority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class AllocationQuerySet(OwnedQuerySet):
    owner_field = "employee_id"

    def pending(self):
        return self.filter(status=AllocationStatus.PENDING)

    def for_employee(self, emp_id: str):
        from django.db.models import Q
        return self.filter(Q(employee_id=emp_id) | Q(qc_id=emp_id))

    def open(self):
        return self.filter(
            status__in=(AllocationStatus.PENDING, AllocationStatus.SEARCH_IN_PROGRESS, AllocationStatus.READY_FOR_QC, AllocationStatus.QC_IN_PROGRESS)
        )

    def open_or_completed_today(self):
        from django.db.models import Q
        import datetime
        today_start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + datetime.timedelta(days=1)
        return self.filter(
            Q(status__in=(AllocationStatus.PENDING, AllocationStatus.SEARCH_IN_PROGRESS, AllocationStatus.READY_FOR_QC, AllocationStatus.QC_IN_PROGRESS)) |
            Q(status__in=[AllocationStatus.COMPLETED, AllocationStatus.DISPATCH], completed_at__gte=today_start, completed_at__lt=today_end)
        )

    def due_within(self, hours: int):
        """Open allocations whose SLA lands inside the window. Drives the
        breach-warning beat task."""
        from datetime import timedelta

        return self.open().filter(
            due_at__isnull=False,
            due_at__lte=now_ist() + timedelta(hours=hours),
            due_at__gt=now_ist(),
        )

    def overdue(self):
        return self.open().filter(due_at__isnull=False, due_at__lt=now_ist())


class BatchAllocation(models.Model):
    """A batch of work assigned to an employee."""

    id = models.AutoField(primary_key=True)
    allocation_id = models.CharField(max_length=50, unique=True, db_index=True)
    employee_id = models.CharField(max_length=20, db_index=True)
    employee_name = models.CharField(max_length=100, blank=True, default="")

    project = models.CharField(max_length=150, blank=True, default="")
    client_code = models.CharField(max_length=50, blank=True, default="")
    work_type = models.CharField(max_length=100, blank=True, default="")
    batch = models.CharField(max_length=100, blank=True, default="")
    order_id = models.CharField(max_length=100, blank=True, default="", db_index=True)

    # Added fields expected by frontend
    owner_name = models.CharField(max_length=255, blank=True, null=True)
    property_address = models.CharField(max_length=500, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    county = models.CharField(max_length=100, blank=True, null=True)
    search_type = models.CharField(max_length=100, blank=True, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    margin = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    vendor_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    document_file = models.FileField(upload_to="order_docs/", max_length=255, blank=True, null=True)
    document_name = models.CharField(max_length=255, blank=True, null=True)
    received_date = models.DateTimeField(blank=True, null=True)
    eta = models.DateTimeField(blank=True, null=True)
    general_instructions = models.TextField(blank=True, null=True)

    quantity = models.IntegerField(default=0)
    completed_quantity = models.IntegerField(default=0)
    
    # Employee uploaded files
    chain_sheet = models.FileField(upload_to="employee_docs/", blank=True, null=True)
    chain_sheet_name = models.CharField(max_length=255, blank=True, null=True)
    search_package = models.FileField(upload_to="employee_docs/", blank=True, null=True)
    search_package_name = models.CharField(max_length=255, blank=True, null=True)
    report = models.FileField(upload_to="employee_docs/", blank=True, null=True)
    report_name = models.CharField(max_length=255, blank=True, null=True)

    status = models.CharField(
        max_length=20, choices=AllocationStatus.choices,
        default=AllocationStatus.PENDING, db_index=True,
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )

    allocated_at = models.DateTimeField(default=now_ist)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    allocated_by = models.CharField(max_length=20, blank=True, default="")
    remarks = models.CharField(max_length=500, blank=True, default="")
    employee_comments = models.TextField(blank=True, default="")
    qc_id = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    qc_name = models.CharField(max_length=100, blank=True, null=True)
    qc_comments = models.TextField(blank=True, null=True)
    search_time_taken = models.CharField(max_length=100, blank=True, default="")
    qc_time_taken = models.CharField(max_length=100, blank=True, default="")
    qc_started_at = models.DateTimeField(null=True, blank=True)
    ar_number = models.CharField(max_length=20, blank=True, null=True, unique=True)
    sla_notified = models.BooleanField(default=False)

    objects = AllocationQuerySet.as_manager()

    @classmethod
    def generate_ar_number(cls) -> str:
        last_allocation = cls.objects.exclude(ar_number__isnull=True).exclude(ar_number="").order_by("-pk").first()
        if not last_allocation or not last_allocation.ar_number.startswith("AT00M"):
            return "AT00M001"
        try:
            num = int(last_allocation.ar_number.replace("AT00M", ""))
            return f"AT00M{num + 1:03d}"
        except ValueError:
            return "AT00M001"

    class Meta:
        managed = legacy_managed()
        db_table = "ot_batch_allocations"
        ordering = ["-allocated_at"]
        indexes = [
            models.Index(fields=["employee_id", "status"], name="ix_alloc_emp_status"),
            models.Index(fields=["status", "due_at"], name="ix_alloc_status_due"),
        ]

    def __str__(self) -> str:
        return f"{self.allocation_id} → {self.employee_id} ({self.status})"

    @property
    def is_open(self) -> bool:
        return self.status in (AllocationStatus.PENDING, AllocationStatus.SEARCH_IN_PROGRESS, AllocationStatus.QC_IN_PROGRESS)

    @property
    def progress_percent(self) -> float:
        if not self.quantity:
            return 0.0
        return round(min(self.completed_quantity / self.quantity * 100, 100), 1)

    @property
    def is_overdue(self) -> bool:
        return bool(self.due_at) and self.is_open and self.due_at < now_ist()


class OrderHistory(models.Model):
    """Append-only audit trail of what happened to an allocation.

    Never updated, only inserted — an audit trail you can edit is not one.
    """

    id = models.AutoField(primary_key=True)
    allocation_id = models.CharField(max_length=50, db_index=True)
    order_id = models.CharField(max_length=100, blank=True, default="", db_index=True)
    employee_id = models.CharField(max_length=20, blank=True, default="", db_index=True)
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20, blank=True, default="")
    quantity = models.IntegerField(null=True, blank=True)
    remarks = models.CharField(max_length=500, blank=True, default="")
    performed_by = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(default=now_ist, db_index=True)

    class Meta:
        managed = legacy_managed()
        db_table = "ot_orders_history"
        ordering = ["-created_at"]
        verbose_name_plural = "order history"

    def __str__(self) -> str:
        return f"{self.allocation_id}: {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class OrderRate(models.Model):
    """Vendor rates and SLAs for order types across states and counties."""

    id = models.AutoField(primary_key=True)
    order_type = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    stateabr = models.CharField(max_length=100, blank=True, default="")
    county = models.CharField(max_length=100)
    vendor_rts = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    eta_rts = models.IntegerField(blank=True, null=True)
    vendor_slt = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    eta_slt = models.IntegerField(blank=True, null=True)
    remark = models.CharField(max_length=250, blank=True, default="")

    class Meta:
        managed = legacy_managed()
        db_table = "ot_order_rates"
        ordering = ["order_type", "state", "county"]

    def __str__(self) -> str:
        return f"{self.order_type} - {self.state} - {self.county}"


class TitleIndexingSession(models.Model):
    """Tracking sessions and work units for Title Indexing."""

    id = models.AutoField(primary_key=True)
    employee_id = models.CharField(max_length=20, db_index=True)
    project = models.CharField(max_length=150, default="Title Indexing")
    client_code = models.CharField(max_length=50)
    work_type = models.CharField(max_length=100)
    
    # Session tracking
    started_at = models.DateTimeField(default=now_ist)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken = models.CharField(max_length=100, blank=True)
    
    # Indexing specific metrics
    work_units_completed = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, 
        choices=[('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed')],
        default='IN_PROGRESS'
    )

    class Meta:
        # Not setting managed = legacy_managed() since this is a new table
        db_table = "ot_title_indexing_sessions"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Session {self.id} for {self.employee_id} ({self.status})"
