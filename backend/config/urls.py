"""
Peluquería Lorena — Configuración de URLs raíz.

Centraliza todas las rutas de la aplicación web y de la API.
"""
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

from django.shortcuts import render

def modulo_en_desarrollo(request, nombre_modulo="Módulo"):
    """Renderiza vista informativa para módulos en desarrollo."""
    return render(
        request,
        "modulo_no_disponible.html",
        {"nombre_modulo": nombre_modulo},
    )

urlpatterns = [
    path("admin/", admin.site.urls),
    # La pantalla de inicio del sistema exige sesión iniciada. Un visitante sin
    # sesión es redirigido a la pantalla de login (settings.LOGIN_URL).
    path(
        "",
        login_required(TemplateView.as_view(template_name="index.html")),
        name="index",
    ),
    path("clientes/", include("apps.clientes.urls")),
    path("turnos/", include("apps.turnos.urls")),
    path("inventario/", include("apps.inventario.urls")),
    path("proveedores/", include("apps.proveedores.urls")),
    path("usuarios/", include("apps.usuarios.urls")),
    path("api/v1/usuarios/", include(("apps.usuarios.urls", "usuarios"), namespace="usuarios-api")),
    path("servicios/", include("apps.servicios.urls")),
    path("pagos/", include("apps.pagos.urls")),
]

