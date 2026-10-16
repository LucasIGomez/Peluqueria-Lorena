"""
Peluquería Lorena — Servicio del Dashboard (RF 2).

Centraliza la lógica de negocio y consultas de los requerimientos funcionales:
- RF 2.1: Turnos del día
- RF 2.2: Resumen de ingresos (día, semana y mes)
- RF 2.3: Alertas de stock mínimo
- RF 2.4: Próximos turnos agendados
- RF 2.5: Cumpleaños del mes en curso
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict

from django.db.models import Sum
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.inventario.models import Producto
from apps.inventario.services import InventarioService
from apps.pagos.models import Cobro
from apps.turnos.models import Turno


class DashboardService:
    """Servicio de cálculo y consolidación de métricas para la pantalla de inicio."""

    @classmethod
    def obtener_metricas(cls, hoy: date | None = None) -> Dict[str, Any]:
        """
        Retorna las métricas y colecciones consolidadas para el Dashboard.

        Args:
            hoy: Fecha de referencia (por defecto timezone.localdate() para respetar
                 el huso horario de Argentina).
        """
        if hoy is None:
            hoy = timezone.localdate()

        # ── RF 2.1: Turnos del día ──
        turnos_hoy_qs = (
            Turno.objects.filter(fecha=hoy)
            .select_related("servicio", "profesional", "cliente")
            .order_by("hora")
        )
        turnos_hoy = list(turnos_hoy_qs)
        turnos_hoy_activos = [t for t in turnos_hoy if t.estado != Turno.Estado.CANCELADO]
        turnos_hoy_completados = [t for t in turnos_hoy if t.estado == Turno.Estado.COMPLETADO]
        turnos_hoy_pendientes = [
            t for t in turnos_hoy if t.estado in {Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO}
        ]

        # ── RF 2.2: Resumen de ingresos ──
        # Inicio de la semana (Lunes)
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        # Inicio del mes
        inicio_mes = hoy.replace(day=1)

        cobros_validos = Cobro.objects.filter(anulado=False)

        ingresos_dia = (
            cobros_validos.filter(fecha=hoy).aggregate(total=Sum("total"))["total"]
            or Decimal("0.00")
        )
        ingresos_semana = (
            cobros_validos.filter(fecha__gte=inicio_semana, fecha__lte=hoy).aggregate(
                total=Sum("total")
            )["total"]
            or Decimal("0.00")
        )
        ingresos_mes = (
            cobros_validos.filter(
                fecha__year=hoy.year, fecha__month=hoy.month, fecha__lte=hoy
            ).aggregate(total=Sum("total"))["total"]
            or Decimal("0.00")
        )
        cobros_count_dia = cobros_validos.filter(fecha=hoy).count()

        # ── RF 2.3: Alertas de stock ──
        productos_bajo_stock_qs = InventarioService.obtener_productos_bajo_stock()
        productos_bajo_stock = list(productos_bajo_stock_qs[:10])
        total_alertas_stock = productos_bajo_stock_qs.count()
        sin_stock_count = sum(1 for p in productos_bajo_stock if p.stock_actual <= 0)

        # ── RF 2.4: Próximos turnos ──
        proximos_turnos_qs = (
            Turno.objects.filter(fecha__gt=hoy)
            .exclude(estado=Turno.Estado.CANCELADO)
            .select_related("servicio", "profesional", "cliente")
            .order_by("fecha", "hora")
        )
        proximos_turnos = list(proximos_turnos_qs[:6])
        proximos_turnos_total = proximos_turnos_qs.count()

        # ── RF 2.5: Cumpleaños del mes ──
        cumpleaneras_mes_qs = (
            Cliente.objects.filter(activo=True, fecha_nacimiento__month=hoy.month)
            .order_by("fecha_nacimiento__day", "nombre")
        )
        cumpleaneras_mes = list(cumpleaneras_mes_qs)
        cumpleaneras_hoy = [
            c for c in cumpleaneras_mes if c.fecha_nacimiento and c.fecha_nacimiento.day == hoy.day
        ]

        return {
            "hoy": hoy,
            "inicio_semana": inicio_semana,
            "inicio_mes": inicio_mes,
            # RF 2.1
            "turnos_hoy": turnos_hoy,
            "turnos_hoy_total": len(turnos_hoy),
            "turnos_hoy_activos_count": len(turnos_hoy_activos),
            "turnos_hoy_completados_count": len(turnos_hoy_completados),
            "turnos_hoy_pendientes_count": len(turnos_hoy_pendientes),
            # RF 2.2
            "ingresos_dia": ingresos_dia,
            "ingresos_semana": ingresos_semana,
            "ingresos_mes": ingresos_mes,
            "cobros_count_dia": cobros_count_dia,
            # RF 2.3
            "productos_bajo_stock": productos_bajo_stock,
            "total_alertas_stock": total_alertas_stock,
            "sin_stock_count": sin_stock_count,
            # RF 2.4
            "proximos_turnos": proximos_turnos,
            "proximos_turnos_total": proximos_turnos_total,
            # RF 2.5
            "cumpleaneras_mes": cumpleaneras_mes,
            "cumpleaneras_hoy": cumpleaneras_hoy,
            "total_cumpleaneras_mes": len(cumpleaneras_mes),
        }
