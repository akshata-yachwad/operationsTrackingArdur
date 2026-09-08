"""Request-scoped middleware: request ids, access logging, security headers."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("opstracking.access")

# ContextVar, not threading.local: this also works under ASGI, where a single
# thread interleaves many requests and a thread-local would leak one request's
# id into another's log line.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


class RequestIDLogFilter(logging.Filter):
    """Injects ``request_id`` into every record so the formatter can print it."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


class RequestIDMiddleware(MiddlewareMixin):
    """Assign every request a short id, echoed in the response header.

    When a user sends a screenshot of an error, the reference in it is this
    id, and one grep finds the exact log line.
    """

    header = "X-Request-ID"

    def process_request(self, request):
        incoming = request.headers.get(self.header)
        request_id = incoming if incoming and len(incoming) <= 64 else uuid.uuid4().hex[:12]
        set_request_id(request_id)
        request.request_id = request_id
        request._start_time = time.monotonic()

    def process_response(self, request, response):
        response[self.header] = getattr(request, "request_id", "-")
        return response


class AccessLogMiddleware(MiddlewareMixin):
    """One structured line per request. Slow requests are logged at WARNING."""

    SLOW_MS = 1000

    def process_response(self, request, response):
        start = getattr(request, "_start_time", None)
        if start is None:
            return response

        duration_ms = (time.monotonic() - start) * 1000
        user = getattr(request, "user", None)
        actor = getattr(user, "emp_id", None) or "anon"

        level = logging.WARNING if duration_ms >= self.SLOW_MS else logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR

        logger.log(
            level,
            '%s %s %s %d %.1fms user=%s',
            request.method,
            request.path,
            request.META.get("QUERY_STRING", "")[:200] or "-",
            response.status_code,
            duration_ms,
            actor,
        )
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Headers Django does not set on its own.

    The CSP is the second half of the XSS defence: message bodies are stored
    raw and escaped at render, and if a bug ever gets a ``<script>`` past that,
    ``script-src 'self'`` stops it executing.
    """

    def process_response(self, request, response):
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )

        # The browsable API and the admin need inline styles; the app's own
        # pages do not. Applying the strict policy only to our routes keeps
        # the policy tight where it matters without breaking tooling.
        if not request.path.startswith(("/admin/", "/api-auth/")):
            csp = getattr(settings, "CONTENT_SECURITY_POLICY", None)
            if csp and "Content-Security-Policy" not in response:
                response["Content-Security-Policy"] = csp

        return response


class CatchSessionInterruptedMiddleware:
    """Catches SessionInterrupted exceptions from forced logouts and redirects safely."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as e:
            # Import here to avoid circular imports during startup
            from django.contrib.sessions.exceptions import SessionInterrupted
            if isinstance(e, SessionInterrupted):
                from django.http import HttpResponseRedirect
                response = HttpResponseRedirect('/login/')
                response.delete_cookie(
                    settings.SESSION_COOKIE_NAME,
                    path=settings.SESSION_COOKIE_PATH,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    samesite=settings.SESSION_COOKIE_SAMESITE,
                )
                return response
            raise
