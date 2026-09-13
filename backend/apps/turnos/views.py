"""
Peluquería Lorena — Vistas del módulo de Turnos (Agenda).

Vista de agenda (día / semana), alta, edición, cancelación, asignación de
peluquera y cambio de estado. Completar un turno redirige a Servicios para
registrar la atención real (RF4.6), que es lo que queda vinculado al turno.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.usuarios.models import Usuario
from .forms import TurnoForm
from .models import Turno
from .services import TurnoError, TurnoService


def _parsear_fecha(valor: str | None) -> date:
    if valor:
        try:
            return date.fromisoformat(valor)
        except ValueError:
            pass
    return timezone.localdate()


# ──────────────────────────────────────────────────────────────
# Agenda
# ──────────────────────────────────────────────────────────────


@login_required
def agenda_view(request):
    """Tablero de agenda: vista por día o por semana."""
    vista = request.GET.get("vista", "semana")
    fecha = _parsear_fecha(request.GET.get("fecha"))

    context: dict[str, Any] = {
        "vista": vista,
        "fecha": fecha,
        "fecha_str": fecha.isoformat(),
        "hoy": timezone.localdate(),
        "profesionales": Usuario.objects.filter(is_active=True).order_by("nombre"),
        "estados": Turno.Estado.choices,
    }

    if vista == "dia":
        context["turnos"] = TurnoService.listar_turnos_dia(fecha)
        context["dia_anterior"] = (fecha - timedelta(days=1)).isoformat()
        context["dia_siguiente"] = (fecha + timedelta(days=1)).isoformat()
    else:
        inicio_semana = fecha - timedelta(days=fecha.weekday())
        dias = [inicio_semana + timedelta(days=i) for i in range(7)]
        turnos_semana = TurnoService.listar_turnos_rango(dias[0], dias[-1])
        turnos_por_dia: dict[date, list[Turno]] = {d: [] for d in dias}
        for turno in turnos_semana:
            turnos_por_dia[turno.fecha].append(turno)
        context["dias_semana"] = [{"fecha": d, "turnos": turnos_por_dia[d]} for d in dias]
        context["semana_anterior"] = (inicio_semana - timedelta(days=7)).isoformat()
        context["semana_siguiente"] = (inicio_semana + timedelta(days=7)).isoformat()

    return render(request, "turnos/agenda.html", context)


# ──────────────────────────────────────────────────────────────
# Alta, edición y cancelación
# ──────────────────────────────────────────────────────────────


@login_required
def crear_turno_view(request):
    """Agenda un nuevo turno."""
    if request.method == "POST":
        form = TurnoForm(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                turno = TurnoService.crear_turno(
                    cliente_nombre=datos["cliente_nombre"],
                    servicio=datos["servicio"],
                    fecha=datos["fecha"],
                    hora=datos["hora"],
                    cliente=datos.get("cliente"),
                    cliente_telefono=datos.get("cliente_telefono", ""),
                    profesional=datos.get("profesional"),
                    duracion_minutos=datos.get("duracion_minutos"),
                    notas=datos.get("notas", ""),
                )
                messages.success(
                    request,
                    f"Turno agendado para {turno.cliente_nombre} el {turno.fecha.strftime('%d/%m/%Y')} a las "
                    f"{turno.hora.strftime('%H:%M')}.",
                )
                return redirect(f"{reverse('turnos:agenda')}?vista=dia&fecha={turno.fecha.isoformat()}")
            except TurnoError as exc:
                form.add_error(None, str(exc))
    else:
        initial: dict[str, Any] = {"fecha": _parsear_fecha(request.GET.get("fecha")), "hora": "09:00"}
        cliente_id = request.GET.get("cliente")
        if cliente_id:
            from apps.clientes.models import Cliente

            cli = Cliente.objects.filter(pk=cliente_id).first()
            if cli:
                initial["cliente"] = cli
                initial["cliente_nombre"] = cli.nombre
                initial["cliente_telefono"] = cli.telefono
        form = TurnoForm(initial=initial)

    from apps.servicios.models import Servicio

    servicios = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
    duraciones = {str(s.pk): s.duracion_estimada_minutos for s in servicios}

    return render(
        request,
        "turnos/form_turno.html",
        {"form": form, "accion": "Agendar Turno", "duraciones": duraciones},
    )


@login_required
def editar_turno_view(request, pk: int):
    """Edita un turno existente (horario, servicio, peluquera o notas)."""
    turno = get_object_or_404(Turno, pk=pk)

    if request.method == "POST":
        form = TurnoForm(request.POST, instance=turno)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                TurnoService.editar_turno(
                    turno,
                    cliente_nombre=datos["cliente_nombre"],
                    cliente_telefono=datos.get("cliente_telefono", ""),
                    servicio=datos["servicio"],
                    fecha=datos["fecha"],
                    hora=datos["hora"],
                    profesional=datos.get("profesional"),
                    duracion_minutos=datos.get("duracion_minutos"),
                    notas=datos.get("notas", ""),
                )
                messages.success(request, "Turno actualizado correctamente.")
                return redirect(f"{reverse('turnos:agenda')}?vista=dia&fecha={turno.fecha.isoformat()}")
            except TurnoError as exc:
                form.add_error(None, str(exc))
    else:
        form = TurnoForm(instance=turno)

    from apps.servicios.models import Servicio

    servicios = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
    duraciones = {str(s.pk): s.duracion_estimada_minutos for s in servicios}

    return render(
        request,
        "turnos/form_turno.html",
        {"form": form, "accion": "Editar Turno", "turno": turno, "duraciones": duraciones},
    )


@login_required
def cancelar_turno_view(request, pk: int):
    """Cancela un turno, liberando el horario de la peluquera."""
    turno = get_object_or_404(Turno, pk=pk)
    if request.method == "POST":
        try:
            TurnoService.cancelar_turno(turno)
            messages.success(request, f"Turno de {turno.cliente_nombre} cancelado.")
        except TurnoError as exc:
            messages.error(request, str(exc))
        return redirect(f"{reverse('turnos:agenda')}?vista=dia&fecha={turno.fecha.isoformat()}")
    return render(request, "turnos/cancelar_turno.html", {"turno": turno})


# ──────────────────────────────────────────────────────────────
# Acciones rápidas desde la agenda
# ──────────────────────────────────────────────────────────────


@login_required
def asignar_profesional_view(request, pk: int):
    """Asigna o reasigna la peluquera de un turno desde la agenda."""
    turno = get_object_or_404(Turno, pk=pk)
    if request.method == "POST":
        profesional_id = request.POST.get("profesional")
        profesional = Usuario.objects.filter(pk=profesional_id, is_active=True).first() if profesional_id else None
        try:
            TurnoService.asignar_profesional(turno, profesional)
            messages.success(request, "Turno reasignado correctamente.")
        except TurnoError as exc:
            messages.error(request, str(exc))
    return redirect(f"{reverse('turnos:agenda')}?vista={request.POST.get('vista', 'dia')}&fecha={request.POST.get('fecha', turno.fecha.isoformat())}")


@login_required
def cambiar_estado_view(request, pk: int):
    """Cambia el estado del turno (confirmar / marcar ausente) desde la agenda."""
    turno = get_object_or_404(Turno, pk=pk)
    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")
        try:
            TurnoService.cambiar_estado(turno, nuevo_estado)
            messages.success(request, f"Turno marcado como {turno.get_estado_display()}.")
        except TurnoError as exc:
            messages.error(request, str(exc))
    return redirect(f"{reverse('turnos:agenda')}?vista={request.POST.get('vista', 'dia')}&fecha={request.POST.get('fecha', turno.fecha.isoformat())}")


@login_required
def completar_turno_view(request, pk: int):
    """Redirige a Servicios para registrar la atención real vinculada a este turno."""
    turno = get_object_or_404(Turno, pk=pk)
    if turno.estado == Turno.Estado.CANCELADO:
        messages.error(request, "No se puede completar un turno cancelado.")
        return redirect(f"{reverse('turnos:agenda')}?vista=dia&fecha={turno.fecha.isoformat()}")
    return redirect(f"{reverse('servicios:registrar_servicio_realizado')}?turno={turno.pk}")


# ── Aliases camelCase ──
agendaView = agenda_view
crearTurnoView = crear_turno_view
editarTurnoView = editar_turno_view
cancelarTurnoView = cancelar_turno_view
asignarProfesionalView = asignar_profesional_view
cambiarEstadoView = cambiar_estado_view
completarTurnoView = completar_turno_view
