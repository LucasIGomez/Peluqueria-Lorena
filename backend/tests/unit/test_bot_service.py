"""
Peluquería Lorena — Pruebas unitarias para TurnoBotService.
"""
from datetime import date, time
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from apps.bot_asistente.ai.interpreter import BotResponseSchema, IntencionEnum
from apps.bot_asistente.models import ConversacionBot
from apps.bot_asistente.services import TurnoBotService
from apps.clientes.models import Cliente
from apps.servicios.models import Servicio
from apps.turnos.models import Turno


@pytest.mark.django_db
class TestTurnoBotService:
    """Verifica las reglas de negocio, agendado en bolsa común y opciones del menú."""

    @pytest.fixture(autouse=True)
    def setup_servicios(self) -> None:
        self.corte = Servicio.objects.create(
            nombre="Corte Damas",
            categoria=Servicio.Categoria.CORTES,
            precio_base=Decimal("15000.00"),
            duracion_estimada_minutos=45,
            requiere_consentimiento=False,
        )
        self.balayage = Servicio.objects.create(
            nombre="Balayage",
            categoria=Servicio.Categoria.MECHAS,
            precio_base=Decimal("120000.00"),
            duracion_estimada_minutos=180,
            requiere_consentimiento=True,
        )

    def test_menu_primer_contacto(self) -> None:
        """Un saludo o primer contacto muestra el menú numérico guiado."""
        telefono = "5491122334455"
        with patch.object(TurnoBotService, "_esta_en_horario", return_value=True):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono=telefono,
                texto="Hola",
                nombre_remitente="Camila",
            )

        assert "1️⃣ Sacar turno" in respuesta
        assert "2️⃣ Cancelar turno" in respuesta
        assert "3️⃣ Ver mis turnos" in respuesta
        assert "4️⃣ Consultar precios" in respuesta
        assert "5️⃣ Hablar con alguien" in respuesta

    def test_opcion_4_consulta_precios(self) -> None:
        """La opción 4 lista los precios oficiales del catálogo con aviso para técnicos."""
        telefono = "5491122334455"
        with patch.object(TurnoBotService, "_esta_en_horario", return_value=True):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono=telefono,
                texto="4",
                nombre_remitente="Camila",
            )

        assert "Corte Damas" in respuesta
        assert "15.000" in respuesta or "15000" in respuesta
        assert "Balayage" in respuesta
        assert "diagnóstico presencial" in respuesta

    def test_opcion_5_escalado_humano(self) -> None:
        """La opción 5 marca la conversación para derivación a Lorena/Zaira."""
        telefono = "5491122334455"
        with patch.object(TurnoBotService, "_esta_en_horario", return_value=True):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono=telefono,
                texto="5",
                nombre_remitente="Camila",
            )

        conv = ConversacionBot.objects.get(telefono_cliente=telefono)
        assert conv.requiere_humano is True
        assert "Lorena" in respuesta or "Zaira" in respuesta

    def test_agendado_automatico_en_bolsa_comun(self) -> None:
        """Si la IA detecta agendar turno en horario comercial, crea el Turno con profesional=None."""
        telefono = "5491122334455"
        mock_schema = BotResponseSchema(
            intencion=IntencionEnum.AGENDAR_TURNO,
            servicios_detectados=["Corte Damas"],
            fecha_sugerida="2026-09-24",
            hora_sugerida="15:00",
            mensaje_respuesta="¡Perfecto! Te agendé para Corte Damas este jueves 24/09 a las 15:00.",
            requiere_escalado=False,
        )

        with patch.object(TurnoBotService, "_esta_en_horario", return_value=True), \
             patch("apps.bot_asistente.services.InterpreteIA.interpretar_mensaje", return_value=mock_schema):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono=telefono,
                texto="Quiero turno para corte el jueves a las 15hs porfa",
                nombre_remitente="Romina Test",
            )

        # Verifica que el turno fue creado en base de datos
        turno = Turno.objects.filter(cliente_telefono=telefono).first()
        assert turno is not None
        assert turno.servicio == self.corte
        assert turno.profesional is None  # Bolsa común
        assert turno.fecha == date(2026, 9, 24)
        assert turno.hora == time(15, 0)
        assert turno.duracion_minutos == 45
        assert turno.estado in [Turno.Estado.CONFIRMADO, Turno.Estado.PENDIENTE]

        # Verifica que la clienta fue vinculada o creada
        cliente = Cliente.objects.filter(telefono=telefono).first()
        assert cliente is not None
        assert turno.cliente == cliente

    def test_rechazo_y_mensaje_cordial_fuera_de_horario(self) -> None:
        """Si el mensaje ingresa fuera de horario comercial, no agenda y devuelve mensaje cordial."""
        telefono = "5491122334455"
        with patch.object(TurnoBotService, "_esta_en_horario", return_value=False):
            respuesta = TurnoBotService.procesar_mensaje(
                telefono=telefono,
                texto="Quiero un turno para mañana a las 10",
                nombre_remitente="Romina Test",
            )

        # No debe haberse creado turno alguno
        assert Turno.objects.filter(cliente_telefono=telefono).count() == 0
        assert "Martes a Sábado" in respuesta
        assert "09:00" in respuesta
