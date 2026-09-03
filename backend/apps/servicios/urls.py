"""
Peluquería Lorena — URLs del módulo de Servicios.

Define las rutas para:
- Catálogo oficial y tarifario de servicios.
- Control diario de atenciones por fecha y horario.
- Emisión y visualización de Consentimiento Informado.
- Cierre de insumos del día con descuento automático de stock.
- API REST para catálogo.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ServicioViewSet,
    catalogo_servicios_view,
    cierre_diario_view,
    control_diario_servicios_view,
    crear_consentimiento_view,
    crear_servicio_view,
    editar_servicio_view,
    registrar_servicio_realizado_view,
    ver_consentimiento_view,
)

app_name = "servicios"

router = DefaultRouter()
router.register(r"api", ServicioViewSet, basename="servicio-api")

urlpatterns = [
    # ── Catálogo Oficial ──
    path("", catalogo_servicios_view, name="catalogo"),
    path("nuevo/", crear_servicio_view, name="crear_servicio"),
    path("editar/<int:pk>/", editar_servicio_view, name="editar_servicio"),

    # ── Control Diario de Servicios ──
    path("control-diario/", control_diario_servicios_view, name="control_diario"),
    path("atencion/nueva/", registrar_servicio_realizado_view, name="registrar_servicio_realizado"),

    # ── Consentimiento Informado (Decoloración y Alisado) ──
    path("consentimiento/nuevo/", crear_consentimiento_view, name="crear_consentimiento"),
    path("consentimiento/<int:pk>/", ver_consentimiento_view, name="ver_consentimiento"),

    # ── Cierre Diario de Insumos ──
    path("cierre-diario/", cierre_diario_view, name="cierre_diario"),

    # ── API REST ──
    path("", include(router.urls)),
]
