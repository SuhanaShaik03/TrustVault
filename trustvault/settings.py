import os
from pathlib import Path

import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "development-only-change-this-secret-key-before-deployment",
)
IS_VERCEL = (
    os.environ.get("VERCEL", "").lower() in {"1", "true", "yes"}
    or bool(os.environ.get("VERCEL_ENV", "").strip())
    or bool(os.environ.get("VERCEL_URL", "").strip())
)
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
IS_RENDER = (
    os.environ.get("RENDER", "").lower() in {"1", "true", "yes"}
    or bool(os.environ.get("RENDER_SERVICE_ID", "").strip())
    or bool(RENDER_EXTERNAL_HOSTNAME)
)
IS_DEPLOYED = IS_VERCEL or IS_RENDER

try:
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
except ValueError as error:
    raise RuntimeError("TRUSTED_PROXY_COUNT must be a non-negative integer.") from error
if TRUSTED_PROXY_COUNT < 0:
    raise RuntimeError("TRUSTED_PROXY_COUNT must be a non-negative integer.")

debug_setting = os.environ.get("DJANGO_DEBUG")
if debug_setting is None:
    DEBUG = False
elif debug_setting.lower() in {"1", "true", "yes"}:
    DEBUG = True
elif debug_setting.lower() in {"0", "false", "no"}:
    DEBUG = False
else:
    raise RuntimeError("DJANGO_DEBUG must be set to true or false.")

if IS_DEPLOYED and DEBUG:
    raise RuntimeError("DJANGO_DEBUG must be false in a deployed environment.")

default_allowed_hosts = [
    "localhost",
    "127.0.0.1",
    "trust-vault-snowy.vercel.app",
    "trust-vault-pocx51pye-na-2210.vercel.app",
]

for env_name in ("VERCEL_URL", "APP_URL", "PUBLIC_URL", "SITE_URL"):
    value = os.environ.get(env_name, "").strip()
    if value:
        default_allowed_hosts.append(value)
if RENDER_EXTERNAL_HOSTNAME:
    default_allowed_hosts.append(RENDER_EXTERNAL_HOSTNAME)

ALLOWED_HOSTS = list(
    dict.fromkeys(
        host.strip()
        for host in os.environ.get(
            "DJANGO_ALLOWED_HOSTS",
            ",".join(default_allowed_hosts),
        ).split(",")
        if host.strip()
    )
)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "documents",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "trustvault.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "trustvault.wsgi.application"
ASGI_APPLICATION = "trustvault.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("DATABASE_URL="):
    DATABASE_URL = DATABASE_URL[len("DATABASE_URL="):].strip()

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,
            conn_health_checks=True,
            ssl_require=not DEBUG,
        )
    }
    if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise RuntimeError("DATABASE_URL must use PostgreSQL.")
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise RuntimeError("DATABASE_URL must be configured with a PostgreSQL connection URL.")

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
PRIVATE_MEDIA_ROOT = Path(
    os.environ.get("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "media_private"))
)
PRIVATE_MEDIA_DISK_MOUNT = Path(
    os.environ.get(
        "PRIVATE_MEDIA_DISK_MOUNT",
        "/var/data" if IS_RENDER else str(PRIVATE_MEDIA_ROOT.parent),
    )
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

if not DEBUG:
    if SECRET_KEY == "development-only-change-this-secret-key-before-deployment":
        raise RuntimeError("DJANGO_SECRET_KEY must be configured when DJANGO_DEBUG is false.")
    if not os.environ.get("DJANGO_SECRET_KEY", "").strip():
        raise RuntimeError("DJANGO_SECRET_KEY must be configured when DJANGO_DEBUG is false.")
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
