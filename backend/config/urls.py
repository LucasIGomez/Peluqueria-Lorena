"""
Peluquería Lorena — Configuración de URLs raíz.

Centraliza todas las rutas de la aplicación web y de la API.
"""
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    # La pantalla de inicio del sistema exige sesión iniciada. Un visitante sin
    # sesión es redirigido a la pantalla de login (settings.LOGIN_URL).
    path(
        "",
        login_required(TemplateView.as_view(template_name="index.html")),
        name="index",
    ),
    path("inventario/", include("apps.inventario.urls")),
    path("proveedores/", include("apps.proveedores.urls")),
    path("usuarios/", include("apps.usuarios.urls")),
    path("api/v1/usuarios/", include(("apps.usuarios.urls", "usuarios"), namespace="usuarios-api")),
    path("clientes/", include("apps.clientes.urls")),
    path("servicios/", include("apps.servicios.urls")),
]
