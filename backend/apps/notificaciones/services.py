"""
Peluquería Lorena — Servicio de notificaciones (RF 12.4: recordatorio de turno).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone

from apps.bot_asistente.services import normalizar_telefono
from apps.turnos.models import Turno

from .models import Notificacion

logger = logging.getLogger(__name__)


class NotificacionService:
    """Genera y envía los recordatorios automáticos de turno."""

    @staticmethod
    def _inicio_turno(turno: Turno) -> datetime:
        return timezone.make_aware(datetime.combine(turno.fecha, turno.hora))

    @staticmethod
    def _telefono(turno: Turno) -> str:
        telefono = turno.cliente_telefono or (turno.cliente.telefono if turno.cliente else "")
        return normalizar_telefono(telefono)

    @staticmethod
    def _mensaje_recordatorio(turno: Turno) -> str:
        nombre = (turno.cliente_nombre or "").split(" ")[0] or "clienta"
        return (
            f"Hola {nombre}, te recordamos tu turno de {turno.servicio.nombre} hoy a las "
            f"{turno.hora.strftime('%H:%M')} hs en Peluquería Lorena. "
            "Si no podés asistir, avisanos por este medio. ¡Te esperamos!"
        )

    @classmethod
    def enviar_recordatorios_turnos(
        cls,
        ahora: Optional[datetime] = None,
        anticipacion_minutos: Optional[int] = None,
    ) -> dict:
        """
        Envía el recordatorio de los turnos que empiezan dentro de la anticipación configurada
        (por defecto, 60 minutos). Es idempotente: un turno recibe un solo recordatorio, y los
        que fallaron se reintentan en la siguiente ejecución mientras el turno no haya empezado.
        """
        ahora = ahora or timezone.now()
        if anticipacion_minutos is None:
            anticipacion_minutos = settings.RECORDATORIO_TURNO_ANTICIPACION_MINUTOS
        limite = ahora + timedelta(minutes=anticipacion_minutos)
        hoy = timezone.localtime(ahora).date()
        fecha_limite = timezone.localtime(limite).date()

        candidatos = (
            Turno.objects.filter(
                fecha__gte=hoy,
                fecha__lte=fecha_limite,
                estado__in=[Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO],
            )
            .select_related("servicio", "cliente")
            .order_by("fecha", "hora")
        )

        resumen = {"enviadas": 0, "fallidas": 0, "omitidas": 0}
        for turno in candidatos:
            inicio = cls._inicio_turno(turno)
            if not (ahora < inicio <= limite):
                continue
            notificacion, _ = Notificacion.objects.get_or_create(
                turno=turno,
                tipo=Notificacion.Tipo.RECORDATORIO_TURNO,
                defaults={
                    "cliente": turno.cliente,
                    "destinatario": cls._telefono(turno),
                    "mensaje": cls._mensaje_recordatorio(turno),
                },
            )
            if notificacion.estado_envio == Notificacion.EstadoEnvio.ENVIADA:
                resumen["omitidas"] += 1
                continue
            if notificacion.enviar():
                resumen["enviadas"] += 1
            else:
                resumen["fallidas"] += 1
                logger.warning("Recordatorio del turno #%s no enviado: %s", turno.pk, notificacion.detalle_error)
        return resumen
