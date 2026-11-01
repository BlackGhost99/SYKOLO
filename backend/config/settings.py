import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
ENVIRONMENT = os.environ.get("APP_ENV", "development")
if ENVIRONMENT not in {"development", "test", "staging", "production"}:
    raise ImproperlyConfigured("APP_ENV invalide.")
DEPLOYED = ENVIRONMENT in {"staging", "production"}
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
if DEPLOYED and DEBUG:
    raise ImproperlyConfigured("DEBUG doit être désactivé en staging/production.")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if DEPLOYED and len(SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY doit contenir au moins 50 caractères."
    )
if not SECRET_KEY:
    SECRET_KEY = "development-only-do-not-use-in-deployment-" + "0" * 32
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "" if DEPLOYED else "localhost,127.0.0.1,testserver"
    ).split(",")
    if h.strip()
]
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
if DEPLOYED and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Un nom d’hôte explicite est requis.")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "accounts",
    "pedagogy",
]
AUTH_USER_MODEL = "accounts.User"
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.ResponseHeadersMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = []
database_url = os.environ.get("DATABASE_URL", "")
if DEPLOYED and not database_url.startswith(("postgres://", "postgresql://")):
    raise ImproperlyConfigured(
        "DATABASE_URL PostgreSQL est requis en staging/production."
    )
DATABASES = {
    "default": dj_database_url.parse(
        database_url, conn_max_age=60, conn_health_checks=True
    )
    if database_url
    else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "dev.sqlite3"}
}
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = os.environ.get("APP_TIME_ZONE", "Africa/Libreville")
USE_I18N = True
USE_TZ = True
STATIC_URL = "/assets/"
STATIC_ROOT = ROOT_DIR / "staticfiles"
STATICFILES_DIRS = (
    [ROOT_DIR / "dist" / "assets"] if (ROOT_DIR / "dist" / "assets").exists() else []
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
SECURE_SSL_REDIRECT = DEPLOYED
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if DEPLOYED else None
SECURE_HSTS_SECONDS = 31536000 if DEPLOYED else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = DEPLOYED
SECURE_HSTS_PRELOAD = DEPLOYED
SESSION_COOKIE_SECURE = DEPLOYED
CSRF_COOKIE_SECURE = DEPLOYED
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}"
    for h in ALLOWED_HOSTS
    if h not in {"localhost", "127.0.0.1", "testserver"}
]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
