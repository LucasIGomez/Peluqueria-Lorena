"""
Peluquería Lorena — Intérprete Semántico con Google GenAI SDK (Gemini).

Implementa la llamada estructurada (Structured Outputs) con Pydantic y Gemini
para transformar lenguaje cotidiano libre en intenciones y datos normalizados.
"""
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import List, Optional

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .prompts import generar_system_prompt

logger = logging.getLogger(__name__)


class IntencionEnum(str, Enum):
    """Categorías de intención reconocidas por el bot de WhatsApp."""
    AGENDAR_TURNO = "AGENDAR_TURNO"
    CANCELAR_TURNO = "CANCELAR_TURNO"
    CONSULTAR_PRECIOS = "CONSULTAR_PRECIOS"
    CONSULTAR_TURNOS = "CONSULTAR_TURNOS"
    ESCALAR_HUMANO = "ESCALAR_HUMANO"
    OTRO = "OTRO"


class BotResponseSchema(BaseModel):
    """Esquema de salida estructurada garantizada por el LLM."""
    intencion: IntencionEnum = Field(
        description="Intención principal detectada en el mensaje de la clienta."
    )
    servicios_detectados: List[str] = Field(
        default_factory=list,
        description="Lista de nombres de servicios identificados (ej: ['Corte Damas', 'Balayage'])."
    )
    fecha_sugerida: Optional[str] = Field(
        default=None,
        description="Fecha solicitada o sugerida en formato ISO YYYY-MM-DD. None si no se especificó."
    )
    hora_sugerida: Optional[str] = Field(
        default=None,
        description="Hora solicitada o sugerida en formato HH:MM (24 horas). None si no se especificó."
    )
    mensaje_respuesta: str = Field(
        description="Respuesta redactada para enviar directamente a la clienta por WhatsApp."
    )
    requiere_escalado: bool = Field(
        default=False,
        description="True si la conversación debe ser transferida a atención humana."
    )


class InterpreteIA:
    """
    Encapsula la comunicación con la API de Google GenAI (Gemini)
    para el procesamiento de lenguaje natural estructurado.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model_name = model_name or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    def _obtener_cliente(self) -> genai.Client:
        """Inicializa el cliente oficial del SDK google-genai."""
        if self.api_key:
            return genai.Client(api_key=self.api_key)
        return genai.Client()

    def interpretar_mensaje(self, texto_mensaje: str, catalogo_resumen: str = "") -> BotResponseSchema:
        """
        Envía el mensaje al modelo de lenguaje con el system prompt contextualizado
        y exige una respuesta estructurada conforme al esquema Pydantic.
        """
        system_instruction = generar_system_prompt(catalogo_resumen=catalogo_resumen)

        try:
            client = self._obtener_cliente()
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=BotResponseSchema,
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=texto_mensaje,
                config=config,
            )

            # Extraer el JSON generado
            raw_text = response.text or "{}"
            data = json.loads(raw_text)
            return BotResponseSchema(**data)

        except Exception as exc:
            logger.error("Error al comunicarse con Google GenAI / Gemini: %s", exc, exc_info=True)
            # Fallback seguro para no cortar la comunicación con la clienta
            return BotResponseSchema(
                intencion=IntencionEnum.OTRO,
                servicios_detectados=[],
                fecha_sugerida=None,
                hora_sugerida=None,
                mensaje_respuesta=(
                    "¡Hola! Recibimos tu mensaje en Peluquería Lorena. "
                    "Aguardanos un momento, en breve Lorena o el equipo te responderá personalmente."
                ),
                requiere_escalado=True,
            )
