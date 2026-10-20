"""
Peluquería Lorena — Servicio del Dashboard (RF 2).

Centraliza la lógica de negocio y consultas de los requerimientos funcionales:
- RF 2.1: Turnos del día
- RF 2.2: Resumen de ingresos (día, semana, mes y últimos 7 días)
- RF 2.3: Alertas de stock mínimo
- RF 2.4: Próximos turnos agendados
- RF 2.5: Cumpleaños y beneficios de fidelización (RF10)

La vista del dashboard solo consume este servicio para mantenerse delgada.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

from django.db.models import Count, Sum
from django.utils import timezone

from apps.bot_asistente.models import ConversacionBot
from apps.clientes.models import Cliente
from apps.fidelizacion.models import BeneficioOtorgado
from apps.inventario.services import InventarioService
from apps.pagos.facturacion import FacturaService
from apps.pagos.models import Cobro
from apps.turnos.models import Turno


DIAS_SEMANA_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _money(valor: Decimal | None) -> Decimal:
    """Normaliza un importe a dos decimales para mostrarlo de forma uniforme."""
    return (valor or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

#: Paleta alineada al tema oscuro/dorado del salón (usada por Chart.js).
COLORES_MEDIOS_PAGO = {
    Cobro.MedioPago.EFECTIVO: "#e5c158",
    Cobro.MedioPago.MERCADO_PAGO: "#6ea8fe",
    Cobro.MedioPago.UALA: "#a78bfa",
    Cobro.MedioPago.TARJETA_DEBITO: "#5fd0a5",
    Cobro.MedioPago.TARJETA_CREDITO: "#ee8f74",
}


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
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        inicio_mes = hoy.replace(day=1)
        ayer = hoy - timedelta(days=1)

        cobros_validos = Cobro.objects.filter(anulado=False)

        ingresos_dia = (
            cobros_validos.filter(fecha=hoy).aggregate(total=Sum("total"))["total"]
            or Decimal("0.00")
        )
        ingresos_ayer = (
            cobros_validos.filter(fecha=ayer).aggregate(total=Sum("total"))["total"]
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
        ingresos_dia = _money(ingresos_dia)
        ingresos_ayer = _money(ingresos_ayer)
        ingresos_semana = _money(ingresos_semana)
        ingresos_mes = _money(ingresos_mes)
        cobros_count_dia = cobros_validos.filter(fecha=hoy).count()

        # Cantidad de ventas del día (agrupa los ítems de un mismo carrito).
        ventas_count_dia = (
            cobros_validos.filter(fecha=hoy)
            .values(
                "cliente_nombre",
                "profesional_id",
                "medio_pago",
                "porcentaje_descuento",
                "observaciones",
                "cliente_id",
            )
            .annotate(cantidad=Count("id"))
            .count()
        )

        ticket_promedio_dia = (
            (ingresos_dia / cobros_count_dia).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if cobros_count_dia
            else Decimal("0.00")
        )

        variacion_dia_pct = None
        if ingresos_ayer > 0:
            variacion_dia_pct = (
                (ingresos_dia - ingresos_ayer) / ingresos_ayer * Decimal("100")
            ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

        # ── Ingresos de los últimos 7 días (gráfico de tendencia) ──
        inicio_7d = hoy - timedelta(days=6)
        totales_por_dia = {
            fila["fecha"]: fila["total"] or Decimal("0.00")
            for fila in cobros_validos.filter(fecha__gte=inicio_7d, fecha__lte=hoy)
            .values("fecha")
            .annotate(total=Sum("total"))
        }
        ingresos_7_dias = []
        for desplazamiento in range(6, -1, -1):
            dia = hoy - timedelta(days=desplazamiento)
            ingresos_7_dias.append(
                {
                    "fecha": dia.isoformat(),
                    "etiqueta": f"{DIAS_SEMANA_CORTOS[dia.weekday()]} {dia.day}",
                    "total": float(totales_por_dia.get(dia, Decimal("0.00"))),
                }
            )
        ingresos_7d_total = sum(
            (totales_por_dia.get(hoy - timedelta(days=i), Decimal("0.00")) for i in range(7)),
            Decimal("0.00"),
        )
        ingresos_7d_promedio = (ingresos_7d_total / 7).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # ── Distribución por medio de pago del mes en curso ──
        filas_medios = list(
            cobros_validos.filter(
                fecha__year=hoy.year, fecha__month=hoy.month, fecha__lte=hoy
            )
            .values("medio_pago")
            .annotate(total=Sum("total"), cantidad=Count("id"))
            .order_by("-total")
        )
        total_medios = sum((fila["total"] or Decimal("0.00") for fila in filas_medios), Decimal("0.00"))
        etiquetas_medios = dict(Cobro.MedioPago.choices)
        distribucion_medios = [
            {
                "codigo": fila["medio_pago"],
                "etiqueta": etiquetas_medios.get(fila["medio_pago"], fila["medio_pago"]),
                "total": float(fila["total"] or Decimal("0.00")),
                "cantidad": fila["cantidad"],
                "porcentaje": float(
                    ((fila["total"] or Decimal("0.00")) / total_medios * Decimal("100")).quantize(
                        Decimal("0.1"), rounding=ROUND_HALF_UP
                    )
                )
                if total_medios
                else 0.0,
                "color": COLORES_MEDIOS_PAGO.get(fila["medio_pago"], "#8b93a1"),
            }
            for fila in filas_medios
        ]

        # ── Últimos movimientos de caja (ventas agrupadas, no ítems sueltos) ──
        ultimos_cobros = list(
            cobros_validos.select_related("servicio", "producto", "profesional", "cliente")
            .order_by("-fecha", "-fecha_creacion")[:20]
        )
        ultimos_movimientos = FacturaService.agrupar_ventas(ultimos_cobros)[:5]

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

        # ── RF 2.5: Cumpleaños del mes y de la próxima semana ──
        cumpleaneras_mes_qs = (
            Cliente.objects.filter(activo=True, fecha_nacimiento__month=hoy.month)
            .order_by("fecha_nacimiento__day", "nombre")
        )
        cumpleaneras_mes = list(cumpleaneras_mes_qs)
        cumpleaneras_hoy = [
            c for c in cumpleaneras_mes if c.fecha_nacimiento and c.fecha_nacimiento.day == hoy.day
        ]

        fin_semana = hoy + timedelta(days=6)
        meses_semana = sorted({hoy.month, fin_semana.month})
        cumpleaneras_semana = []
        for cliente in Cliente.objects.filter(
            activo=True, fecha_nacimiento__month__in=meses_semana
        ):
            proximo = cliente.proximo_cumpleanos(hoy)
            if proximo is None:
                continue
            dias = (proximo - hoy).days
            if 0 <= dias <= 6:
                cumpleaneras_semana.append((dias, cliente))
        cumpleaneras_semana.sort(key=lambda par: (par[0], par[1].nombre))
        cumpleaneras_semana = [cliente for _, cliente in cumpleaneras_semana]

        # ── RF 10: Beneficios disponibles para canjear ──
        beneficios_qs = BeneficioOtorgado.objects.filter(
            estado=BeneficioOtorgado.Estado.DISPONIBLE,
            fecha_vencimiento__gte=hoy,
        ).select_related("cliente", "regla")
        total_beneficios_disponibles = beneficios_qs.count()
        beneficios_disponibles = list(beneficios_qs.order_by("fecha_vencimiento")[:4])
        beneficios_por_vencer_count = beneficios_qs.filter(
            fecha_vencimiento__lte=hoy + timedelta(days=7)
        ).count()

        # ── Atención Requerida Bot WhatsApp ──
        conversaciones_derivadas_qs = ConversacionBot.objects.filter(requiere_humano=True).order_by("-ultimo_mensaje_at")
        conversaciones_derivadas_count = conversaciones_derivadas_qs.count()
        conversaciones_derivadas = list(conversaciones_derivadas_qs[:5])

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
            "ingresos_ayer": ingresos_ayer,
            "ingresos_semana": ingresos_semana,
            "ingresos_mes": ingresos_mes,
            "cobros_count_dia": cobros_count_dia,
            "ventas_count_dia": ventas_count_dia,
            "ticket_promedio_dia": ticket_promedio_dia,
            "variacion_dia_pct": variacion_dia_pct,
            "ingresos_7_dias": ingresos_7_dias,
            "ingresos_7d_total": ingresos_7d_total,
            "ingresos_7d_promedio": ingresos_7d_promedio,
            "distribucion_medios": distribucion_medios,
            "total_medios_periodo": total_medios,
            "ultimos_movimientos": ultimos_movimientos,
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
            "cumpleaneras_semana": cumpleaneras_semana,
            "total_cumpleaneras_semana": len(cumpleaneras_semana),
            # RF 10
            "beneficios_disponibles": beneficios_disponibles,
            "total_beneficios_disponibles": total_beneficios_disponibles,
            "beneficios_por_vencer_count": beneficios_por_vencer_count,
            # Bot WhatsApp (Derivaciones a Lorena)
            "conversaciones_derivadas": conversaciones_derivadas,
            "conversaciones_derivadas_count": conversaciones_derivadas_count,
        }
