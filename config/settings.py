"""Minimal settings for the project so `manage.py` can run checks.

This is intentionally small — adjust as needed for your real project.
"""
from pathlib import Path
import os

# Load environment helpers (env.py) if present
try:
    import env  # noqa: F401
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-placeholder-key")
DEBUG = os.environ.get("DEBUG", "False").strip().lower() in ("1", "true", "yes")
# Parse HOST env var (comma-separated) into a cleaned list for ALLOWED_HOSTS.
# Example: HOST="myapp.herokuapp.com,alansalbums.com,www.alansalbums.com"
_hosts_env = os.environ.get('HOST', '127.0.0.1')
HOSTS = [h.strip() for h in _hosts_env.split(',') if h.strip()]
ALLOWED_HOSTS = HOSTS + ["localhost"]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sites",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "accounts.apps.AccountsConfig",
    # Cloudinary for image storage
    "cloudinary",
    "cloudinary_storage",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise should come right after SecurityMiddleware to serve static files
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # LocaleMiddleware enables language preference handling (put after sessions)
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database - default to sqlite for quick local runs; allow DATABASE_URL via dj-database-url
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# If a DATABASE_URL is provided (heroku/neon/supabase/etc.) prefer that.
# dj-database-url is listed in requirements.txt.
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    try:
        import dj_database_url

        DATABASES["default"] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    except Exception:
        # If dj_database_url isn't installed the app will continue to use sqlite
        pass

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# During development, also look for a top-level `static/` directory
STATICFILES_DIRS = [BASE_DIR / "static"]

# Use WhiteNoise to serve static files in production via Gunicorn
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

# Cloudinary storage configuration (optional — used when CLOUDINARY_URL env var is set)
if os.environ.get('CLOUDINARY_URL'):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
        'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
        'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Required by django.contrib.sites and some 3rd-party apps
SITE_ID = 1

# Authentication redirects
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"
