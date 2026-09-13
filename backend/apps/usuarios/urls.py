"""
Peluquería Lorena — URLs del módulo de Usuarios.

Define las rutas web para autenticación y panel de gestión de usuarios,
así como los endpoints de la API REST bajo /api/v1/usuarios/.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    PerfilView,
    UsuarioViewSet,
    crear_usuario_view,
    editar_usuario_view,
    eliminar_usuario_view,
    lista_usuarios_view,
    login_view,
    logout_view,
)

app_name = "usuarios"

# Router para el ViewSet de Usuarios (CRUD API)
router = DefaultRouter()
router.register(r"", UsuarioViewSet, basename="usuario")

urlpatterns = [
    # ── Vistas Web SSR ──
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("gestion/", lista_usuarios_view, name="lista_usuarios"),
    path("gestion/nuevo/", crear_usuario_view, name="crear_usuario"),
    path("gestion/editar/<int:pk>/", editar_usuario_view, name="editar_usuario"),
    path("gestion/eliminar/<int:pk>/", eliminar_usuario_view, name="eliminar_usuario"),

    # ── API REST Autenticación ──
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("perfil/", PerfilView.as_view(), name="perfil"),

    # ── CRUD de usuarios API ──
    path("", include(router.urls)),
]
