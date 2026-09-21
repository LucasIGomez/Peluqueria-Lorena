"""
Peluquería Lorena — Validador de Horarios Comerciales del Bot de WhatsApp.

Regla de negocio:
- El bot solo procesa consultas y turnos dentro del horario comercial del salón.
- Días de atención: Martes a Sábado (Lunes y Domingo cerrado).
- Rango horario: 09:00 a 19:00.
- Fuera de este rango, responde cordialmente indicando los horarios sin procesar ni agendar turnos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from django.conf import settings
from django.utils import timezone


class BusinessHoursValidator:
    """Validador de reglas de apertura y horario del salón."""

    DIAS_HABILITADOS = [1, 2, 3, 4, 5]  # Martes (1) a Sábado (5). 0=Lunes, 6=Domingo
    HORA_APERTURA = 9                  # 09:00
    HORA_CIERRE = 19                   # 19:00

    @classmethod
    def esta_en_horario(cls, dt: Optional[datetime] = None) -> bool:
        """
        Determina si una fecha/hora dada (o el momento actual) se encuentra
        dentro de la franja comercial de Peluquería Lorena.
        """
        if dt is None:
            dt = timezone.localtime()

        # Validar día de la semana
        if dt.weekday() not in cls.DIAS_HABILITADOS:
            return False

        # Validar franja horaria (09:00:00 a 18:59:59)
        if dt.hour < cls.HORA_APERTURA or dt.hour >= cls.HORA_CIERRE:
            return False

        return True

    @classmethod
    def obtener_mensaje_fuera_de_horario(cls) -> str:
        """
        Genera el mensaje cordial estándar para responder a mensajes
        que ingresan cuando el salón se encuentra cerrado.
        """
        return (
            "¡Hola! Gracias por comunicarte con *Peluquería Lorena* 💇‍♀️✨.\n\n"
            "En este momento nuestro salón se encuentra cerrado. "
            "Nuestros días y horarios de atención son de *Martes a Sábado de 09:00 a 19:00 hs*.\n\n"
            "Te responderemos a la brevedad en cuanto retomemos la atención. ¡Que tengas un excelente día!"
        )
