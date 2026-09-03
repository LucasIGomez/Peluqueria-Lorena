"""
Peluquería Lorena — URLs del módulo de Clientes.

Define las rutas para:
- Agenda y listado de clientas con alertas de cumpleaños.
- Ficha de perfil integral y seguimiento multisesión.
- API REST CRUD para clientas.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClienteViewSet,
    crear_cliente_view,
    detalle_cliente_view,
    editar_cliente_view,
    iniciar_tratamiento_view,
    lista_clientes_view,
    registrar_evolucion_view,
)

app_name = "clientes"

router = DefaultRouter()
router.register(r"api", ClienteViewSet, basename="cliente-api")

urlpatterns = [
    # ── Vistas Web SSR ──
    path("", lista_clientes_view, name="lista_clientes"),
    path("nueva/", crear_cliente_view, name="crear_cliente"),
    path("<int:pk>/", detalle_cliente_view, name="detalle_cliente"),
    path("editar/<int:pk>/", editar_cliente_view, name="editar_cliente"),
    path("<int:cliente_pk>/tratamiento/nuevo/", iniciar_tratamiento_view, name="iniciar_tratamiento"),
    path("tratamiento/<int:tratamiento_pk>/evolucion/", registrar_evolucion_view, name="registrar_evolucion"),

    # ── API REST ──
    path("", include(router.urls)),
]
