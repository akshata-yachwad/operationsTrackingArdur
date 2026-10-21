"""Shared template context.

Everything a page needs to boot its JavaScript: who the user is, which
features are on, and where the websocket lives. Serialised into a single
``window.__BOOTSTRAP__`` blob so the client makes zero requests before it can
render its shell.
"""

from __future__ import annotations

from django.conf import settings


def base_context(request, **extra) -> dict:
    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)

    context = {
        "current_user": _user_payload(user) if authenticated else None,
        "features": {
            "chat": settings.FEATURE_CHAT,
            "presence": settings.FEATURE_PRESENCE,
            "notifications": settings.FEATURE_NOTIFICATIONS,
        },
        "ws_url": websocket_url(request),
        "api_base": "/api/v1",
        "request_id": getattr(request, "request_id", ""),
    }
    context.update(extra)
    return context


def _user_payload(user) -> dict:
    employee = user.employee
    return {
        "emp_id": user.emp_id,
        "name": user.display_name,
        "role": user.role,
        "is_admin": user.is_super_admin,
        "is_super_admin": user.is_super_admin,
        "is_project_admin": user.is_project_admin,
        "is_team_lead": user.is_team_lead,
        "is_supervisor": user.is_supervisor,
        "project": employee.project if employee else "",
        "shift": employee.shift if employee else "",
    }


def websocket_url(request) -> str:
    """Where the browser should open its socket.

    Same origin by default — Apache proxies /ws/ to Daphne. WS_PUBLIC_URL
    overrides it if the realtime service ever moves to its own host.
    """
    configured = getattr(settings, "WS_PUBLIC_URL", "")
    if configured:
        return configured.rstrip("/") + "/ws/gateway/"

    scheme = "wss" if request.is_secure() else "ws"
    return f"{scheme}://{request.get_host()}/ws/gateway/"
