"""
Peluquería Lorena — Pruebas de las derivaciones del bot de WhatsApp a atención humana.

Cubren los caminos que antes fallaban por nombres de estado inexistentes:
- Opción 1 del menú (pasa la conversación a "en proceso").
- Derivación por servicio no reconocido.
- Derivación por franja sin cupo (capacidad simultánea del salón).
- Búsqueda en el panel de administración de conversaciones.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone

from apps.bot_asistente.admin import ConversacionBotAdmin
from apps.bot_asistente.ai.interpreter import BotResponseSchema, IntencionEnum
from apps.bot_asistente.models import ConversacionBot
from apps.bot_asistente.services import TurnoBotService
from apps.servicios.models import Servicio
from apps.turnos.models import Turno


def _proximo_dia_habil() -> date:
    """Primer día de martes a sábado que cae al menos 3 días después de hoy."""
    dia = timezone.localdate() + timedelta(days=3)
    while dia.weekday() not in (1, 2, 3, 4, 5):
        dia += timedelta(days=1)
    return dia


def _schema(servicios: list[str], fecha: date) -> BotResponseSchema:
    return BotResponseSchema(
        intencion=IntencionEnum.AGENDAR_TURNO,
        servicios_detectados=servicios,
        fecha_sugerida=fecha.isoformat(),
        hora_sugerida="15:00",
        mensaje_respuesta="ok",
        requiere_escalado=False,
    )


@pytest.fixture
def corte(db) -> Servicio:
    return Servicio.objects.create(
        nombre="Corte Damas",
        categoria="CORTE",
        precio_base=15000,
        duracion_estimada_minutos=45,
    )


@pytest.mark.django_db
class TestDerivacionesBot:
    def test_opcion_1_del_menu_pasa_a_en_proceso(self, corte: Servicio) -> None:
        with patch.object(TurnoBotService, "_esta_en_horario", return_value=True):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono="5491100000003", texto="1", nombre_remitente="Cami", wamid="wamid.menu1"
            )
        conv = ConversacionBot.objects.get(telefono_cliente="5491100000003")
        assert conv.estado == ConversacionBot.Estado.EN_PROCESO
        assert "servicio" in respuesta.lower()

    def test_servicio_no_reconocido_deriva_a_una_persona(self, corte: Servicio) -> None:
        fecha = _proximo_dia_habil()
        with patch.object(TurnoBotService, "_esta_en_horario", return_value=True), patch(
            "apps.bot_asistente.services.InterpreteIA.interpretar_mensaje",
            return_value=_schema(["Servicio inexistente xyz"], fecha),
        ):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono="5491100000002", texto="quiero turno", nombre_remitente="Bea", wamid="wamid.sv1"
            )
        conv = ConversacionBot.objects.get(telefono_cliente="5491100000002")
        assert conv.requiere_humano is True
        assert conv.estado == ConversacionBot.Estado.ESCALADO_HUMANO
        assert "Lorena" in respuesta
        assert Turno.objects.count() == 0

    def test_franja_sin_cupo_deriva_a_una_persona(self, corte: Servicio) -> None:
        fecha = _proximo_dia_habil()
        for i in range(2):  # el cupo simultáneo por defecto es 2
            Turno.objects.create(
                cliente_nombre=f"Clienta {i}",
                servicio=corte,
                fecha=fecha,
                hora=time(15, 0),
                duracion_minutos=45,
                estado=Turno.Estado.CONFIRMADO,
            )
        with patch.object(TurnoBotService, "_esta_en_horario", return_value=True), patch(
            "apps.bot_asistente.services.InterpreteIA.interpretar_mensaje",
            return_value=_schema(["Corte Damas"], fecha),
        ):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono="5491100000001", texto="quiero turno", nombre_remitente="Ana", wamid="wamid.cupo1"
            )
        conv = ConversacionBot.objects.get(telefono_cliente="5491100000001")
        assert conv.requiere_humano is True
        assert conv.estado == ConversacionBot.Estado.ESCALADO_HUMANO
        assert "cupo completo" in respuesta
        assert Turno.objects.count() == 2  # no se creó un tercer turno

    def test_busqueda_del_panel_de_administracion(self) -> None:
        ConversacionBot.objects.create(telefono_cliente="5491100009999", nombre_remitente="Zoe")
        ma = ConversacionBotAdmin(ConversacionBot, admin.site)
        resultado, _ = ma.get_search_results(RequestFactory().get("/"), ConversacionBot.objects.all(), "zoe")
        assert resultado.count() == 1
