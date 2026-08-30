"""
Peluquería Lorena — Configuración de URLs raíz.

Centraliza todas las rutas de la aplicación web y de la API.
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
    path("inventario/", include("apps.inventario.urls")),
    path("proveedores/", include("apps.proveedores.urls")),
    path("api/v1/usuarios/", include("apps.usuarios.urls")),
]
