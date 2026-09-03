"""
Peluquería Lorena — Rutas URL del módulo de Inventario.

Define las rutas para:
- RF 7.1: Gestión de productos (lista, alta, edición, baja).
- RF 7.2: Descuento manual de stock por servicio.
- Agregar / Reponer Stock con registro de auditoría.
- RF 7.3: Alertas de stock y trazabilidad de movimientos.
- API REST con DRF Router.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "inventario"

router = DefaultRouter()
router.register(r"api", views.ProductoViewSet, basename="producto-api")

urlpatterns = [
    # ── Vistas Web (Plantillas HTML) ──
    path("productos/", views.lista_productos, name="lista_productos"),
    path("productos/crear/", views.crear_producto, name="crear_producto"),
    path("productos/editar/<int:pk>/", views.editar_producto, name="editar_producto"),
    path("productos/eliminar/<int:pk>/", views.eliminar_producto, name="eliminar_producto"),
    # Agregar / Reponer Stock
    path("reponer-stock/", views.reponer_stock_view, name="reponer_stock_general"),
    path("productos/<int:pk>/reponer/", views.reponer_stock_view, name="reponer_stock_producto"),
    # RF 7.2: Descuento manual de stock al finalizar servicio
    path("descontar-stock/", views.descontar_stock_servicio, name="descontar_stock_general"),
    path("productos/<int:pk>/descontar/", views.descontar_stock_servicio, name="descontar_stock_producto"),
    # Historial y auditoría de movimientos con buscador inteligente
    path("historial/", views.historial_movimientos, name="historial_movimientos"),
    # Sugerencias en tiempo real para buscadores
    path("sugerencias/", views.sugerencias_productos, name="sugerencias_productos"),
    # ── Endpoints API REST ──
    path("", include(router.urls)),
]
