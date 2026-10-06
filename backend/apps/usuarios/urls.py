"""
Peluquería Lorena — URLs del módulo de Usuarios.

Define las rutas web para autenticación y panel de gestión de usuarios.
Los endpoints de la API REST están en api_urls.py bajo /api/v1/usuarios/.
"""
from django.urls import path

from .views import (
    crear_usuario_view,
    editar_usuario_view,
    eliminar_usuario_view,
    lista_usuarios_view,
    login_view,
    logout_view,
)

app_name = "usuarios"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("gestion/", lista_usuarios_view, name="lista_usuarios"),
    path("gestion/nuevo/", crear_usuario_view, name="crear_usuario"),
    path("gestion/editar/<int:pk>/", editar_usuario_view, name="editar_usuario"),
    path("gestion/eliminar/<int:pk>/", eliminar_usuario_view, name="eliminar_usuario"),
]
