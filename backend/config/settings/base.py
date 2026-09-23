"""
Peluquería Lorena — Configuración base de Django.

Este archivo contiene la configuración compartida entre todos los entornos
(desarrollo, testing, producción). Las configuraciones específicas se
definen en local.py, testing.py y production.py.
"""
import os
from datetime import timedelta
from pathlib import Path
from typing import List

try:
    from decouple import config
except ImportError:
    def config(key, default=""):
        return os.environ.get(key, default)

# ──────────────────────────────────────────────
# RUTAS BASE
# ──────────────────────────────────────────────
# BASE_DIR apunta a /backend/
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# ──────────────────────────────────────────────
# SEGURIDAD
# ──────────────────────────────────────────────
SECRET_KEY: str = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-peluqueria-lorena-cambiar-en-produccion",
)

DEBUG: bool = False

ALLOWED_HOSTS: List[str] = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# ──────────────────────────────────────────────
# APLICACIONES
# ──────────────────────────────────────────────
DJANGO_APPS: List[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS: List[str] = [
    "rest_framework",
    "corsheaders",
    "django_extensions",
]

LOCAL_APPS: List[str] = [
    "apps.usuarios",
    "apps.inventario",
    "apps.proveedores",
    "apps.clientes",
    "apps.servicios",
    "apps.turnos",
    "apps.pagos",
    "apps.bot_asistente",
]

INSTALLED_APPS: List[str] = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ──────────────────────────────────────────────
# MIDDLEWARE
# ──────────────────────────────────────────────
MIDDLEWARE: List[str] = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ──────────────────────────────────────────────
# URLS & WSGI
# ──────────────────────────────────────────────
ROOT_URLCONF: str = "config.urls"
WSGI_APPLICATION: str = "config.wsgi.application"

# ──────────────────────────────────────────────
# TEMPLATES
# ──────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR.parent / "frontend"],
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

# ──────────────────────────────────────────────
# MODELO DE USUARIO PERSONALIZADO
# ──────────────────────────────────────────────
AUTH_USER_MODEL: str = "usuarios.Usuario"

# ──────────────────────────────────────────────
# VALIDADORES DE CONTRASEÑA
# ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ──────────────────────────────────────────────
# PASSWORD HASHERS (PBKDF2 por defecto, Argon2 recomendado en prod)
# ──────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# ──────────────────────────────────────────────
# DJANGO REST FRAMEWORK
# ──────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}

# ──────────────────────────────────────────────
# SIMPLE JWT
# ──────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# ──────────────────────────────────────────────
# INTERNACIONALIZACIÓN
# ──────────────────────────────────────────────
LANGUAGE_CODE: str = "es-ar"
TIME_ZONE: str = "America/Argentina/Buenos_Aires"
USE_I18N: bool = True
USE_TZ: bool = True
LOCALE_PATHS: List[Path] = [
    BASE_DIR / "locale",
]

# ──────────────────────────────────────────────
# ARCHIVOS ESTÁTICOS
# ──────────────────────────────────────────────
STATIC_URL: str = "static/"

# ──────────────────────────────────────────────
# CAMPO AUTOINCREMENTAL POR DEFECTO
# ──────────────────────────────────────────────
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────
# EMAIL (se sobreescribe por entorno)
# ──────────────────────────────────────────────
EMAIL_BACKEND: str = "django.core.mail.backends.console.EmailBackend"

# ──────────────────────────────────────────────
# AUTH URLS
# ──────────────────────────────────────────────
LOGIN_URL: str = "/usuarios/login/"
LOGIN_REDIRECT_URL: str = "/"
LOGOUT_REDIRECT_URL: str = "/usuarios/login/"

# ──────────────────────────────────────────────
# DATOS DEL SALÓN Y DE LA DUEÑA
# ──────────────────────────────────────────────
DATOS_PELUQUERIA = {
    "NOMBRE_SALON": "Peluquería Lorena",
    "NOMBRE_DUENA": os.environ.get("PELUQUERIA_DUENA_NOMBRE", "Lorena Yanil Ortigoza"),
    "CUIT_DUENA": os.environ.get("PELUQUERIA_DUENA_CUIT", "27-29327958-1"),
    "TELEFONO": os.environ.get("PELUQUERIA_TELEFONO", "+54 9 297 534-9278"),
    "EMAIL": os.environ.get("PELUQUERIA_EMAIL", "lrnortigoza@gmail.com"),
    "DIRECCION": os.environ.get("PELUQUERIA_DIRECCION", "Comodoro Rivadavia, Chubut, Argentina"),
}

# ──────────────────────────────────────────────
# BOT ASISTENTE Y WHATSAPP BUSINESS
# ──────────────────────────────────────────────
GEMINI_API_KEY: str = config("GEMINI_API_KEY", default="")
GEMINI_MODEL: str = config("GEMINI_MODEL", default="gemini-2.5-flash")
WHATSAPP_VERIFY_TOKEN: str = config("WHATSAPP_VERIFY_TOKEN", default="")
WHATSAPP_APP_SECRET: str = config("WHATSAPP_APP_SECRET", default="")
WHATSAPP_PHONE_NUMBER_ID: str = config("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_ACCESS_TOKEN: str = config("WHATSAPP_ACCESS_TOKEN", default="")

BOT_CONFIG = {
    "HORARIO_APERTURA": 9,   # 09:00
    "HORARIO_CIERRE": 19,    # 19:00
    "DIAS_ATENCION": [1, 2, 3, 4, 5],  # Martes (1) a Sábado (5). Lunes=0, Domingo=6 cerrados
}


