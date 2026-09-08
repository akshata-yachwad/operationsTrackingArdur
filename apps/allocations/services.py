"""Allocation business rules.

Creating and reassigning allocations is a supervisor action — that is the fix
for "an employee can create allocations for themselves".
"""

from __future__ import annotations

from django.db import transaction

from apps.allocations.models import (
    AllocationStatus,
    BatchAllocation,
    OrderHistory,
)
from core.exceptions import ConflictError, ValidationError
from core.services import BaseService
from core.timezone import now_ist


class AllocationService(BaseService):
    """Assign, progress and complete allocations."""

    @transaction.atomic
    def create(self, data: dict) -> BatchAllocation:
        self.require_supervisor("Only a supervisor can allocate work.")

        allocation_id = data.get("allocation_id")
        if not allocation_id:
            last = BatchAllocation.objects.order_by("-pk").first()
            if not last or not last.allocation_id.startswith("Task-"):
                allocation_id = "Task-000001"
            else:
                try:
                    num = int(last.allocation_id.replace("Task-", ""))
                    allocation_id = f"Task-{num + 1:06d}"
                except ValueError:
                    allocation_id = "Task-000001"
            data["allocation_id"] = allocation_id
        elif BatchAllocation.objects.filter(allocation_id=allocation_id).exists():
            raise ConflictError(f"Allocation {allocation_id} already exists.")

        if not data.get("ar_number"):
            data["ar_number"] = BatchAllocation.generate_ar_number()

        allocation = BatchAllocation.objects.create(
            allocated_by=self.actor_emp_id or "",
            allocated_at=now_ist(),
            **data,
        )

        self._record(allocation, "allocated", to_status=allocation.status)
        self.log("allocation_created", id=allocation.allocation_id)
        self.on_commit(lambda: self._notify_assignee(allocation))
        return allocation

    @transaction.atomic
    def reassign(self, allocation: BatchAllocation, new_employee_id: str,
                 employee_name: str = "") -> BatchAllocation:
        self.require_supervisor("Only a supervisor can reassign work.")

        if allocation.status == AllocationStatus.COMPLETED:
            raise ConflictError("A completed allocation cannot be reassigned.")

        previous = allocation.employee_id
        allocation.employee_id = new_employee_id
        allocation.employee_name = employee_name
        allocation.save(update_fields=["employee_id", "employee_name"])

        self._record(allocation, "reassigned", remarks=f"from {previous} to {new_employee_id}")
        self.log("allocation_reassigned", id=allocation.allocation_id, to=new_employee_id)
        self.on_commit(lambda: self._notify_assignee(allocation))
        return allocation

    @transaction.atomic
    def update_status(self, allocation_pk: int, status: str,
                      completed_quantity: int | None = None,
                      remarks: str = "",
                      employee_comments: str = "",
                      qc_comments: str = "",
                      chain_sheet=None,
                      search_package=None,
                      report=None) -> BatchAllocation:
        allocation = self.require_found(
            BatchAllocation.objects.select_for_update().filter(pk=allocation_pk).first(),
            "No such allocation.",
        )

        if not (self.actor and (self.actor.is_supervisor or self.actor_emp_id in (allocation.employee_id, allocation.qc_id))):
            raise ConflictError("That allocation is assigned to someone else.")

        if status not in AllocationStatus.values:
            raise ValidationError(f"'{status}' is not a valid status.")

        if allocation.status == AllocationStatus.COMPLETED and not (
            self.actor and self.actor.is_supervisor
        ):
            raise ConflictError("A completed allocation can only be reopened by a supervisor.")

        previous = allocation.status
        allocation.status = status

        if completed_quantity is not None:
            if completed_quantity < 0 or completed_quantity > allocation.quantity:
                raise ValidationError(
                    f"Completed quantity must be between 0 and {allocation.quantity}."
                )
            allocation.completed_quantity = completed_quantity

        if status == AllocationStatus.SEARCH_IN_PROGRESS and not allocation.started_at:
            allocation.started_at = now_ist()
            
        if status == AllocationStatus.QC_IN_PROGRESS and not allocation.qc_started_at:
            allocation.qc_started_at = now_ist()

        if status in (AllocationStatus.COMPLETED, AllocationStatus.READY_FOR_QC, AllocationStatus.DISPATCH) and not allocation.completed_at:
            allocation.completed_at = now_ist()
            if allocation.started_at:
                delta = allocation.completed_at - allocation.started_at
                total_seconds = int(delta.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                parts = []
                if hours > 0:
                    parts.append(f"{hours}h")
                if minutes > 0 or hours == 0:
                    parts.append(f"{minutes}m")
                allocation.search_time_taken = " ".join(parts)

        if status == AllocationStatus.DISPATCH and allocation.qc_started_at and not allocation.qc_time_taken:
            delta = now_ist() - allocation.qc_started_at
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            parts = []
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0 or hours == 0:
                parts.append(f"{minutes}m")
            allocation.qc_time_taken = " ".join(parts)

        if remarks:
            allocation.remarks = remarks[:500]
            
        if employee_comments:
            allocation.employee_comments = employee_comments

        if qc_comments:
            allocation.qc_comments = qc_comments

        # if chain_sheet:
        #     allocation.chain_sheet = chain_sheet
        #     allocation.chain_sheet_name = chain_sheet.name
        # if search_package:
        #     allocation.search_package = search_package
        #     allocation.search_package_name = search_package.name
        # if report:
        #     allocation.report = report
        #     allocation.report_name = report.name

        update_fields = [
            "status", "completed_quantity", "started_at", "completed_at", 
            "remarks", "employee_comments", "qc_comments", "search_time_taken",
            "qc_time_taken", "qc_started_at"
        ]
        # if chain_sheet:
        #     update_fields.extend(['chain_sheet', 'chain_sheet_name'])
        # if search_package:
        #     update_fields.extend(['search_package', 'search_package_name'])
        # if report:
        #     update_fields.extend(['report', 'report_name'])

        allocation.save(update_fields=update_fields)

        self._record(
            allocation, f"status_{status}", from_status=previous,
            to_status=status, quantity=allocation.completed_quantity, remarks=remarks,
        )
        self.log("allocation_status", id=allocation.allocation_id, status=status)
        self.on_commit(lambda: self._announce(allocation))
        return allocation

    @transaction.atomic
    def cancel(self, allocation: BatchAllocation, reason: str = "") -> BatchAllocation:
        self.require_supervisor("Only a supervisor can cancel an allocation.")

        if allocation.status == AllocationStatus.COMPLETED:
            raise ConflictError("A completed allocation cannot be cancelled.")

        previous = allocation.status
        allocation.status = AllocationStatus.CANCELLED
        
        cancel_note = f"[CANCEL REASON]: {reason}" if reason else "[CANCELLED]"
        if allocation.remarks and cancel_note not in allocation.remarks:
            allocation.remarks = f"{allocation.remarks}\n\n{cancel_note}"[:500]
        else:
            allocation.remarks = cancel_note[:500]
            
        allocation.save(update_fields=["status", "remarks"])

        self._record(allocation, "cancelled", from_status=previous,
                     to_status=AllocationStatus.CANCELLED, remarks=reason)
        self.on_commit(lambda: self._announce(allocation))
        return allocation

    # ── internals ────────────────────────────────────────────

    def _record(self, allocation: BatchAllocation, action: str, **fields) -> None:
        OrderHistory.objects.create(
            allocation_id=allocation.allocation_id,
            order_id=allocation.order_id,
            employee_id=allocation.employee_id,
            action=action,
            performed_by=self.actor_emp_id or "system",
            created_at=now_ist(),
            **fields,
        )

    @staticmethod
    def _notify_assignee(allocation: BatchAllocation) -> None:
        from apps.notifications.services import NotificationService

        NotificationService().notify(
            recipients=[allocation.employee_id],
            notif_type="allocation.assigned",
            context={
                "task_id": allocation.allocation_id,
                "ar_number": allocation.ar_number,
                "project": allocation.project,
                "quantity": allocation.quantity,
            }
        )
        # Also push the live event so the user-dashboard panel refreshes
        # immediately without waiting for the notification to arrive.
        AllocationService._announce_assigned(allocation)

    @staticmethod
    def _announce_assigned(allocation: BatchAllocation) -> None:
        from apps.realtime.groups import user_group
        from core.events import publish

        publish(
            group=user_group(allocation.employee_id),
            event="allocation.assigned",
            data={
                "id": allocation.id,
                "allocation_id": allocation.allocation_id,
                "ar_number": allocation.ar_number,
                "status": allocation.status,
                "project": allocation.project,
                "client_code": allocation.client_code,
                "work_type": allocation.work_type,
            },
        )

    @staticmethod
    def _announce(allocation: BatchAllocation) -> None:
        from apps.realtime.groups import user_group
        from core.events import publish

        publish(
            group=user_group(allocation.employee_id),
            event="allocation.updated",
            data={
                "id": allocation.id,
                "allocation_id": allocation.allocation_id,
                "status": allocation.status,
                "progress_percent": allocation.progress_percent,
            },
        )
