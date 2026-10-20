"""
Peluquería Lorena — Configuración de Producción (VPS Ubuntu 24.04 / Gunicorn / Nginx).

Hereda de base.py con directivas estrictas de seguridad:
- DEBUG = False
- HSTS y redirección forzada a HTTPS
- Cookies de sesión y CSRF restringidas a HTTPS
- Conexión a PostgreSQL (con fallback configurable vía .env)
- CORS restringido a dominios del salón
- Logging estructurado para journalctl / syslog
"""
from __future__ import annotations

from decouple import Csv, config

from .base import *  # noqa: F401, F403

# ──────────────────────────────────────────────
# DEBUG & HOSTS
# ──────────────────────────────────────────────
DEBUG: bool = False

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    cast=Csv(),
    default="peluquerialorena.cloud,www.peluquerialorena.cloud,100.116.140.71,179.199.155.141,localhost,127.0.0.1",
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    cast=Csv(),
    default="https://peluquerialorena.cloud,https://www.peluquerialorena.cloud,http://100.116.140.71",
)

# ──────────────────────────────────────────────
# BASE DE DATOS — PostgreSQL para producción
# ──────────────────────────────────────────────
DB_ENGINE = config("DB_ENGINE", default="django.db.backends.postgresql")

if "sqlite" in DB_ENGINE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": config("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": config("DB_NAME", default="peluqueria_lorena"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=600, cast=int),
        }
    }

# ──────────────────────────────────────────────
# SEGURIDAD HTTPS, HSTS Y COOKIES
# ──────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

# HTTP Strict Transport Security (HSTS)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Encabezados de protección del navegador
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# ──────────────────────────────────────────────
# CORS (Cross-Origin Resource Sharing)
# ──────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    cast=Csv(),
    default="https://peluquerialorena.cloud,https://www.peluquerialorena.cloud",
)

# ──────────────────────────────────────────────
# ARCHIVOS ESTÁTICOS
# ──────────────────────────────────────────────
STATIC_ROOT = BASE_DIR / "staticfiles"

# ──────────────────────────────────────────────
# LOGGING (Salida hacia systemd journalctl)
# ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} [{name}:{lineno}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": config("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.bot_asistente": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.turnos": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
