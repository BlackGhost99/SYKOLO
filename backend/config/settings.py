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
    "institutions",
    "pedagogy",
]
AUTH_USER_MODEL = "accounts.User"
MFA_ENCRYPTION_KEY = os.environ.get("MFA_ENCRYPTION_KEY", SECRET_KEY if not DEPLOYED else "")
if DEPLOYED and len(MFA_ENCRYPTION_KEY) < 32:
    raise ImproperlyConfigured("MFA_ENCRYPTION_KEY (32 caractères minimum) est requise.")
PASSWORD_RESET_TIMEOUT = 1800
# Never enable real payments without a reviewed merchant contract and environment secrets.
YEM_PAYMENTS_LIVE_ENABLED = os.environ.get("YEM_PAYMENTS_LIVE_ENABLED", "false").lower() == "true"
# OFF until SingPay confirms callback authentication and school merchant acceptance.
YEM_SINGPAY_ENABLED = os.environ.get("YEM_SINGPAY_ENABLED", "false").lower() == "true"
YEM_PAYMENT_ENCRYPTION_KEY = os.environ.get("YEM_PAYMENT_ENCRYPTION_KEY", "")
AUTH_PUBLIC_BASE_URL = os.environ.get("AUTH_PUBLIC_BASE_URL", "" if DEPLOYED else "http://localhost:3000")
EMAIL_HOST = os.environ.get("YEM_SMTP_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("YEM_SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("YEM_SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("YEM_SMTP_PASSWORD", "")
EMAIL_USE_TLS = not os.environ.get("YEM_SMTP_TLS", "true").lower() == "false"
YEM_RESEND_API_KEY = os.environ.get("YEM_RESEND_API_KEY", "")
DEFAULT_FROM_EMAIL = os.environ.get("YEM_FROM_EMAIL", "no-reply@localhost")
EMAIL_BACKEND = os.environ.get(
    "YEM_EMAIL_BACKEND",
    "accounts.email_backends.ResendEmailBackend" if YEM_RESEND_API_KEY else
    ("django.core.mail.backends.smtp.EmailBackend" if DEPLOYED else "django.core.mail.backends.console.EmailBackend"),
)
# Two supported production transports: HTTPS email API or SMTP on hosting
# that permits outbound mail ports. Do not claim availability on key alone:
# actual delivery must be tested with the user's verified sender domain.
PASSWORD_RESET_ENABLED = not DEPLOYED or bool(
    AUTH_PUBLIC_BASE_URL.startswith("https://")
    and os.environ.get("YEM_FROM_EMAIL")
    and (YEM_RESEND_API_KEY or os.environ.get("YEM_SMTP_HOST"))
)
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
SESSION_COOKIE_AGE = 8 * 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
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
