"""
Peluquería Lorena — Capa de servicios del módulo de Turnos (Agenda).

Centraliza la lógica de negocio: alta/edición de turnos, control de
solapamiento de horarios por peluquera, cambios de estado y el enlace con
Servicios cuando un turno se atiende de verdad (RF4.6).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from django.db import transaction
from django.db.models import QuerySet

from .models import Turno


class TurnoError(Exception):
    """Excepción base del módulo de turnos."""


class TurnoInvalidoError(TurnoError):
    """Se lanza cuando los datos del turno no son válidos."""


class SolapamientoError(TurnoError):
    """Se lanza cuando el turno se superpone con otro de la misma peluquera."""


class TurnoService:
    """Servicio de dominio para la agenda de turnos."""

    # ── Solapamiento de horarios ──

    @staticmethod
    def hay_solapamiento(
        profesional: Any,
        fecha: date,
        hora: time,
        duracion_minutos: int,
        excluir_pk: Optional[int] = None,
    ) -> bool:
        """
        Indica si la peluquera ya tiene un turno vigente que se superpone
        con el horario indicado. Sin peluquera asignada no hay conflicto
        posible (el turno queda en una bolsa común hasta que se asigne).
        """
        if profesional is None:
            return False

        inicio = datetime.combine(fecha, hora)
        fin = inicio + timedelta(minutes=duracion_minutos)

        candidatos: QuerySet[Turno] = Turno.objects.filter(
            profesional=profesional, fecha=fecha
        ).exclude(estado__in=[Turno.Estado.CANCELADO, Turno.Estado.AUSENTE])
        if excluir_pk is not None:
            candidatos = candidatos.exclude(pk=excluir_pk)

        for turno in candidatos:
            t_inicio = datetime.combine(turno.fecha, turno.hora)
            t_fin = t_inicio + timedelta(minutes=turno.duracion_minutos)
            if inicio < t_fin and t_inicio < fin:
                return True
        return False

    @classmethod
    def haySolapamiento(cls, *args: Any, **kwargs: Any) -> bool:
        return cls.hay_solapamiento(*args, **kwargs)

    # ── Alta y edición ──

    @classmethod
    def crear_turno(
        cls,
        cliente_nombre: str,
        servicio: Any,
        fecha: date,
        hora: time,
        cliente: Any = None,
        cliente_telefono: str = "",
        profesional: Any = None,
        duracion_minutos: Optional[int] = None,
        notas: str = "",
    ) -> Turno:
        """Agenda un nuevo turno, validando datos mínimos y solapamiento."""
        if not cliente_nombre or not cliente_nombre.strip():
            raise TurnoInvalidoError("El nombre de la clienta es obligatorio.")
        if servicio is None:
            raise TurnoInvalidoError("Debe seleccionar un servicio.")

        duracion = duracion_minutos or servicio.duracion_estimada_minutos
        if duracion <= 0:
            raise TurnoInvalidoError("La duración del turno debe ser mayor a cero.")

        if cls.hay_solapamiento(profesional, fecha, hora, duracion):
            raise SolapamientoError(
                f"{getattr(profesional, 'nombre', 'La peluquera')} ya tiene un turno asignado en ese horario."
            )

        return Turno.objects.create(
            cliente=cliente,
            cliente_nombre=cliente_nombre.strip(),
            cliente_telefono=cliente_telefono.strip() if cliente_telefono else "",
            servicio=servicio,
            profesional=profesional,
            fecha=fecha,
            hora=hora,
            duracion_minutos=duracion,
            notas=notas.strip() if notas else "",
            estado=Turno.Estado.CONFIRMADO if profesional is not None else Turno.Estado.PENDIENTE,
        )

    @classmethod
    def crearTurno(cls, *args: Any, **kwargs: Any) -> Turno:
        return cls.crear_turno(*args, **kwargs)

    @classmethod
    def editar_turno(
        cls,
        turno: Turno,
        cliente_nombre: Optional[str] = None,
        cliente_telefono: Optional[str] = None,
        servicio: Any = None,
        fecha: Optional[date] = None,
        hora: Optional[time] = None,
        profesional: Any = "__sin_cambios__",
        duracion_minutos: Optional[int] = None,
        notas: Optional[str] = None,
    ) -> Turno:
        """Edita un turno existente, re-validando solapamiento con los nuevos datos."""
        if turno.estado in (Turno.Estado.CANCELADO, Turno.Estado.COMPLETADO):
            raise TurnoInvalidoError("No se puede editar un turno cancelado o ya completado.")

        nueva_fecha = fecha or turno.fecha
        nueva_hora = hora or turno.hora
        nueva_duracion = duracion_minutos or turno.duracion_minutos
        nuevo_profesional = turno.profesional if profesional == "__sin_cambios__" else profesional

        if cls.hay_solapamiento(nuevo_profesional, nueva_fecha, nueva_hora, nueva_duracion, excluir_pk=turno.pk):
            raise SolapamientoError(
                f"{getattr(nuevo_profesional, 'nombre', 'La peluquera')} ya tiene un turno asignado en ese horario."
            )

        if cliente_nombre is not None:
            turno.cliente_nombre = cliente_nombre.strip()
        if cliente_telefono is not None:
            turno.cliente_telefono = cliente_telefono.strip()
        if servicio is not None:
            turno.servicio = servicio
        turno.fecha = nueva_fecha
        turno.hora = nueva_hora
        turno.duracion_minutos = nueva_duracion
        if profesional != "__sin_cambios__":
            turno.profesional = nuevo_profesional
        if notas is not None:
            turno.notas = notas.strip()

        turno.save()
        return turno

    @classmethod
    def editarTurno(cls, *args: Any, **kwargs: Any) -> Turno:
        return cls.editar_turno(*args, **kwargs)

    # ── Asignación de peluquera ──

    @classmethod
    def asignar_profesional(cls, turno: Turno, profesional: Any) -> Turno:
        """Asigna o reasigna la peluquera que atiende el turno."""
        if turno.estado in (Turno.Estado.CANCELADO, Turno.Estado.COMPLETADO):
            raise TurnoInvalidoError("No se puede reasignar un turno cancelado o ya completado.")
        if cls.hay_solapamiento(profesional, turno.fecha, turno.hora, turno.duracion_minutos, excluir_pk=turno.pk):
            raise SolapamientoError(
                f"{getattr(profesional, 'nombre', 'La peluquera')} ya tiene un turno asignado en ese horario."
            )
        turno.profesional = profesional
        if profesional is not None and turno.estado == Turno.Estado.PENDIENTE:
            turno.estado = Turno.Estado.CONFIRMADO
        turno.save(update_fields=["profesional", "estado"])
        return turno

    @classmethod
    def asignarProfesional(cls, *args: Any, **kwargs: Any) -> Turno:
        return cls.asignar_profesional(*args, **kwargs)

    # ── Estados ──

    @classmethod
    def cambiar_estado(cls, turno: Turno, nuevo_estado: str) -> Turno:
        """Cambia el estado del turno (confirmar / marcar ausente / cancelar)."""
        if nuevo_estado not in Turno.Estado.values:
            raise TurnoInvalidoError(f"Estado inválido: {nuevo_estado}.")
        if turno.estado == Turno.Estado.COMPLETADO:
            raise TurnoInvalidoError("El turno ya fue completado, no se puede modificar.")
        if turno.estado == Turno.Estado.CANCELADO and nuevo_estado != Turno.Estado.CANCELADO:
            raise TurnoInvalidoError("El turno está cancelado.")
        if nuevo_estado == Turno.Estado.COMPLETADO:
            raise TurnoInvalidoError(
                "Un turno se completa registrando la atención real en Servicios, no cambiando el estado directamente."
            )
        turno.estado = nuevo_estado
        turno.save(update_fields=["estado"])
        return turno

    @classmethod
    def cambiarEstado(cls, *args: Any, **kwargs: Any) -> Turno:
        return cls.cambiar_estado(*args, **kwargs)

    @classmethod
    def cancelar_turno(cls, turno: Turno) -> Turno:
        """Cancela el turno, liberando el horario de la peluquera."""
        if turno.estado == Turno.Estado.COMPLETADO:
            raise TurnoInvalidoError("No se puede cancelar un turno ya completado.")
        turno.estado = Turno.Estado.CANCELADO
        turno.save(update_fields=["estado"])
        return turno

    @classmethod
    def cancelarTurno(cls, *args: Any, **kwargs: Any) -> Turno:
        return cls.cancelar_turno(*args, **kwargs)

    @classmethod
    @transaction.atomic
    def completar_turno(cls, turno: Turno, servicio_realizado: Any) -> Turno:
        """
        Vincula el turno con la atención ya registrada en Servicios
        (RF4.6) y lo marca como completado.
        """
        if turno.estado == Turno.Estado.CANCELADO:
            raise TurnoInvalidoError("No se puede completar un turno cancelado.")
        turno.servicio_realizado = servicio_realizado
        turno.estado = Turno.Estado.COMPLETADO
        turno.save(update_fields=["servicio_realizado", "estado"])
        return turno

    @classmethod
    def completarTurno(cls, *args: Any, **kwargs: Any) -> Turno:
        return cls.completar_turno(*args, **kwargs)

    # ── Consultas de agenda ──

    @staticmethod
    def listar_turnos_dia(fecha: date) -> QuerySet[Turno]:
        """Lista todos los turnos de un día (incluidos cancelados, para verlos en la agenda)."""
        return Turno.objects.filter(fecha=fecha).select_related(
            "cliente", "servicio", "profesional", "servicio_realizado"
        ).order_by("hora")

    @staticmethod
    def listarTurnosDia(*args: Any, **kwargs: Any) -> QuerySet[Turno]:
        return TurnoService.listar_turnos_dia(*args, **kwargs)

    @staticmethod
    def listar_turnos_rango(fecha_desde: date, fecha_hasta: date) -> QuerySet[Turno]:
        """Lista los turnos de un rango de fechas (para la vista semanal)."""
        return Turno.objects.filter(
            fecha__gte=fecha_desde, fecha__lte=fecha_hasta
        ).select_related("cliente", "servicio", "profesional", "servicio_realizado").order_by("fecha", "hora")

    @staticmethod
    def listarTurnosRango(*args: Any, **kwargs: Any) -> QuerySet[Turno]:
        return TurnoService.listar_turnos_rango(*args, **kwargs)
