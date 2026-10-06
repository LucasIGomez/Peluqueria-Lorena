"""
Peluquería Lorena — URLs de la API REST de Usuarios (/api/v1/usuarios/).

Autenticación JWT, perfil propio y CRUD de usuarios (solo Administradora).
Las pantallas web viven en urls.py bajo /usuarios/.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, PerfilView, UsuarioViewSet

app_name = "usuarios-api"

# Router para el ViewSet de Usuarios (CRUD API)
router = DefaultRouter()
router.register(r"", UsuarioViewSet, basename="usuario")

urlpatterns = [
    # ── Autenticación ──
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("perfil/", PerfilView.as_view(), name="perfil"),

    # ── CRUD de usuarios ──
    path("", include(router.urls)),
]
