"""
Peluquería Lorena — URLs del módulo de Beneficios y Fidelización (RF10).

Rutas:
- /fidelizacion/reglas/ : Motor de reglas (RF 10.1 — Administradora).
- /fidelizacion/reglas/nueva/ : Alta de regla.
- /fidelizacion/reglas/<pk>/editar/ : Edición de regla.
- /fidelizacion/reglas/<pk>/alternar/ : Activar/pausar regla.
- /fidelizacion/reglas/<pk>/eliminar/ : Eliminar regla (conserva cupones otorgados).
- /fidelizacion/beneficios/ : Panel de auditoría de cupones otorgados.
- /fidelizacion/beneficios/<pk>/ : Ficha del cupón con canje y reenvío.
"""
from django.urls import path

from .views import (
    alternar_regla_view,
    crear_regla_view,
    detalle_beneficio_view,
    editar_regla_view,
    eliminar_regla_view,
    lista_reglas_view,
    panel_beneficios_view,
)

app_name = "fidelizacion"

urlpatterns = [
    path("reglas/", lista_reglas_view, name="lista_reglas"),
    path("reglas/nueva/", crear_regla_view, name="crear_regla"),
    path("reglas/<int:pk>/editar/", editar_regla_view, name="editar_regla"),
    path("reglas/<int:pk>/alternar/", alternar_regla_view, name="alternar_regla"),
    path("reglas/<int:pk>/eliminar/", eliminar_regla_view, name="eliminar_regla"),
    path("beneficios/", panel_beneficios_view, name="panel_beneficios"),
    path("beneficios/<int:pk>/", detalle_beneficio_view, name="detalle_beneficio"),
]
