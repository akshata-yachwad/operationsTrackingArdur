"""Allocation serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.allocations.models import (
    AllocationStatus,
    BatchAllocation,
    OrderHistory,
    Priority,
    OrderRate,
    TitleIndexingSession,
)
from core.validators import validate_emp_id


class AllocationSerializer(serializers.ModelSerializer):
    progress_percent = serializers.FloatField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    client_name = serializers.SerializerMethodField()
    batch_documents = serializers.SerializerMethodField()
    dispatch_date = serializers.SerializerMethodField()

    def get_dispatch_date(self, obj):
        history = OrderHistory.objects.filter(allocation_id=obj.allocation_id, to_status='dispatch').order_by('-created_at').first()
        return history.created_at if history else None

    def get_batch_documents(self, obj):
        docs = []
        if obj.document_name:
            docs.append({"name": obj.document_name, "type": "original"})
        if obj.chain_sheet_name:
            docs.append({"name": obj.chain_sheet_name, "type": "chain_sheet"})
        if obj.search_package_name:
            docs.append({"name": obj.search_package_name, "type": "search_package"})
        if obj.report_name:
            docs.append({"name": obj.report_name, "type": "report"})
        return docs
    # document_file = serializers.FileField(write_only=True, required=False, allow_null=True)

    def get_client_name(self, obj):
        from apps.masters.models import ClientCode
        client = ClientCode.objects.filter(client_code=obj.client_code).first()
        return client.client_name if client else obj.client_code

    class Meta:
        model = BatchAllocation
        fields = [
            "id", "allocation_id", "employee_id", "employee_name",
            "project", "client_code", "client_name", "work_type", "batch", "order_id",
            "quantity", "completed_quantity", "progress_percent",
            "status", "priority", "allocated_at", "due_at", "started_at",
            "completed_at", "allocated_by", "remarks", "is_overdue", "is_open",
            "owner_name", "property_address", "state", "county", "search_type",
            "fees", "margin", "vendor_rate", # "document_file",
            "document_name", "received_date", "eta",
            "employee_comments", "qc_id", "qc_name", "qc_comments", "search_time_taken", "qc_time_taken", "ar_number",
            "batch_documents",
            "chain_sheet_name", "search_package_name", "report_name", "general_instructions",
            "dispatch_date"
        ]
        read_only_fields = [
            "id", "progress_percent", "is_overdue", "is_open",
            "allocated_by", "allocated_at", "started_at", "completed_at",
            "search_time_taken", "qc_time_taken", "ar_number", "dispatch_date"
        ]


class AllocationWriteSerializer(serializers.ModelSerializer):
    allocation_id = serializers.CharField(max_length=50, required=False)
    # employee_id is optional at creation time — orders can be created first
    # and assigned to an employee later via the inline table assignment.
    employee_id = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)
    priority = serializers.ChoiceField(choices=Priority.choices, default=Priority.NORMAL)
    # document_file = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = BatchAllocation
        fields = [
            "allocation_id", "employee_id", "employee_name", "project",
            "client_code", "work_type", "batch", "order_id", "quantity",
            "priority", "due_at", "remarks",
            "owner_name", "property_address", "state", "county", "search_type",
            "fees", "margin", "vendor_rate", # "document_file",
            "document_name", "received_date", "eta", "employee_comments",
            "qc_id", "qc_name", "qc_comments", "ar_number", "general_instructions"
        ]

    def update(self, instance, validated_data):
        # We explicitly specify update_fields to prevent Django from saving the entire row.
        # This fixes a 500 crash on legacy DB rows where `document_file` holds a BLOB instead of a path.
        update_fields = []
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            update_fields.append(attr)
        
        # If QC is assigned to an order that was in COMPLETED (Search Complete) status, transition to READY_FOR_QC
        if "qc_id" in validated_data and validated_data["qc_id"]:
            if instance.status == AllocationStatus.COMPLETED:
                from_status = instance.status
                instance.status = AllocationStatus.READY_FOR_QC
                update_fields.append("status")
                try:
                    from core.utils import now_ist
                    req = self.context.get("request")
                    emp_actor = req.user.emp_id if req and hasattr(req, "user") and hasattr(req.user, "emp_id") else "admin"
                    OrderHistory.objects.create(
                        allocation_id=instance.allocation_id,
                        order_id=instance.order_id,
                        employee_id=instance.employee_id,
                        action="status_ready_for_qc",
                        from_status=from_status,
                        to_status=AllocationStatus.READY_FOR_QC,
                        remarks=f"QC assigned to {instance.qc_name or instance.qc_id}",
                        performed_by=emp_actor,
                        created_at=now_ist(),
                    )
                except Exception:
                    pass
        
        if update_fields:
            instance.save(update_fields=update_fields)
        return instance

    def validate_employee_id(self, value: str) -> str:
        # Only validate when a non-empty value is provided.
        # Empty means the order is being created without an assignment yet.
        if not value:
            return value
        from apps.accounts.models import Employee

        if not Employee.objects.filter(employee_id=value, status="active").exists():
            raise serializers.ValidationError("No active employee with that ID.")
        return value

    def validate_due_at(self, value):
        from core.timezone import now_ist

        if value and value < now_ist():
            raise serializers.ValidationError("The due date cannot be in the past.")
        return value


class AllocationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AllocationStatus.choices)
    completed_quantity = serializers.IntegerField(
        min_value=0, required=False, allow_null=True, default=None
    )
    remarks = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    employee_comments = serializers.CharField(required=False, allow_blank=True, default="")
    qc_comments = serializers.CharField(required=False, allow_blank=True, default="")
    # chain_sheet = serializers.FileField(required=False, allow_null=True)
    # search_package = serializers.FileField(required=False, allow_null=True)
    # report = serializers.FileField(required=False, allow_null=True)


class ReassignSerializer(serializers.Serializer):
    employee_id = serializers.CharField(max_length=20, validators=[validate_emp_id])
    employee_name = serializers.CharField(max_length=100, required=False,
                                          allow_blank=True, default="")


class OrderHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderHistory
        fields = [
            "id", "allocation_id", "order_id", "employee_id", "action",
            "from_status", "to_status", "quantity", "remarks",
            "performed_by", "created_at",
        ]
        read_only_fields = fields


class OrderRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRate
        fields = [
            "id", "order_type", "state", "stateabr", "county",
            "vendor_rts", "eta_rts", "vendor_slt", "eta_slt", "remark",
        ]
        read_only_fields = fields


class TitleIndexingSessionSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = TitleIndexingSession
        fields = [
            "id", "employee_id", "employee_name", "project", "client_code", "work_type",
            "started_at", "completed_at", "time_taken",
            "work_units_completed", "status"
        ]

    def get_employee_name(self, obj):
        from apps.accounts.models import Employee
        emp = Employee.objects.filter(employee_id=obj.employee_id).first()
        return emp.name if emp else obj.employee_id
