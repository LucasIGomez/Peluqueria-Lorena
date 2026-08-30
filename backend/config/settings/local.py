"""
Peluquería Lorena — Configuración de desarrollo local.

Hereda de base.py y activa DEBUG, SQLite y CORS permisivo.
"""
from .base import *  # noqa: F401, F403

# ──────────────────────────────────────────────
# DEBUG
# ──────────────────────────────────────────────
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "100.82.23.52", "*"]

# ──────────────────────────────────────────────
# BASE DE DATOS — SQLite para desarrollo local
# ──────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ──────────────────────────────────────────────
# CORS — Permitir todo en desarrollo
# ──────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ──────────────────────────────────────────────
# EMAIL — Mostrar en consola
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
