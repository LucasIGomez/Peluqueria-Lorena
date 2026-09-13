"""
Peluquería Lorena — URLs del módulo de Turnos (Agenda).
"""
from django.urls import path

from .views import (
    agenda_view,
    asignar_profesional_view,
    cambiar_estado_view,
    cancelar_turno_view,
    completar_turno_view,
    crear_turno_view,
    editar_turno_view,
)

app_name = "turnos"

urlpatterns = [
    path("", agenda_view, name="agenda"),
    path("nuevo/", crear_turno_view, name="crear_turno"),
    path("editar/<int:pk>/", editar_turno_view, name="editar_turno"),
    path("cancelar/<int:pk>/", cancelar_turno_view, name="cancelar_turno"),
    path("<int:pk>/asignar/", asignar_profesional_view, name="asignar_profesional"),
    path("<int:pk>/estado/", cambiar_estado_view, name="cambiar_estado"),
    path("<int:pk>/completar/", completar_turno_view, name="completar_turno"),
]
