"""Production settings for GoDaddy cPanel (CloudLinux + Passenger).

This is a DEGRADED production profile. It exists because cPanel shared hosting
cannot run the stack prod.py assumes:

    Passenger is WSGI-only   → no ASGI, so WebSockets do not work
    No Redis                 → no channel layer, no Celery broker, no Redis cache
    No long-running processes → no Celery worker, no Celery beat

So this module keeps the request/response app fully working and substitutes
in-process equivalents for the pieces that need a daemon:

    channel layer → InMemory  (per-process; realtime is effectively off)
    cache         → database  (shared across Passenger workers, unlike LocMem)
    Celery        → eager     (tasks run inline, inside the web request)

The consequence to understand: anything in apps/*/tasks.py now runs *during*
the HTTP request that triggers it. A heavy report export will block that
request. That is the tradeoff for staying on shared hosting; prod.py remains
the module to use once this moves to a VPS.
"""

import os

from opstracking.settings.base import *  # noqa: F403
from opstracking.settings.base import BASE_DIR, INSTALLED_APPS, LOGGING, env  # noqa: F401

# ───────────────────── MySQL driver shim ─────────────────────
# mysqlclient is a C extension and often will not build under the CloudLinux
# Python selector. PyMySQL is pure Python and always installs; this makes it
# answer to the name Django looks for. Harmless when mysqlclient is present.

try:  # pragma: no cover - depends on what the host could install
    import MySQLdb  # noqa: F401
except ImportError:  # pragma: no cover
    import pymysql

    pymysql.install_as_MySQLdb()

DEBUG = False

SECRET_KEY = env("SECRET_KEY")  # no default: fail loudly rather than run insecure
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# The tables already exist and hold live data from the Flask app. Django must
# read and write them but never issue DDL against them.
#
# Assigned False literally, not read from the environment — same reasoning
# prod.py applies to DEBUG. A leftover LEGACY_TABLES_MANAGED=True in a deployed
# .env would let migrations rewrite the live legacy schema, and that is not a
# mistake anyone gets to make twice.
LEGACY_TABLES_MANAGED = False

# ───────────────────────── transport security ────────────────
# Apache terminates TLS and forwards X-Forwarded-Proto.
#
# HSTS is deliberately OFF by default here. The certificate for
# opstracking.ardurtechnology.com expired 2025-12-23; sending HSTS while TLS is
# broken would pin browsers to an unreachable https:// for a year and there is
# no way to undo it from the server. Turn these on via .env only once AutoSSL
# has issued a valid certificate and the site loads clean in a browser.

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
CSRF_COOKIE_HTTPONLY = False  # the JS fetch wrapper reads it for X-CSRFToken

# ───────────────────────── cache ─────────────────────────────
# Passenger runs several worker processes, so LocMemCache would give each one a
# private, inconsistent cache. The database table is shared. Create it once:
#     python manage.py createcachetable

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache_table",
        "KEY_PREFIX": "opstracking",
        "TIMEOUT": 300,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

# ───────────────────────── realtime (off) ────────────────────
# InMemory keeps group_send() from raising when application code fires an
# event. It does NOT deliver across processes — under Passenger there is no
# WebSocket transport at all. Clients must fall back to polling.

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# base.py lists "daphne" first in INSTALLED_APPS so that runserver speaks ASGI.
# Passenger serves WSGI and never touches it, and the daphne package pulls in
# twisted + cryptography — cryptography has no wheel here and compiles from
# Rust source, turning a two-minute pip install into a twenty-minute one that
# often just times out. Dropping the app lets requirements-cpanel.txt install
# plain `channels` instead.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "daphne"]

WS_PUBLIC_URL = env("WS_PUBLIC_URL", default="")
FEATURE_PRESENCE = env.bool("FEATURE_PRESENCE", default=False)
FEATURE_CHAT = False

# ───────────────────────── background jobs ───────────────────
# No worker exists, so tasks execute inline. EAGER_PROPAGATES is left False so
# a failing background task surfaces as a logged error rather than turning a
# user's page into a 500.

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "django-db"

# ───────────────────────── static files ──────────────────────
# Non-manifest storage on purpose: ManifestStaticFilesStorage raises at request
# time for any file missing from staticfiles.json, which is a live 500 after an
# incomplete drag-and-drop upload. Compression without the manifest degrades to
# a 404 for one asset instead.

STORAGES = {
    "default": {"BACKEND": "apps.files.storage.PrivateStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

WHITENOISE_MAX_AGE = 31_536_000

# ───────────────────────── logging ───────────────────────────

_log_file = env("DJANGO_LOG_FILE", default=str(BASE_DIR / "logs" / "django.log"))
os.makedirs(os.path.dirname(_log_file), exist_ok=True)
LOGGING["handlers"]["file"]["filename"] = _log_file  # noqa: F405

# ───────────────────────── observability ─────────────────────

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:  # pragma: no cover
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="production-cpanel"),
    )
