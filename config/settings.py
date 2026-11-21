"""Loyiha sozlamalari. Maxfiy qiymatlar .env faylidan o'qiladi (.env.example ga qarang)."""
import os
import shutil
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))
DEBUG = env_bool("DEBUG", not ON_RAILWAY)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
if not DEBUG and SECRET_KEY.startswith("dev-insecure"):
    raise ImproperlyConfigured("Production uchun .env faylida SECRET_KEY ni o'rnating.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Railway o'zi beradigan domen (masalan, mysite.up.railway.app) — avtomatik qo'shiladi.
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")
ALLOWED_HOSTS += ["healthcheck.railway.app"]

# Ma'lumotlar (baza va yuklangan fayllar) papkasi. Railway'da Volume ulanadigan joy: /data
DATA_DIR = Path(os.getenv("DATA_DIR") or BASE_DIR)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "core",
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
if DEBUG:  # lokalda static fayllarni runserver o'zi beradi
    MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

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
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
# Django admin o'zbekcha tarjimasidagi kamchiliklar shu yerda to'ldirilgan (locale/uz/LC_MESSAGES)
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR / "media"
# Media fayllarni Django o'zi tarqatadimi (lokalda — ha; serverda odatda nginx tarqatadi).
SERVE_MEDIA = env_bool("SERVE_MEDIA", DEBUG or ON_RAILWAY)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# Yuklangan fayllar hech qanday qayta ishlanmaydi — asl holida saqlanadi.
FILE_UPLOAD_PERMISSIONS = 0o644
DATA_UPLOAD_MAX_NUMBER_FILES = 200

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Sayt ---
SITE_URL = (os.getenv("SITE_URL") or (f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else "")).rstrip("/")
ADMIN_URL = os.getenv("ADMIN_URL", "admin/").strip("/") + "/"

# --- LinkedIn (shaxsiy profil) ---
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
# LinkedIn API versiyasi (YYYYMM). Versiyalar ~1 yil ishlaydi; xato bersa yangirog'ini yozing.
LINKEDIN_API_VERSION = os.getenv("LINKEDIN_API_VERSION", "202607").strip()

# --- Instagram (Business akkaunt) ---
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "").strip()
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "").strip()
INSTAGRAM_API_VERSION = os.getenv("INSTAGRAM_API_VERSION", "v25.0").strip()
# Make.com orqali yuborish: berilsa, Instagram postlari shu webhook'ga ketadi (Meta ilovasi kerak emas).
MAKE_INSTAGRAM_WEBHOOK_URL = os.getenv("MAKE_INSTAGRAM_WEBHOOK_URL", "").strip()

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
TELEGRAM_API_BASE = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
# Rasmiy Bot API orqali bot 50 MB gacha fayl yubora oladi. O'z Bot API serveringiz bo'lsa — 2000 gacha.
TELEGRAM_MAX_UPLOAD_MB = int(os.getenv("TELEGRAM_MAX_UPLOAD_MB", "50"))

# Video o'lchamlarini aniqlash uchun (ixtiyoriy). Topilmasa — video baribir ishlaydi.
FFPROBE_PATH = os.getenv("FFPROBE_PATH") or shutil.which("ffprobe")

if not DEBUG and env_bool("HTTPS", True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"core": {"handlers": ["console"], "level": "INFO"}, "core.publishers": {"level": "INFO"}},
}
