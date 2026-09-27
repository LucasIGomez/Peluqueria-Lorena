"""
Peluquería Lorena — URLs del módulo de Comisiones y Liquidación (RF8).

Rutas:
- /comisiones/registrar/ : Registro rápido de trabajo por peluquera (RF 8.2 y RF 8.3).
- /comisiones/mis-comisiones/ : Bitácora personal de comisiones para profesionales.
- /comisiones/configuracion/ : Parametrización de comisiones por categoría (RF 8.1 - Administradora).
- /comisiones/liquidacion/ : Reporte de liquidación y consolidado por período (RF 8.4 - Administradora).
- /comisiones/liquidacion/cerrar/ : Asiento formal de liquidación y pago.
"""
from django.urls import path

from .views import (
    cerrar_liquidacion_view,
    configuracion_comisiones_view,
    mis_comisiones_view,
    registrar_trabajo_view,
    reporte_liquidacion_view,
)

app_name = "comisiones"

urlpatterns = [
    path("registrar/", registrar_trabajo_view, name="registrar_trabajo"),
    path("mis-comisiones/", mis_comisiones_view, name="mis_comisiones"),
    path("configuracion/", configuracion_comisiones_view, name="configuracion"),
    path("liquidacion/", reporte_liquidacion_view, name="reporte_liquidacion"),
    path("liquidacion/cerrar/", cerrar_liquidacion_view, name="cerrar_liquidacion"),
]
