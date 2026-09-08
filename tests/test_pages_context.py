"""pages/context.py — the bootstrap blob every Jinja2 page injects as
``window.__BOOTSTRAP__``.

Nothing here is exercised elsewhere: the page views call ``base_context()``
and hand the result straight to the template, so a bug here (the wrong role,
a leaked field for an anonymous visitor, a websocket URL pointing at the
wrong origin) would only show up as a broken page in a browser.
"""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, override_settings

import pytest

from pages.context import base_context, websocket_url

pytestmark = pytest.mark.django_db

rf = RequestFactory()


def _request(path="/", *, secure=False, user=None, request_id=None):
    request = rf.get(path, secure=secure)
    request.user = user if user is not None else AnonymousUser()
    if request_id is not None:
        request.request_id = request_id
    return request


# ── current_user ──────────────────────────────────────────────

def test_anonymous_visitor_gets_no_current_user():
    context = base_context(_request())
    assert context["current_user"] is None


def test_signed_in_employee_gets_their_profile(employee):
    context = base_context(_request(user=employee))
    payload = context["current_user"]

    assert payload["emp_id"] == employee.emp_id
    assert payload["name"] == employee.display_name
    assert payload["role"] == "employee"
    assert payload["is_admin"] is False
    assert payload["is_supervisor"] is False


def test_supervisor_flags_are_correct(supervisor):
    payload = base_context(_request(user=supervisor))["current_user"]
    assert payload["is_supervisor"] is True
    assert payload["is_admin"] is False


def test_admin_is_also_a_supervisor(admin):
    payload = base_context(_request(user=admin))["current_user"]
    assert payload["is_admin"] is True
    assert payload["is_supervisor"] is True


def test_current_user_project_and_shift_come_from_the_employee_record(employee):
    from apps.accounts.models import Employee

    Employee.objects.filter(employee_id=employee.emp_id).update(
        project="Northwind Records", shift="Night"
    )
    # The User.employee property is cached per instance — build a fresh one
    # so this test does not depend on fixture internals.
    from apps.accounts.models import User

    fresh = User.objects.get(pk=employee.pk)

    payload = base_context(_request(user=fresh))["current_user"]
    assert payload["project"] == "Northwind Records"
    assert payload["shift"] == "Night"


def test_current_user_handles_a_missing_employee_record(db):
    """A User row with no matching Employee must not crash the page —
    project/shift degrade to empty strings instead of raising."""
    from apps.accounts.models import User

    orphan = User.objects.create_user(emp_id="ORPHAN1", password="x", name="No Employee Row")

    payload = base_context(_request(user=orphan))["current_user"]
    assert payload["project"] == ""
    assert payload["shift"] == ""


def test_current_user_fields_are_exactly_the_documented_shape(employee):
    payload = base_context(_request(user=employee))["current_user"]
    assert set(payload) == {
        "emp_id", "name", "role", "is_admin", "is_super_admin", "is_project_admin", "is_team_lead", "is_supervisor", "project", "shift",
    }


# ── feature flags ─────────────────────────────────────────────

def test_features_reflect_settings():
    with override_settings(FEATURE_CHAT=False, FEATURE_PRESENCE=True, FEATURE_NOTIFICATIONS=True):
        context = base_context(_request())

    assert context["features"] == {"chat": False, "presence": True, "notifications": True}


def test_chat_feature_flag_is_off_by_default_in_this_deployment():
    """Chat is deliberately deferred — see apps/chat/README.md. This context
    is the switch a template checks before rendering any chat UI at all."""
    from django.conf import settings

    assert settings.FEATURE_CHAT is False


def test_toggling_a_feature_flag_is_reflected_immediately():
    with override_settings(FEATURE_NOTIFICATIONS=False):
        assert base_context(_request())["features"]["notifications"] is False
    with override_settings(FEATURE_NOTIFICATIONS=True):
        assert base_context(_request())["features"]["notifications"] is True


# ── request_id / api_base / extra kwargs ─────────────────────

def test_request_id_passes_through_when_present():
    context = base_context(_request(request_id="abc123"))
    assert context["request_id"] == "abc123"


def test_request_id_defaults_to_empty_string_when_absent():
    """RequestIdMiddleware sets this in the real stack; a request built
    without it (as in a unit test) must degrade gracefully, not raise."""
    context = base_context(_request())
    assert context["request_id"] == ""


def test_api_base_is_the_stable_v1_prefix():
    assert base_context(_request())["api_base"] == "/api/v1"


def test_extra_kwargs_are_merged_into_the_context():
    context = base_context(_request(), page_title="Dashboard", extra_flag=True)
    assert context["page_title"] == "Dashboard"
    assert context["extra_flag"] is True


def test_extra_kwargs_can_override_a_default_key():
    """base_context.update(extra) runs last — a page view can deliberately
    override a default (e.g. a custom api_base for a preview environment)."""
    context = base_context(_request(), api_base="/api/v2-preview")
    assert context["api_base"] == "/api/v2-preview"


def test_context_has_exactly_the_documented_top_level_keys():
    context = base_context(_request())
    assert set(context) == {
        "current_user", "features", "ws_url", "api_base", "request_id",
    }


# ── websocket_url ─────────────────────────────────────────────

def test_websocket_url_defaults_to_same_origin_ws():
    url = websocket_url(_request(secure=False))
    assert url.startswith("ws://testserver/ws/gateway/")


def test_websocket_url_upgrades_to_wss_over_https():
    url = websocket_url(_request(secure=True))
    assert url.startswith("wss://testserver/ws/gateway/")


def test_websocket_url_honours_the_hostname():
    request = rf.get("/", HTTP_HOST="ops.example.com")
    request.user = AnonymousUser()
    assert websocket_url(request) == "ws://ops.example.com/ws/gateway/"


def test_websocket_url_override_is_used_verbatim():
    with override_settings(WS_PUBLIC_URL="wss://realtime.example.com"):
        assert websocket_url(_request()) == "wss://realtime.example.com/ws/gateway/"


def test_websocket_url_override_strips_a_trailing_slash():
    with override_settings(WS_PUBLIC_URL="wss://realtime.example.com/"):
        assert websocket_url(_request()) == "wss://realtime.example.com/ws/gateway/"


def test_websocket_url_override_wins_even_over_https_detection():
    """A configured public URL is authoritative — it is not recomputed from
    request.is_secure() once WS_PUBLIC_URL is set."""
    with override_settings(WS_PUBLIC_URL="ws://realtime.example.com"):
        assert websocket_url(_request(secure=True)) == "ws://realtime.example.com/ws/gateway/"


def test_base_context_embeds_the_same_websocket_url():
    context = base_context(_request())
    assert context["ws_url"] == websocket_url(_request())
