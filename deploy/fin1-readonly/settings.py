"""Production overrides for the frozen Fin1 archive."""
from config import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["django.lmnet.dpdns.org", "t1django.lan", "10.0.0.17", "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = ["https://django.lmnet.dpdns.org"]
STATIC_URL = "/fin1/static/"
MEDIA_URL = "/fin1/anexos/"
STATIC_ROOT = "/opt/fin1/STATIC"
MEDIA_ROOT = "/var/lib/fin1/ANEXOS"
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_PATH = "/fin1/"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_PATH = "/fin1/"
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3",
                "NAME": "file:/var/lib/fin1/db.sqlite3?mode=ro", "OPTIONS": {"uri": True}},
    "docs": {"ENGINE": "django.db.backends.sqlite3",
             "NAME": "file:/var/lib/fin1/docs.sqlite3?mode=ro", "OPTIONS": {"uri": True}},
    "dados": {"ENGINE": "django.db.backends.sqlite3",
              "NAME": "file:/var/lib/fin1/dados.sqlite3?mode=ro", "OPTIONS": {"uri": True}},
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "fin1.readonly.ReadOnlyArchiveMiddleware",
    "fin1.readonly.ArchiveUserMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
X_FRAME_OPTIONS = "SAMEORIGIN"
CORS_ORIGIN_ALLOW_ALL = False

# The legacy file logger needs a writable source tree. Production logs go only
# to journald through Gunicorn stdout/stderr.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
