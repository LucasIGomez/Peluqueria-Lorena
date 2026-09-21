"""
Peluquería Lorena — Pruebas unitarias para InterpreteIA con Google GenAI SDK.
"""
from unittest.mock import MagicMock, patch
import pytest

from apps.bot_asistente.ai.interpreter import BotResponseSchema, InterpreteIA, IntencionEnum


class TestBotInterpreter:
    """Verifica la interpretación semántica y extracción estructurada con Gemini."""

    def test_schema_pydantic_valido(self) -> None:
        """Comprueba que el esquema estructurado valide correctamente."""
        data = {
            "intencion": "AGENDAR_TURNO",
            "servicios_detectados": ["Corte", "Color"],
            "fecha_sugerida": "2026-09-24",
            "hora_sugerida": "15:30",
            "mensaje_respuesta": "¡Hola! Te puedo agendar un turno para Corte y Color el jueves a las 15:30.",
            "requiere_escalado": False,
        }
        obj = BotResponseSchema(**data)
        assert obj.intencion == IntencionEnum.AGENDAR_TURNO
        assert "Corte" in obj.servicios_detectados
        assert obj.fecha_sugerida == "2026-09-24"
        assert obj.hora_sugerida == "15:30"
        assert obj.requiere_escalado is False

    @patch("apps.bot_asistente.ai.interpreter.genai.Client")
    def test_interprete_extrae_intencion_agendar_turno(self, mock_client_cls: MagicMock) -> None:
        """Simula respuesta estructurada de Gemini para solicitud de turno."""
        mock_response = MagicMock()
        mock_response.text = (
            '{"intencion": "AGENDAR_TURNO", "servicios_detectados": ["Corte Damas"], '
            '"fecha_sugerida": "2026-09-24", "hora_sugerida": "16:00", '
            '"mensaje_respuesta": "¡Perfecto! Te reservo para Corte Damas este jueves a las 16:00.", '
            '"requiere_escalado": false}'
        )

        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        interprete = InterpreteIA(api_key="test-api-key")
        resultado = interprete.interpretar_mensaje(
            texto_mensaje="Hola! Tenés un turno para corte este jueves a las 16hs?",
            catalogo_resumen="Corte Damas ($15.000)",
        )

        assert resultado.intencion == IntencionEnum.AGENDAR_TURNO
        assert "Corte Damas" in resultado.servicios_detectados
        assert resultado.fecha_sugerida == "2026-09-24"
        assert resultado.hora_sugerida == "16:00"
        assert resultado.requiere_escalado is False

    @patch("apps.bot_asistente.ai.interpreter.genai.Client")
    def test_interprete_consulta_precios_servicio_tecnico(self, mock_client_cls: MagicMock) -> None:
        """Simula consulta de precios aclarando diagnóstico presencial obligatorio para técnicos."""
        mock_response = MagicMock()
        mock_response.text = (
            '{"intencion": "CONSULTAR_PRECIOS", "servicios_detectados": ["Balayage"], '
            '"fecha_sugerida": null, "hora_sugerida": null, '
            '"mensaje_respuesta": "El Balayage tiene un precio base desde $120.000. '
            'El valor final depende del largo y volumen, y se define en un diagnóstico presencial en el salón.", '
            '"requiere_escalado": false}'
        )

        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        interprete = InterpreteIA(api_key="test-api-key")
        resultado = interprete.interpretar_mensaje(
            texto_mensaje="Hola, cuánto cuesta hacerme un balayage?",
            catalogo_resumen="Balayage (desde $120.000)",
        )

        assert resultado.intencion == IntencionEnum.CONSULTAR_PRECIOS
        assert "Balayage" in resultado.servicios_detectados
        assert "diagnóstico presencial" in resultado.mensaje_respuesta

    @patch("apps.bot_asistente.ai.interpreter.genai.Client")
    def test_interprete_detecta_escalado_a_humano(self, mock_client_cls: MagicMock) -> None:
        """Simula detección de pedido explícito o reclamo que requiere derivación humana."""
        mock_response = MagicMock()
        mock_response.text = (
            '{"intencion": "ESCALAR_HUMANO", "servicios_detectados": [], '
            '"fecha_sugerida": null, "hora_sugerida": null, '
            '"mensaje_respuesta": "Te comunico enseguida con Lorena para que te atienda personalmente.", '
            '"requiere_escalado": true}'
        )

        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance

        interprete = InterpreteIA(api_key="test-api-key")
        resultado = interprete.interpretar_mensaje(
            texto_mensaje="Tengo un reclamo sobre el color que me hicieron la semana pasada",
        )

        assert resultado.intencion == IntencionEnum.ESCALAR_HUMANO
        assert resultado.requiere_escalado is True

    @patch("apps.bot_asistente.ai.interpreter.genai.Client")
    def test_interprete_fallback_ante_error_de_api(self, mock_client_cls: MagicMock) -> None:
        """Ante excepción en la llamada a la API de Google, devuelve fallback seguro."""
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = Exception("API connection timeout")
        mock_client_cls.return_value = mock_instance

        interprete = InterpreteIA(api_key="test-api-key")
        resultado = interprete.interpretar_mensaje(
            texto_mensaje="Hola, quiero reservar para el viernes",
        )

        assert resultado.intencion == IntencionEnum.OTRO
        assert resultado.requiere_escalado is True
        assert "un momento" in resultado.mensaje_respuesta.lower() or "Lorena" in resultado.mensaje_respuesta
