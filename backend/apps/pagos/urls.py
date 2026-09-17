"""
Peluquería Lorena — URLs del módulo de Caja y Ventas.

Define las rutas para:
- Tablero de caja diaria y registro de cobros.
- Cierre de caja diario (solo Administradora).
- Reporte de ingresos por medio de pago.
- API REST de cobros y cierres.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CierreCajaViewSet,
    CobroViewSet,
    anular_cobro_view,
    anular_venta_view,
    caja_diaria_view,
    cierre_caja_view,
    factura_pdf_view,
    reabrir_caja_view,
    registrar_cobro_view,
    reporte_medios_view,
)

app_name = "pagos"

router = DefaultRouter()
router.register(r"api/cobros", CobroViewSet, basename="cobro-api")
router.register(r"api/cierres", CierreCajaViewSet, basename="cierre-api")

urlpatterns = [
    # ── Caja diaria y cobros ──
    path("", caja_diaria_view, name="caja_diaria"),
    path("nuevo/", registrar_cobro_view, name="registrar_cobro"),
    path("anular/<int:pk>/", anular_cobro_view, name="anular_cobro"),
    path("anular-venta/<int:pk>/", anular_venta_view, name="anular_venta"),
    path("factura/<int:pk>/", factura_pdf_view, name="factura_pdf"),
    # ── Cierre diario y reapertura ──
    path("cierre/", cierre_caja_view, name="cierre_caja"),
    path("reabrir/", reabrir_caja_view, name="reabrir_caja"),
    # ── Reporte por medio de pago ──
    path("reporte/", reporte_medios_view, name="reporte_medios"),
    # ── API REST ──
    path("", include(router.urls)),
]
