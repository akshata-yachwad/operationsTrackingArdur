"""Work session business rules.

The rule that matters most in this file: **every timestamp comes from the
server.** The client may send ``end_time``; the serializer drops it and the
service calls ``now_ist()``. A browser clock is attacker-controlled, and
anything derived from it lands in a report someone gets paid against.

Pause/resume/delete are implemented here rather than left as dead endpoints —
the UI has buttons for them.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.tracking.models import SessionState, Target, WorkSession
from core.events import publish
from core.exceptions import ConflictError, ValidationError
from core.services import BaseService
from core.timezone import elapsed_seconds, now_ist, today_ist


class WorkSessionService(BaseService):
    """Start, pause, resume, end and delete work sessions."""

    @transaction.atomic
    def start_session(
        self,
        *,
        project: str,
        work_type: str,
        client_code: str = "",
        batch: str = "",
        allocation_id: str | None = None,
    ) -> WorkSession:
        actor = self.require_actor()

        # One open session per person. The row lock is what makes this a real
        # guarantee rather than a hopeful check — two clicks 40ms apart on a
        # flaky connection both see "nothing open" without it.
        already_open = (
            WorkSession.objects.select_for_update()
            .filter(emp_id=actor.emp_id, end_time__isnull=True,
                    is_started=SessionState.RUNNING)
            .exists()
        )
        if already_open:
            raise ConflictError(
                "You already have a work session running. End it before starting another."
            )

        try:
            session = WorkSession.objects.create(
                emp_id=actor.emp_id,
                name=actor.display_name,
                project=project,
                work_type=work_type,
                client_code=client_code,
                batch=batch,
                allocation_id=allocation_id,
                start_time=now_ist(),
                is_started=SessionState.RUNNING,
            )
        except IntegrityError as exc:
            # uq_one_open_session_per_emp caught a race the lock did not,
            # because both transactions started before either had inserted.
            raise ConflictError(
                "You already have a work session running. End it before starting another."
            ) from exc

        self.log("session_started", id=session.id, project=project)
        self.on_commit(lambda: self._announce(session, "work.session.started"))
        return session

    @transaction.atomic
    def pause_session(self, session_id: int) -> WorkSession:
        session = self._locked_open_session(session_id)

        if session.is_paused:
            raise ConflictError("This session is already paused.")

        session.is_paused = True
        session.paused_at = now_ist()
        session.paused_by = self.actor_emp_id or ""
        session.save(update_fields=["is_paused", "paused_at", "paused_by"])

        self.log("session_paused", id=session.id)
        self.on_commit(lambda: self._announce(session, "work.session.paused"))
        return session

    @transaction.atomic
    def resume_session(self, session_id: int) -> WorkSession:
        session = self._locked_open_session(session_id)

        if not session.is_paused:
            raise ConflictError("This session is not paused.")

        # Accumulate the pause into paused_elapsed rather than moving
        # start_time — moving the start would rewrite when the work began.
        paused_for = elapsed_seconds(session.paused_at) if session.paused_at else 0.0
        session.paused_elapsed = (session.paused_elapsed or 0) + paused_for
        session.is_paused = False
        session.paused_at = None
        session.paused_by = ""
        session.save(update_fields=["is_paused", "paused_at", "paused_by", "paused_elapsed"])

        self.log("session_resumed", id=session.id, paused_for=round(paused_for))
        self.on_commit(lambda: self._announce(session, "work.session.resumed"))
        return session

    @transaction.atomic
    def end_session(
        self,
        session_id: int,
        *,
        review: str = "",
        chain_sheet=None,
        search_package=None,
        report=None,
        employee_comments: str = "",
    ) -> WorkSession:
        session = self._locked_open_session(session_id)

        end = now_ist()  # server clock, always

        # A session ended while paused should not be billed for the pause.
        paused_elapsed = float(session.paused_elapsed) if session.paused_elapsed else 0.0
        if session.is_paused and session.paused_at:
            paused_elapsed += elapsed_seconds(session.paused_at, end)

        gross = elapsed_seconds(session.start_time, end)
        total = max(gross - paused_elapsed, 0.0)

        session.end_time = end
        session.total_time = round(total, 2)
        session.paused_elapsed = round(paused_elapsed, 2)
        session.is_started = SessionState.COMPLETED
        session.is_paused = False
        session.paused_at = None
        session.review = (review or "")[:500]
        session.save(
            update_fields=[
                "end_time", "total_time", "paused_elapsed",
                "is_started", "is_paused", "paused_at", "review",
            ]
        )

        if session.allocation_id:
            from apps.allocations.models import BatchAllocation
            from apps.tracking.models import EmployeeSubmission
            
            # Save files to EmployeeSubmission
            # if chain_sheet or search_package or report:
            #     submission = EmployeeSubmission(allocation_id=session.allocation_id)
            #     if chain_sheet:
            #         submission.chain_sheet = chain_sheet
            #     if search_package:
            #         submission.search_package = search_package
            #     if report:
            #         submission.report = report
            #     submission.save()

            # Save employee_comments back to BatchAllocation if provided
            if employee_comments:
                alloc = BatchAllocation.objects.filter(allocation_id=session.allocation_id).first()
                if alloc:
                    # Append or overwrite? Usually append or just overwrite if empty
                    if alloc.employee_comments:
                        alloc.employee_comments = f"{alloc.employee_comments}\n{employee_comments}"
                    else:
                        alloc.employee_comments = employee_comments
                    alloc.save(update_fields=['employee_comments'])

        self._roll_up_target(session)

        self.log("session_ended", id=session.id, total=session.total_time)
        self.on_commit(lambda: self._announce_completion(session))
        return session

    @transaction.atomic
    def delete_session(self, session_id: int) -> None:
        """Remove a session created in error.

        Only the owner while it is still open, or a supervisor at any time —
        an employee must not be able to delete a finished session whose hours
        a supervisor has already reviewed.
        """
        session = self.require_found(
            WorkSession.objects.select_for_update().filter(pk=session_id).first(),
            "No such work session.",
        )
        actor = self.require_actor()

        if not actor.is_supervisor:
            self.require(session.emp_id == actor.emp_id, "That session belongs to someone else.")
            self.require(
                session.is_open,
                "A completed session can only be removed by a supervisor.",
                code="conflict",
            )

        emp_id = session.emp_id
        session.delete()

        self.log("session_deleted", id=session_id, emp_id=emp_id)
        self.on_commit(
            lambda: publish(
                group=f"user.{emp_id}",
                event="work.session.deleted",
                data={"id": session_id},
            )
        )

    @transaction.atomic
    def indexing_submit(self, session_id: int, units: int) -> dict:
        """Submit multiple units for an indexing session, end the session, and start a new one."""
        session = self._locked_open_session(session_id)
        
        # End the current session without rolling up 1 unit automatically
        end = now_ist()
        gross = elapsed_seconds(session.start_time, end)
        paused_elapsed = float(session.paused_elapsed) if session.paused_elapsed else 0.0
        if session.is_paused and session.paused_at:
            paused_elapsed += elapsed_seconds(session.paused_at, end)
        
        total = max(gross - paused_elapsed, 0.0)
        session.end_time = end
        session.total_time = round(total, 2)
        session.paused_elapsed = round(paused_elapsed, 2)
        session.is_started = SessionState.COMPLETED
        session.is_paused = False
        session.paused_at = None
        session.save(update_fields=[
            "end_time", "total_time", "paused_elapsed",
            "is_started", "is_paused", "paused_at"
        ])

        # Roll up the specific number of units
        from core.timezone import today_ist
        target, _ = Target.objects.get_or_create(
            emp_id=session.emp_id, 
            project=session.project, 
            target_date=today_ist(),
            defaults={"target_units": 0, "work_type": session.work_type or "INDEXING"}
        )
        was_met = target.is_met
        Target.objects.filter(pk=target.pk).update(
            achieved_units=models.F('achieved_units') + units,
            updated_at=now_ist(),
        )
        target.refresh_from_db()
        if target.is_met and not was_met:
            self.on_commit(lambda: self._notify_target_met(session, target))
            
        self.log("session_ended", id=session.id, total_time=session.total_time, units=units)
        self.on_commit(lambda: self._announce(session, "work.session.ended"))

        # Start a new session automatically
        new_session = self.start_session(
            emp_id=session.emp_id,
            project=session.project,
            client_code=session.client_code,
            work_type=session.work_type,
            batch=session.batch,
            allocation_id=session.allocation_id
        )

        return {
            "ended_session": session,
            "new_session": new_session,
            "units_submitted": units
        }

    # ── internals ────────────────────────────────────────────

    def _locked_open_session(self, session_id: int) -> WorkSession:
        """Fetch an open session under a row lock, checking ownership."""
        session = self.require_found(
            WorkSession.objects.select_for_update()
            .filter(pk=session_id, end_time__isnull=True)
            .first(),
            "No open work session with that ID.",
        )
        self.require_owner_or_supervisor(
            session.emp_id, "That work session belongs to someone else."
        )
        return session

    def _roll_up_target(self, session: WorkSession) -> None:
        """Add the units to today's target, if one is set."""
        target = Target.objects.filter(
            emp_id=session.emp_id, project=session.project, target_date=today_ist()
        ).first()
        if not target:
            return

        was_met = target.is_met
        Target.objects.filter(pk=target.pk).update(
            achieved_units=target.achieved_units + 1,
            updated_at=now_ist(),
        )
        target.refresh_from_db()

        if target.is_met and not was_met:
            self.on_commit(lambda: self._notify_target_met(session, target))

    @staticmethod
    def _notify_target_met(session: WorkSession, target: Target) -> None:
        from apps.notifications.services import NotificationService

        NotificationService().notify(
            recipients=[session.emp_id],
            notif_type="work.target_met",
            context={"project": session.project or "your project"},
        )

    @staticmethod
    def _announce(session: WorkSession, event: str) -> None:
        from apps.presence.services import PresenceService
        from apps.realtime.groups import user_group

        PresenceService().recompute(session.emp_id)
        publish(
            group=user_group(session.emp_id),
            event=event,
            data={
                "id": session.id,
                "project": session.project,
                "work_type": session.work_type,
                "is_paused": session.is_paused,
                "elapsed_seconds": session.live_elapsed_seconds,
            },
        )

    @staticmethod
    def _announce_completion(session: WorkSession) -> None:
        from apps.presence.services import PresenceService
        from apps.realtime.groups import user_group

        PresenceService().recompute(session.emp_id)
        publish(
            group=user_group(session.emp_id),
            event="work.session.completed",
            data={
                "id": session.id,
                "total_time": session.total_time,
            },
        )


class TargetService(BaseService):
    """Daily targets. Setting one is a supervisor action."""

    @transaction.atomic
    def set_target(
        self, *, emp_id: str, target_date, target_units: int,
        project: str = "", work_type: str = "",
    ) -> Target:
        self.require_supervisor("Only a supervisor can set targets.")

        if target_units < 0:
            raise ValidationError("A target cannot be negative.")

        target, created = Target.objects.update_or_create(
            emp_id=emp_id,
            project=project,
            work_type=work_type,
            target_date=target_date,
            defaults={
                "target_units": target_units,
                "created_by": self.actor_emp_id or "",
                "updated_at": now_ist(),
            },
        )

        self.log("target_set", emp_id=emp_id, units=target_units, created=created)
        self.on_commit(
            lambda: publish(
                group=f"user.{emp_id}",
                event="work.target.set",
                data={
                    "target_date": str(target_date),
                    "target_units": target_units,
                    "project": project,
                },
            )
        )
        return target
