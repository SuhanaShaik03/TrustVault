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
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip()
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1").strip()
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "").strip() or None
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = True
AWS_DEFAULT_ACL = None

if IS_VERCEL and not all(
    (AWS_STORAGE_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
):
    raise RuntimeError(
        "Vercel deployments require AWS_STORAGE_BUCKET_NAME, AWS_ACCESS_KEY_ID, "
        "and AWS_SECRET_ACCESS_KEY for private document storage."
    )

DEBUG = not IS_VERCEL and os.environ.get("DJANGO_DEBUG", "True").lower() in {
    "1",
    "true",
    "yes",
}
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

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured with a PostgreSQL connection URL.")

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
PRIVATE_MEDIA_ROOT = BASE_DIR / "media_private"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

if not DEBUG:
    if SECRET_KEY == "development-only-change-this-secret-key-before-deployment":
        raise RuntimeError("DJANGO_SECRET_KEY must be configured when DJANGO_DEBUG is false.")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
