"""
Peluquería Lorena — Configuración de URLs raíz.

Centraliza todas las rutas de la aplicación web y de la API.
"""
from django.contrib import admin
from django.urls import include, path

from config.views import dashboard_view

urlpatterns = [
    path("admin/", admin.site.urls),
    # La pantalla de inicio del sistema exige sesión iniciada (Dashboard RF 2).
    path("", dashboard_view, name="index"),
    path("clientes/", include("apps.clientes.urls")),
    path("turnos/", include("apps.turnos.urls")),
    path("inventario/", include("apps.inventario.urls")),
    path("proveedores/", include("apps.proveedores.urls")),
    path("usuarios/", include("apps.usuarios.urls")),
    path("api/v1/usuarios/", include("apps.usuarios.api_urls")),
    path("servicios/", include("apps.servicios.urls")),
    path("comisiones/", include("apps.comisiones.urls")),
    path("pagos/", include("apps.pagos.urls")),
    path("fidelizacion/", include("apps.fidelizacion.urls")),
    path("api/v1/bot/", include("apps.bot_asistente.urls", namespace="bot_asistente")),
]

