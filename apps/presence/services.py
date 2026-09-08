"""Presence, derived rather than declared.

"Online" on an ops floor means more than "has a socket open". The application
already knows whether someone is in a work session or on a break, so presence
folds that in. Precedence, highest first:

    1. on_break   an open row in aps_Break_Times
    2. working    an open, unpaused work session
    3. busy       the user set it manually
    4. online     at least one socket, heartbeat within 45s
    5. idle       socket alive but no heartbeat for 5 minutes
    6. offline    no sockets, or the heartbeat has aged out
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache

from apps.presence.models import PresenceState, PresenceStatus, StatusSource
from core.events import publish
from core.timezone import now_ist

logger = logging.getLogger("opstracking.presence")

STATE_KEY = "presence:state:{emp_id}"
CONNS_KEY = "presence:conns:{emp_id}"
MANUAL_KEY = "presence:manual:{emp_id}"

IDLE_AFTER_SECONDS = 300


class PresenceService:
    """Not a BaseService: presence is derived from other people's actions, so
    there is no single 'actor' performing it."""

    @property
    def ttl(self) -> int:
        return getattr(settings, "WS_HEARTBEAT_GRACE", 45)

    # ── socket lifecycle ─────────────────────────────────────

    def connect(self, emp_id: str) -> str:
        """A socket opened. Multiple tabs mean multiple connections."""
        count = self._increment_connections(emp_id, +1)
        logger.debug("presence connect %s (%d connections)", emp_id, count)
        return self.recompute(emp_id)

    def disconnect(self, emp_id: str) -> str:
        count = self._increment_connections(emp_id, -1)
        logger.debug("presence disconnect %s (%d connections)", emp_id, count)
        return self.recompute(emp_id)

    def heartbeat(self, emp_id: str) -> None:
        """Refresh the TTL. Deliberately does not broadcast.

        Broadcasting on every heartbeat would be 150 users x 150 recipients
        every 20 seconds — over a thousand messages a second of pure noise.
        Only real transitions are published; see _store().
        """
        cache.set(CONNS_KEY.format(emp_id=emp_id),
                  cache.get(CONNS_KEY.format(emp_id=emp_id), 1),
                  timeout=self.ttl)

        PresenceState.objects.filter(emp_id=emp_id).update(
            last_heartbeat_at=now_ist(), last_seen_at=now_ist()
        )

    # ── status computation ───────────────────────────────────

    def recompute(self, emp_id: str) -> str:
        """Derive the current status and store it."""
        from apps.breaks.models import BreakTime
        from apps.tracking.models import WorkSession
        from apps.allocations.models import TitleIndexingSession

        if BreakTime.objects.filter(user_id=emp_id, end_time__isnull=True).exists():
            return self._store(emp_id, PresenceStatus.ON_BREAK, StatusSource.BREAK)

        if WorkSession.objects.filter(emp_id=emp_id).active_now().exists():
            return self._store(emp_id, PresenceStatus.WORKING, StatusSource.WORK_SESSION)

        if TitleIndexingSession.objects.filter(employee_id=emp_id, status='IN_PROGRESS').exists():
            return self._store(emp_id, PresenceStatus.WORKING, StatusSource.WORK_SESSION)

        manual = cache.get(MANUAL_KEY.format(emp_id=emp_id))
        if manual and self._connection_count(emp_id) > 0:
            return self._store(emp_id, manual, StatusSource.MANUAL)

        connections = self._connection_count(emp_id)
        if connections > 0:
            state = PresenceState.objects.filter(emp_id=emp_id).first()
            if state and state.last_heartbeat_at:
                from core.timezone import elapsed_seconds

                if elapsed_seconds(state.last_heartbeat_at) > IDLE_AFTER_SECONDS:
                    return self._store(emp_id, PresenceStatus.IDLE, StatusSource.SOCKET)
            return self._store(emp_id, PresenceStatus.IDLE, StatusSource.SOCKET)

        return self._store(emp_id, PresenceStatus.OFFLINE, StatusSource.SOCKET)

    def set_status(self, emp_id: str, status: str, source: str = StatusSource.SOCKET) -> str:
        """Force a status. Used by the break and work services, which already
        know the answer and should not pay for a recompute."""
        return self._store(emp_id, status, source)

    def set_manual(self, emp_id: str, status: str, custom_status: str = "") -> str:
        """The user picked a status themselves.

        Stored in the cache with a TTL so it evaporates when they disconnect —
        a 'busy' badge that outlives the person setting it is worse than none.
        """
        cache.set(MANUAL_KEY.format(emp_id=emp_id), status, timeout=self.ttl * 4)
        if custom_status:
            PresenceState.objects.filter(emp_id=emp_id).update(
                custom_status=custom_status[:80]
            )
        return self.recompute(emp_id)

    def force_offline(self, emp_id: str) -> str:
        cache.delete(CONNS_KEY.format(emp_id=emp_id))
        cache.delete(MANUAL_KEY.format(emp_id=emp_id))
        return self._store(emp_id, PresenceStatus.OFFLINE, StatusSource.SOCKET)

    # ── reads ────────────────────────────────────────────────

    def get(self, emp_id: str) -> dict:
        cached_state = cache.get(STATE_KEY.format(emp_id=emp_id))
        if cached_state:
            return cached_state

        state = PresenceState.objects.filter(emp_id=emp_id).first()
        if not state:
            return {"emp_id": emp_id, "status": PresenceStatus.OFFLINE, "source": "socket"}

        return {
            "emp_id": emp_id,
            "status": state.status,
            "source": state.status_source,
            "custom_status": state.custom_status,
            "last_seen_at": state.last_seen_at.isoformat(),
        }

    def roster(self) -> list[dict]:
        """Every employee's current status, in one query.

        The page fetches this once on load and then applies deltas over the
        socket. Presence is never polled.
        """
        from apps.accounts.models import Employee, User

        states = {s.emp_id: s for s in PresenceState.objects.all()}
        employees = Employee.objects.active().values("employee_id", "name", "role", "project")
        
        emp_ids = [e["employee_id"] for e in employees]
        users = {u.emp_id: u.last_login for u in User.objects.filter(emp_id__in=emp_ids)}

        roster = []
        for employee in employees:
            emp_id = employee["employee_id"]
            state = states.get(emp_id)
            last_login = users.get(emp_id)
            roster.append(
                {
                    "emp_id": emp_id,
                    "name": employee["name"],
                    "role": employee["role"],
                    "project": employee["project"],
                    "status": state.status if state else PresenceStatus.OFFLINE,
                    "custom_status": state.custom_status if state else "",
                    "last_seen_at": state.last_seen_at.isoformat() if state else None,
                    "login_time": last_login.isoformat() if last_login else None,
                }
            )
        return roster

    # ── internals ────────────────────────────────────────────

    def _connection_count(self, emp_id: str) -> int:
        return int(cache.get(CONNS_KEY.format(emp_id=emp_id), 0) or 0)

    def _increment_connections(self, emp_id: str, delta: int) -> int:
        key = CONNS_KEY.format(emp_id=emp_id)
        count = max(self._connection_count(emp_id) + delta, 0)
        if count:
            cache.set(key, count, timeout=self.ttl * 4)
        else:
            cache.delete(key)
        return count

    def _store(self, emp_id: str, status: str, source: str) -> str:
        previous = (cache.get(STATE_KEY.format(emp_id=emp_id)) or {}).get("status")

        payload = {
            "emp_id": emp_id,
            "status": status,
            "source": source,
            "at": now_ist().isoformat(),
        }
        cache.set(STATE_KEY.format(emp_id=emp_id), payload, timeout=self.ttl * 4)

        PresenceState.objects.update_or_create(
            emp_id=emp_id,
            defaults={
                "status": status,
                "status_source": source,
                "connection_count": self._connection_count(emp_id),
                "last_seen_at": now_ist(),
                "updated_at": now_ist(),
            },
        )

        # Broadcast only real transitions. This single guard is the difference
        # between a few dozen messages an hour and a thousand a second.
        if previous != status:
            from apps.realtime.groups import presence_group

            publish(
                group=presence_group(),
                event="presence.changed",
                data={"emp_id": emp_id, "status": status, "source": source},
                durable=False,  # transient — replaying a stale status is worse than none
            )

        return status
