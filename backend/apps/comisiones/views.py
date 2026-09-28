"""
Peluquería Lorena — Vistas del módulo de Comisiones y Liquidación (RF8).

Implementa:
- Parametrización de comisiones por categoría (RF 8.1).
- Registro rápido e interactivo de trabajos por peluquera (RF 8.2 y RF 8.3).
- Bitácora personal "Mis Comisiones" para profesionales.
- Reporte y liquidación consolidada para la Administradora (RF 8.4).
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.servicios.models import Servicio, ServicioRealizado
from .forms import FiltroLiquidacionForm, RegistroTrabajoForm
from .models import ConfiguracionComision, Liquidacion
from .services import ComisionService


def es_admin_check(user) -> bool:
    return user.is_authenticated and user.es_administradora


# ──────────────────────────────────────────────────────────────
# RF 8.1 — Configuración de Comisiones (Solo Administradora)
# ──────────────────────────────────────────────────────────────


@login_required
@user_passes_test(es_admin_check, login_url="comisiones:mis_comisiones")
def configuracion_comisiones_view(request):
    """
    Permite configurar el porcentaje de comisión por categoría de servicio (RF 8.1).
    Valores relevados oficiales: 50% cortes, 25% trabajos técnicos.
    """
    # Asegurar sembrado inicial si la tabla está vacía
    if not ConfiguracionComision.objects.exists():
        ComisionService.sembrar_configuracion_defecto()

    configs = ConfiguracionComision.objects.all().order_by("categoria")

    if request.method == "POST":
        cambios: list[str] = []
        errores: list[str] = []

        for config in configs:
            campo_pct = f"porcentaje_{config.pk}"
            campo_desc = f"descripcion_{config.pk}"
            campo_act = f"activo_{config.pk}"

            if campo_pct in request.POST:
                try:
                    pct_str = request.POST[campo_pct].strip().replace(",", ".")
                    pct = Decimal(pct_str)
                    if pct < Decimal("0.00") or pct > Decimal("100.00"):
                        errores.append(f"{config.get_categoria_display()}: el porcentaje debe estar entre 0% y 100%.")
                        continue

                    nuevo_desc = request.POST.get(campo_desc, "").strip()
                    nuevo_activo = campo_act in request.POST

                    hubo_cambio = False
                    detalle_cat = []

                    if pct != config.porcentaje:
                        detalle_cat.append(f"{config.porcentaje}% ➔ {pct}%")
                        config.porcentaje = pct
                        hubo_cambio = True

                    if nuevo_activo != config.activo:
                        estado_txt = "activada" if nuevo_activo else "desactivada"
                        detalle_cat.append(estado_txt)
                        config.activo = nuevo_activo
                        hubo_cambio = True

                    if nuevo_desc != config.descripcion:
                        config.descripcion = nuevo_desc
                        hubo_cambio = True

                    if hubo_cambio:
                        config.save()
                        cambios.append(f"{config.get_categoria_display()} ({', '.join(detalle_cat)})")

                except (ValueError, TypeError, Decimal.InvalidOperation):
                    errores.append(f"{config.get_categoria_display()}: porcentaje inválido.")

        if errores:
            for err in errores:
                messages.error(request, err)

        if cambios:
            messages.success(
                request,
                f"Configuración actualizada con éxito. Cambios aplicados: {'; '.join(cambios)}.",
            )
        elif not errores:
            messages.info(request, "No se detectaron modificaciones en las comisiones.")

        return redirect("comisiones:configuracion")

    context = {
        "configuraciones": configs,
        "defaults_relevados": ComisionService.DEFAULTS_RELEVADOS,
    }
    return render(request, "comisiones/configuracion.html", context)


# ──────────────────────────────────────────────────────────────
# RF 8.2 & RF 8.3 — Registro Rápido de Trabajos por Peluquera
# ──────────────────────────────────────────────────────────────


@login_required
def registrar_trabajo_view(request):
    """
    Permite a cada peluquera registrar de forma simple los trabajos que realizó,
    calculando en tiempo real el monto de su comisión sobre el presupuesto pactado.
    """
    ComisionService.sembrar_configuracion_defecto()

    if request.method == "POST":
        form = RegistroTrabajoForm(request.POST, user=request.user)
        if form.is_valid():
            datos = form.cleaned_data
            trabajo = ComisionService.registrar_trabajo_peluquera(
                servicio=datos["servicio"],
                profesional=datos["profesional"],
                cliente_nombre=datos["cliente_nombre"],
                precio_acordado=datos["precio_acordado"],
                cliente_telefono=datos.get("cliente_telefono", ""),
                cliente=datos.get("cliente"),
                fecha=datos.get("fecha"),
                hora=datos.get("hora"),
                notas=datos.get("notas", ""),
                consentimiento=datos.get("consentimiento"),
            )
            messages.success(
                request,
                f"Trabajo asentado: {trabajo.servicio.nombre} a {trabajo.cliente_nombre}. "
                f"Comisión calculada: ${trabajo.monto_comision:,.2f} ({trabajo.porcentaje_comision}%).",
            )
            if "guardar_y_otro" in request.POST:
                return redirect("comisiones:registrar_trabajo")
            return redirect("comisiones:mis_comisiones")
    else:
        initial: Dict[str, Any] = {
            "fecha": timezone.localdate(),
            "hora": timezone.localtime().strftime("%H:%M"),
        }
        if not request.user.es_administradora:
            initial["profesional"] = request.user
        form = RegistroTrabajoForm(initial=initial, user=request.user)

    # Preparamos catálogo enriquecido con tasas de comisión para reactividad JavaScript
    servicios = Servicio.objects.filter(activo=True).select_related()
    porcentajes_map = ComisionService.obtener_porcentajes_activos()

    servicios_data: Dict[str, Dict[str, Any]] = {}
    for s in servicios:
        pct = porcentajes_map.get(s.categoria, Decimal("25.00"))
        servicios_data[str(s.pk)] = {
            "nombre": s.nombre,
            "categoria": s.categoria,
            "categoria_display": s.get_categoria_display(),
            "precio_base": str(s.precio_base),
            "porcentaje_comision": str(pct),
            "duracion": s.duracion_estimada_minutos,
            "requiere_consentimiento": s.requiere_consentimiento,
        }

    clientes_data = {
        str(c.pk): {"nombre": c.nombre, "telefono": str(c.telefono or "")}
        for c in Cliente.objects.filter(activo=True)
    }

    # Trabajos de la profesional en el día de hoy
    prof_id = request.user.pk if not request.user.es_administradora else None
    hoy = timezone.localdate()
    trabajos_hoy_qs = ServicioRealizado.objects.filter(fecha=hoy)
    if prof_id:
        trabajos_hoy_qs = trabajos_hoy_qs.filter(profesional_id=prof_id)

    comision_hoy = sum((t.monto_comision or Decimal("0.00") for t in trabajos_hoy_qs), Decimal("0.00"))

    context = {
        "form": form,
        "servicios_data_json": json.dumps(servicios_data),
        "clientes_data_json": json.dumps(clientes_data),
        "trabajos_hoy": trabajos_hoy_qs.order_by("-hora")[:5],
        "total_trabajos_hoy": trabajos_hoy_qs.count(),
        "total_comision_hoy": comision_hoy,
    }
    return render(request, "comisiones/registro_trabajo.html", context)


# ──────────────────────────────────────────────────────────────
# Bitácora Personal — Mis Comisiones
# ──────────────────────────────────────────────────────────────


@login_required
def mis_comisiones_view(request):
    """
    Bitácora de la peluquera logueada con sus trabajos realizados,
    porcentajes aplicados y comisiones acumuladas.
    """
    profesional = request.user
    hoy = timezone.localdate()

    # Rango por defecto: mes en curso
    primer_dia_mes = hoy.replace(day=1)
    fecha_desde_str = request.GET.get("fecha_desde")
    fecha_hasta_str = request.GET.get("fecha_hasta")

    try:
        fecha_desde = date.fromisoformat(fecha_desde_str) if fecha_desde_str else primer_dia_mes
    except ValueError:
        fecha_desde = primer_dia_mes

    try:
        fecha_hasta = date.fromisoformat(fecha_hasta_str) if fecha_hasta_str else hoy
    except ValueError:
        fecha_hasta = hoy

    resumen = ComisionService.obtener_resumen_liquidacion(
        profesional_id=profesional.pk,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    context = {
        "profesional": profesional,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "servicios": resumen["servicios"],
        "total_servicios": resumen["total_servicios"],
        "total_bruto": resumen["total_bruto"],
        "total_comisiones": resumen["total_comisiones"],
        "por_categoria": resumen["por_categoria"],
    }
    return render(request, "comisiones/mis_comisiones.html", context)


# ──────────────────────────────────────────────────────────────
# RF 8.4 — Reporte de Liquidación (Solo Administradora)
# ──────────────────────────────────────────────────────────────


@login_required
@user_passes_test(es_admin_check, login_url="comisiones:mis_comisiones")
def reporte_liquidacion_view(request):
    """
    Genera el reporte de liquidación de comisiones por peluquera y por período (RF 8.4).
    Muestra KPIs, consolidados por profesional y detalle imprimible.
    """
    hoy = timezone.localdate()
    primer_dia_mes = hoy.replace(day=1)

    filtro_form = FiltroLiquidacionForm(request.GET if request.GET else None)
    if filtro_form.is_valid():
        profesional_seleccionada = filtro_form.cleaned_data.get("profesional")
        profesional_id = profesional_seleccionada.pk if profesional_seleccionada else None
        fecha_desde = filtro_form.cleaned_data.get("fecha_desde") or primer_dia_mes
        fecha_hasta = filtro_form.cleaned_data.get("fecha_hasta") or hoy
    else:
        profesional_seleccionada = None
        profesional_id = None
        fecha_desde = primer_dia_mes
        fecha_hasta = hoy
        if not request.GET:
            filtro_form = FiltroLiquidacionForm(
                initial={
                    "profesional": None,
                    "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta,
                }
            )

    resumen = ComisionService.obtener_resumen_liquidacion(
        profesional_id=profesional_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    context = {
        "filtro_form": filtro_form,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "profesional_seleccionada": profesional_seleccionada,
        "servicios": resumen["servicios"],
        "total_servicios": resumen["total_servicios"],
        "total_bruto": resumen["total_bruto"],
        "total_comisiones": resumen["total_comisiones"],
        "por_profesional": resumen["por_profesional"],
        "por_categoria": resumen["por_categoria"],
        "hoy": hoy,
    }
    return render(request, "comisiones/reporte_liquidacion.html", context)


@login_required
@user_passes_test(es_admin_check, login_url="comisiones:mis_comisiones")
def cerrar_liquidacion_view(request):
    """
    Asienta formalmente el pago de la liquidación a una profesional por período.
    """
    if request.method == "POST":
        profesional_id = request.POST.get("profesional_id")
        fecha_desde_str = request.POST.get("fecha_desde")
        fecha_hasta_str = request.POST.get("fecha_hasta")
        observaciones = request.POST.get("observaciones", "")

        profesional = get_object_or_404(Usuario, pk=profesional_id)
        try:
            fecha_desde = date.fromisoformat(fecha_desde_str)
            fecha_hasta = date.fromisoformat(fecha_hasta_str)
        except (ValueError, TypeError):
            messages.error(request, "Fechas de período inválidas.")
            return redirect("comisiones:reporte_liquidacion")

        liquidacion = ComisionService.cerrar_liquidacion_periodo(
            profesional=profesional,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            liquidado_por=request.user,
            observaciones=observaciones,
        )
        messages.success(
            request,
            f"Liquidación #{liquidacion.pk} asentada exitosamente para {profesional.nombre}. Total abonado: ${liquidacion.total_comision:,.2f}.",
        )
        return redirect(f"/comisiones/liquidacion/?profesional={profesional.pk}&fecha_desde={fecha_desde.isoformat()}&fecha_hasta={fecha_hasta.isoformat()}")

    return redirect("comisiones:reporte_liquidacion")
