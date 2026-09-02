"""Local read-only dashboard. Network isolation is required; there is no login."""
import os
from pathlib import Path
import secrets

BASE_DIR = Path(__file__).resolve().parents[1]
DEBUG = os.environ.get("FIN2_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("FIN2_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set FIN2_SECRET_KEY when FIN2_DEBUG=0")
    SECRET_KEY = secrets.token_urlsafe(48)
ALLOWED_HOSTS = os.environ.get("FIN2_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
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
              "APP_DIRS": False, "OPTIONS": {"context_processors": ["django.template.context_processors.request"]}}]
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_TZ = True
STATIC_URL = "/fin2/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DATA_DIR = Path(os.environ.get("FIN2_DATA_DIR", str(Path.home() / "Fin2-private" / "development"))).resolve()
WAREHOUSE_PATH = DATA_DIR / "fin2.duckdb"
DOCUMENT_ROOT = DATA_DIR / "documents"
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CONTENT_TYPE_NOSNIFF = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
