"""Passenger entry point for cPanel (CloudLinux Python selector).

cPanel's "Setup Python App" starts the process and imports ``application``
from this file. It must sit in the Application Root, beside manage.py.

Passenger is WSGI-only, so this serves HTTP but not WebSockets — see
opstracking/settings/cpanel.py for what that costs and why.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Passenger does not always start with the app root on sys.path, and an
# ImportError here surfaces only as a generic 500 in the browser.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load .env before Django reads settings, so DATABASE_URL/SECRET_KEY exist.
try:
    import environ

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        environ.Env.read_env(str(env_file))
except ImportError:  # pragma: no cover - dependency missing is its own error
    pass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "opstracking.settings.cpanel")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
