"""
Peluquería Lorena — Modelos del módulo de Turnos (Agenda).

Define la reserva de un horario para una clienta (Turno). Es un registro de
agenda, independiente del cobro/ejecución real del servicio: cuando el turno
se atiende, se vincula a una atención de apps.servicios.ServicioRealizado
(RF4.6), que es donde se factura y se descuenta stock.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import models


class Turno(models.Model):
    """
    Reserva de un horario de atención para una clienta.

    Las clientas no eligen peluquera al pedir el turno: la asignación de
    `profesional` la hacen la dueña y la empleada internamente (puede quedar
    sin asignar hasta el día de la atención).
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        CONFIRMADO = "CONFIRMADO", "Confirmado"
        CANCELADO = "CANCELADO", "Cancelado"
        AUSENTE = "AUSENTE", "Ausente"
        COMPLETADO = "COMPLETADO", "Completado"

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turnos",
        verbose_name="clienta vinculada",
    )
    cliente_nombre = models.CharField("nombre de la clienta", max_length=200)
    cliente_telefono = models.CharField("teléfono de contacto", max_length=50, blank=True)
    servicio = models.ForeignKey(
        "servicios.Servicio",
        on_delete=models.PROTECT,
        related_name="turnos",
        verbose_name="servicio solicitado",
    )
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turnos_asignados",
        verbose_name="peluquera asignada",
    )
    servicio_realizado = models.ForeignKey(
        "servicios.ServicioRealizado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turno_origen",
        verbose_name="atención generada",
    )
    fecha = models.DateField("fecha del turno", db_index=True)
    hora = models.TimeField("hora del turno")
    duracion_minutos = models.PositiveIntegerField("duración estimada (minutos)", default=60)
    estado = models.CharField(
        "estado",
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
    )
    notas = models.TextField("notas", blank=True)
    fecha_creacion = models.DateTimeField("fecha de registro", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("última actualización", auto_now=True)

    class Meta:
        verbose_name = "turno"
        verbose_name_plural = "turnos"
        ordering = ["fecha", "hora"]

    def __str__(self) -> str:
        return (
            f"Turno {self.cliente_nombre} — {self.servicio.nombre} "
            f"({self.fecha.strftime('%d/%m/%Y')} {self.hora.strftime('%H:%M')})"
        )

    # ── Propiedades de dominio ──

    @property
    def hora_fin(self):
        """Hora de finalización estimada, según la duración del turno."""
        inicio = datetime.combine(self.fecha, self.hora)
        return (inicio + timedelta(minutes=self.duracion_minutos)).time()

    @property
    def esta_activo(self) -> bool:
        """Indica si el turno todavía ocupa un horario (no cancelado)."""
        return self.estado != self.Estado.CANCELADO

    # ── Aliases camelCase ──

    @property
    def horaFin(self):
        return self.hora_fin

    @property
    def estaActivo(self) -> bool:
        return self.esta_activo

    @property
    def clienteNombre(self) -> str:
        return self.cliente_nombre

    @property
    def duracionMinutos(self) -> int:
        return self.duracion_minutos
