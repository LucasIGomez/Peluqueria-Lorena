"""
Peluquería Lorena — URLs del módulo de Usuarios.

Define las rutas de la API para autenticación y gestión de usuarios.
Se incluye desde config/urls.py bajo el prefijo /api/v1/usuarios/.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.usuarios.views import (
    LoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PerfilView,
    UsuarioViewSet,
)

# Router para el ViewSet de Usuarios (CRUD)
router = DefaultRouter()
router.register(r"", UsuarioViewSet, basename="usuario")

urlpatterns = [
    # ── Autenticación ──
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    # ── Perfil del usuario autenticado ──
    path("perfil/", PerfilView.as_view(), name="perfil"),
    # ── Reset de contraseña ──
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "auth/password-reset-confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    # ── CRUD de usuarios (router) ──
    path("", include(router.urls)),
]
