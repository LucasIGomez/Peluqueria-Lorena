"""
Peluquería Lorena — Configuración para testing.

Hereda de base.py. Usa SQLite in-memory, hashers rápidos (MD5)
para acelerar la suite de tests, y email backend en memoria.
"""
from .base import *  # noqa: F401, F403

# ──────────────────────────────────────────────
# DEBUG desactivado para simular producción
# ──────────────────────────────────────────────
DEBUG = False

ALLOWED_HOSTS = ["*"]

# ──────────────────────────────────────────────
# BASE DE DATOS — SQLite in-memory para velocidad
# ──────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ──────────────────────────────────────────────
# PASSWORD HASHERS — MD5 para velocidad en tests
# ──────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ──────────────────────────────────────────────
# EMAIL — In-memory para capturar correos en tests
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ──────────────────────────────────────────────
# Deshabilitar validadores de password en tests
# para poder crear usuarios con passwords simples
# ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = []

# ──────────────────────────────────────────────
# WHATSAPP Y BOT — Configuración mock para testing
# ──────────────────────────────────────────────
WHATSAPP_VERIFY_TOKEN = "test_verify_token"
WHATSAPP_APP_SECRET = "test_secret_key_12345"
WHATSAPP_PHONE_NUMBER_ID = "100200300"
WHATSAPP_ACCESS_TOKEN = "test_access_token"
