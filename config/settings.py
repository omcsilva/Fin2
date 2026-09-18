"""Local read-only dashboard. Network isolation is required; there is no login."""
import os
from pathlib import Path
import secrets
from config.environment import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DEBUG = os.environ.get("FIN2_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("FIN2_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set FIN2_SECRET_KEY when FIN2_DEBUG=0")
    SECRET_KEY = secrets.token_urlsafe(48)
ALLOWED_HOSTS = os.environ.get("FIN2_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
default_csrf_origins = (
    "http://localhost:8000,http://127.0.0.1:8000,https://localhost:8000,https://127.0.0.1:8000,"
    "http://localhost:8020,http://127.0.0.1:8020,https://localhost:8020,https://127.0.0.1:8020"
)
CSRF_TRUSTED_ORIGINS = [
    value.strip()
    for value in os.environ.get("FIN2_CSRF_TRUSTED_ORIGINS", default_csrf_origins).split(",")
    if value.strip()
]
CSRF_COOKIE_SECURE = os.environ.get("FIN2_SECURE_COOKIES", "0") == "1"
# Production Gunicorn binds to loopback; the trusted proxy replaces this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if not DEBUG else None
INSTALLED_APPS = ["django.contrib.staticfiles"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "fin2.dashboard.middleware.PrivateResponses",
]
DATABASES = {}
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"],
              "APP_DIRS": False, "OPTIONS": {
                  "context_processors": ["django.template.context_processors.request", "fin2.dashboard.context_processors.environment"],
                  "libraries": {"fin2_format": "fin2.dashboard.templatetags.fin2_format"},
                  "builtins": ["fin2.dashboard.templatetags.fin2_format"],
              }}]
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_TZ = True
STATIC_URL = "/fin2/static/"
FAVICON_STATIC_NAME = "favicon-DEV.ico" if DEBUG else "favicon-PRD.ico"
FIN1_BASE_URL = os.environ.get("FIN1_BASE_URL", "/fin1/").rstrip("/") + "/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": (
        "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG else
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    )},
}
DATA_DIR = Path(os.environ.get("FIN2_DATA_DIR", str(Path.home() / "Fin2-private" / "development"))).resolve()
WAREHOUSE_PATH = DATA_DIR / "fin2.duckdb"
DOCUMENT_ROOT = DATA_DIR / "documents"
CATALOG_IMAGE_ROOT = DATA_DIR / "catalog-images"
WRITE_ENABLED = os.environ.get("FIN2_WRITE_ENABLED", "1" if DEBUG else "0") == "1"
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CONTENT_TYPE_NOSNIFF = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
