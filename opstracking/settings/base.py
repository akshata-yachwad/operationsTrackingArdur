"""Settings shared by every environment.

Anything that differs between local and production belongs in dev.py / prod.py,
not behind an ``if DEBUG`` in this file.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(str(env_file))

# ─────────────────────────── core ───────────────────────────

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-do-not-use-in-production")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

ROOT_URLCONF = "opstracking.urls"
WSGI_APPLICATION = "opstracking.wsgi.application"
ASGI_APPLICATION = "opstracking.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ───────────────────────── feature flags ─────────────────────
# Chat ships disabled: the app is scaffolded but not implemented.
# See apps/chat/README.md for what "turning it on" will involve.
FEATURE_CHAT = env.bool("FEATURE_CHAT", default=False)
FEATURE_PRESENCE = env.bool("FEATURE_PRESENCE", default=True)
FEATURE_NOTIFICATIONS = env.bool("FEATURE_NOTIFICATIONS", default=True)

# Legacy tables carried over from the Flask application.
#   True  → Django owns the schema; migrations create the tables (local dev).
#   False → Django reads and writes but never issues DDL (production, where
#           the tables already hold live data). Adopt them with:
#               python manage.py migrate --fake-initial
LEGACY_TABLES_MANAGED = env.bool("LEGACY_TABLES_MANAGED", default=True)

# ────────────────────────── applications ─────────────────────

DJANGO_APPS = [
    "daphne",  # must precede staticfiles so runserver speaks ASGI
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "channels",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
]

LOCAL_APPS = [
    "core",
    "pages",
    # ── business domain ──
    "apps.accounts",
    "apps.masters",
    "apps.tracking",
    "apps.breaks",
    "apps.allocations",
    "apps.feedback",
    "apps.reports",
    "apps.settings_app",

    # ── platform ──
    "apps.files",
    "apps.realtime",
    "apps.presence",
    "apps.notifications",
    # ── future ──
    # "apps.chat",   ← scaffolded only; see apps/chat/README.md
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ───────────────────────── middleware ────────────────────────

MIDDLEWARE = [
    "core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "core.middleware.CatchSessionInterruptedMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.AccessLogMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

# ───────────────────────── templates ─────────────────────────
# Two backends on purpose: Jinja2 owns the application's own screens (the
# templates ported from Flask), the Django template language stays available
# for django.contrib.admin and DRF's browsable API.

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "environment": "opstracking.jinja2_env.environment",
            "auto_reload": DEBUG,
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ────────────────────────── database ─────────────────────────

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://opstracking:opstracking@127.0.0.1:5432/opstracking",
    )
}
DATABASES["default"].setdefault("CONN_MAX_AGE", 60)
DATABASES["default"].setdefault("CONN_HEALTH_CHECKS", True)

# MySQL needs to be told, explicitly, not to silently truncate over-length
# values. That is the difference between a loud 400 and a corrupted row.
if "mysql" in DATABASES["default"]["ENGINE"]:
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    )

# ─────────────────────── redis / cache ───────────────────────
# db0 channels · db1 celery broker · db2 celery results · db3 cache

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"{REDIS_URL}/3",
        "KEY_PREFIX": "opstracking",
        "TIMEOUT": 300,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [f"{REDIS_URL}/0"],
            "capacity": 1500,
            "expiry": 20,
            "group_expiry": 86400,
        },
    }
}

# ─────────────────────────── celery ──────────────────────────

CELERY_BROKER_URL = f"{REDIS_URL}/1"
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "default"
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_ENABLE_UTC = False
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.reports.tasks.*": {"queue": "reports"},
    "apps.allocations.tasks.*": {"queue": "reports"},
    "apps.files.tasks.*": {"queue": "default"},
    "apps.notifications.tasks.*": {"queue": "default"},
    "apps.presence.tasks.*": {"queue": "default"},
    "apps.chat.tasks.*": {"queue": "default"},
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ─────────────────── authentication / passwords ──────────────
# The legacy Flask app stored bare bcrypt hashes ($2b$...). scripts/
# migrate_password_hashes.py prefixes them with "bcrypt$" so Django can read
# them; Django then upgrades each user to BCryptSHA256 on their next login.

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.BCryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 4}},
]

# ───────────────────────── sessions ──────────────────────────
# Server-side by default: the cookie is an opaque key, the state is a row.
# logout() deletes the row, so a replayed cookie resolves to nothing.

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_NAME = "opstrack_sid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12  # one shift
SESSION_SAVE_EVERY_REQUEST = True  # sliding expiry

CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# ─────────────────── django rest framework ───────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Deny by default. A view that forgets its permission_classes is locked,
    # not open — a forgotten decorator can never expose data again.
    "DEFAULT_PERMISSION_CLASSES": [
        "core.permissions.IsAuthenticatedEmployee",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "core.exception_handler.handle",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "chat_send": "30/min",
        "upload": "20/min",
        "login": "10/min",
        "report_export": "10/min",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# ───────────────────── i18n / timezone ───────────────────────
# Every timestamp the business cares about is IST. core.timezone.now_ist() is
# the only sanctioned clock — a ruff rule bans bare datetime.now().

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ──────────────────── static and media ───────────────────────

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))

# Uploads NEVER live under the web root. Downloads go through an authenticated
# view that checks permissions before streaming a byte.
PRIVATE_STORAGE_ROOT = Path(env("PRIVATE_STORAGE_ROOT", default=str(BASE_DIR / "storage")))

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_upload_perms = env("FILE_UPLOAD_PERMISSIONS", default="0o640")
FILE_UPLOAD_PERMISSIONS = None if _upload_perms.lower() in ("none", "") else int(_upload_perms, 8)
_dir_perms = env("FILE_UPLOAD_DIRECTORY_PERMISSIONS", default="0o750")
FILE_UPLOAD_DIRECTORY_PERMISSIONS = None if _dir_perms.lower() in ("none", "") else int(_dir_perms, 8)

STORAGES = {
    "default": {"BACKEND": "apps.files.storage.PrivateStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# ─────────────────────────── email ───────────────────────────

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="opstracking@example.com")

# ────────────────────────── realtime ─────────────────────────

WS_PUBLIC_URL = env("WS_PUBLIC_URL", default="")
WS_TICKET_TTL = 60  # seconds; single-use
WS_HEARTBEAT_INTERVAL = 20
WS_HEARTBEAT_GRACE = 45
OUTBOX_RETENTION_DAYS = 7

# ────────────────────────── logging ──────────────────────────

LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "core.middleware.RequestIDLogFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} [{request_id}] {name}: {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "django.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "filters": ["request_id"],
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
        "opstracking": {"level": LOG_LEVEL, "propagate": True},
        "daphne": {"level": "WARNING", "propagate": True},
    },
}

# ───────────────────────── security ──────────────────────────

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
APPEND_SLASH = True

CONTENT_SECURITY_POLICY = (
    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://code.jquery.com https://cdnjs.cloudflare.com https://cdn.datatables.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.datatables.net; "
    "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self' ws: wss:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
