"""
Peluquería Lorena — Modelos del módulo de Notificaciones (RF 12.4).

Registra cada aviso automático que el sistema envía a una clienta. Por ahora
el único tipo es el recordatorio de turno, enviado por WhatsApp antes del horario.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class Notificacion(models.Model):
    """Aviso automático enviado (o por enviar) a una clienta."""

    class Tipo(models.TextChoices):
        RECORDATORIO_TURNO = "RECORDATORIO_TURNO", "Recordatorio de turno"

    class EstadoEnvio(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADA = "ENVIADA", "Enviada"
        FALLIDA = "FALLIDA", "Fallida"

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notificaciones",
        verbose_name="clienta",
    )
    turno = models.ForeignKey(
        "turnos.Turno",
        on_delete=models.CASCADE,
        related_name="notificaciones",
        verbose_name="turno",
    )
    tipo = models.CharField("tipo", max_length=30, choices=Tipo.choices)
    destinatario = models.CharField("teléfono de destino", max_length=50, blank=True)
    mensaje = models.TextField("mensaje")
    estado_envio = models.CharField(
        "estado de envío",
        max_length=10,
        choices=EstadoEnvio.choices,
        default=EstadoEnvio.PENDIENTE,
        db_index=True,
    )
    detalle_error = models.CharField("detalle del error", max_length=500, blank=True)
    fecha_envio = models.DateTimeField("fecha de envío", null=True, blank=True)
    fecha_creacion = models.DateTimeField("fecha de creación", default=timezone.now)

    class Meta:
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        ordering = ["-fecha_creacion"]
        constraints = [
            models.UniqueConstraint(fields=["turno", "tipo"], name="notificacion_unica_por_turno_y_tipo"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — turno #{self.turno_id} ({self.get_estado_envio_display()})"

    def enviar(self) -> bool:
        """Envía el mensaje por WhatsApp y registra el resultado. Devuelve True si salió."""
        from apps.bot_asistente.handlers.whatsapp_client import WhatsAppCloudApiClient

        cliente_api = WhatsAppCloudApiClient()
        if not self.destinatario:
            self.estado_envio = self.EstadoEnvio.FALLIDA
            self.detalle_error = "La clienta no tiene teléfono cargado."
        elif not cliente_api.esta_configurado:
            self.estado_envio = self.EstadoEnvio.FALLIDA
            self.detalle_error = "WhatsApp no está configurado (faltan credenciales de Meta)."
        elif cliente_api.enviar_texto(self.destinatario, self.mensaje):
            self.estado_envio = self.EstadoEnvio.ENVIADA
            self.detalle_error = ""
            self.fecha_envio = timezone.now()
        else:
            self.estado_envio = self.EstadoEnvio.FALLIDA
            self.detalle_error = "Meta rechazó el mensaje o no hubo conexión."
        self.save(update_fields=["estado_envio", "detalle_error", "fecha_envio"])
        return self.estado_envio == self.EstadoEnvio.ENVIADA
