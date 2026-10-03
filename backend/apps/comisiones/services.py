"""
Peluquería Lorena — Capa de servicios del módulo de Comisiones y Liquidación (RF8).

Centraliza la lógica de negocio para:
- Parametrización y defaults de comisiones por categoría (RF 8.1).
- Cálculo automático de comisiones sobre presupuesto pactado (RF 8.2).
- Registro simplificado de atenciones por peluquera (RF 8.3).
- Generación y cierre de reportes de liquidación por profesional y período (RF 8.4).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Count, QuerySet, Sum
from django.utils import timezone

from apps.servicios.models import Servicio, ServicioRealizado
from apps.usuarios.models import Usuario
from .models import ConfiguracionComision, Liquidacion


def _redondear_moneda(valor: Decimal) -> Decimal:
    """Redondea un valor Decimal a dos decimales con criterio financiero."""
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ComisionService:
    """
    Servicio de dominio para el cálculo de comisiones, registro de trabajos
    y reportes consolidados de liquidación.
    """

    # Valores relevados oficiales del salón de Lorena
    DEFAULTS_RELEVADOS: Dict[str, Dict[str, Any]] = {
        ConfiguracionComision.CategoriaServicio.CORTES: {
            "porcentaje": Decimal("50.00"),
            "descripcion": "Cortes damas, caballeros y niños (50% comisión relevada)",
        },
        ConfiguracionComision.CategoriaServicio.COLOR: {
            "porcentaje": Decimal("25.00"),
            "descripcion": "Trabajo técnico - Coloración capilar (25% comisión relevada)",
        },
        ConfiguracionComision.CategoriaServicio.MECHAS: {
            "porcentaje": Decimal("25.00"),
            "descripcion": "Trabajo técnico - Decoloraciones, mechas y balayage (25% comisión relevada)",
        },
        ConfiguracionComision.CategoriaServicio.TRATAMIENTOS: {
            "porcentaje": Decimal("25.00"),
            "descripcion": "Trabajo técnico - Alisados, keratinas y nutrición (25% comisión relevada)",
        },
        ConfiguracionComision.CategoriaServicio.OTROS: {
            "porcentaje": Decimal("25.00"),
            "descripcion": "Peinados, brushing y servicios varios (25% comisión relevada)",
        },
    }

    # ── Configuración y Parametrización (RF 8.1) ──

    @classmethod
    def sembrar_configuracion_defecto(cls) -> int:
        """
        Siembra o inicializa los porcentajes de comisión por categoría según
        el relevamiento del salón si aún no han sido configurados.
        Retorna la cantidad de registros sembrados o actualizados.
        """
        creados = 0
        for cat_key, datos in cls.DEFAULTS_RELEVADOS.items():
            _, created = ConfiguracionComision.objects.get_or_create(
                categoria=cat_key,
                defaults={
                    "porcentaje": datos["porcentaje"],
                    "descripcion": datos["descripcion"],
                    "activo": True,
                },
            )
            if created:
                creados += 1
        return creados

    @classmethod
    def obtener_porcentajes_activos(cls) -> Dict[str, Decimal]:
        """
        Retorna un diccionario {categoria: porcentaje} con los porcentajes
        vigentes, aplicando fallback a los defaults relevados si faltan.
        """
        # Asegurar que existan los defaults si la tabla está vacía
        if not ConfiguracionComision.objects.exists():
            cls.sembrar_configuracion_defecto()

        configs = {
            c.categoria: c.porcentaje
            for c in ConfiguracionComision.objects.filter(activo=True)
        }
        for cat_key, datos in cls.DEFAULTS_RELEVADOS.items():
            if cat_key not in configs:
                configs[cat_key] = datos["porcentaje"]
        return configs

    @classmethod
    def obtener_porcentaje_categoria(cls, categoria: str) -> Decimal:
        """Retorna el porcentaje de comisión para una categoría específica."""
        porcentajes = cls.obtener_porcentajes_activos()
        return porcentajes.get(categoria, Decimal("25.00"))

    # ── Cálculo Automático de Comisión (RF 8.2) ──

    @classmethod
    def calcular_comision(
        cls,
        servicio: Servicio,
        precio_acordado: Decimal,
        porcentaje_manual: Optional[Decimal] = None,
    ) -> Tuple[Decimal, Decimal]:
        """
        Calcula el porcentaje de comisión y el monto exacto en pesos ($)
        sobre el presupuesto pactado. Retorna (porcentaje, monto_comision).
        """
        porcentaje = (
            porcentaje_manual
            if porcentaje_manual is not None
            else cls.obtener_porcentaje_categoria(servicio.categoria)
        )
        monto = (Decimal(str(precio_acordado)) * porcentaje) / Decimal("100")
        return porcentaje, _redondear_moneda(monto)

    # ── Registro Simple de Trabajos por Peluquera (RF 8.3) ──

    @classmethod
    @transaction.atomic
    def registrar_trabajo_peluquera(
        cls,
        servicio: Servicio,
        profesional: Usuario,
        cliente_nombre: str,
        precio_acordado: Decimal,
        cliente_telefono: str = "",
        cliente=None,
        fecha: Optional[date] = None,
        hora=None,
        duracion_minutos: Optional[int] = None,
        notas: str = "",
        consentimiento=None,
    ) -> ServicioRealizado:
        """
        Registra el trabajo realizado por una peluquera con cálculo automático
        de su comisión respectiva (RF 8.2 y RF 8.3).
        """
        fecha_atencion = fecha or timezone.localdate()
        hora_atencion = hora or timezone.localtime().time()
        duracion = (
            duracion_minutos
            if duracion_minutos is not None
            else servicio.duracion_estimada_minutos
        )

        porcentaje, monto = cls.calcular_comision(servicio, precio_acordado)

        trabajo = ServicioRealizado.objects.create(
            servicio=servicio,
            profesional=profesional,
            cliente=cliente,
            cliente_nombre=cliente_nombre.strip(),
            cliente_telefono=cliente_telefono.strip(),
            fecha=fecha_atencion,
            hora=hora_atencion,
            precio_acordado=precio_acordado,
            duracion_minutos=duracion,
            porcentaje_comision=porcentaje,
            monto_comision=monto,
            estado=ServicioRealizado.Estado.COMPLETADO,
            notas=notas.strip(),
            consentimiento=consentimiento,
        )

        # Si existe un turno de agenda pendiente o confirmado para esta atención hoy, vincularlo y completarlo
        try:
            from apps.turnos.models import Turno
            from apps.turnos.services import TurnoService

            turno_match = None
            if cliente:
                turno_match = Turno.objects.filter(
                    fecha=fecha_atencion,
                    cliente=cliente,
                    servicio=servicio,
                    estado__in=[Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO],
                ).first()
            if not turno_match and cliente_nombre:
                turno_match = Turno.objects.filter(
                    fecha=fecha_atencion,
                    cliente_nombre__iexact=cliente_nombre.strip(),
                    servicio=servicio,
                    estado__in=[Turno.Estado.PENDIENTE, Turno.Estado.CONFIRMADO],
                ).first()

            if turno_match:
                TurnoService.completar_turno(turno_match, trabajo)
        except Exception:
            pass

        return trabajo

    # ── Reporte de Liquidación (RF 8.4) ──

    @classmethod
    def obtener_resumen_liquidacion(
        cls,
        profesional_id: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Genera el informe consolidado de comisiones por peluquera y por período,
        con totales brutos recaudados, comisiones a liquidar y desglose fila por fila.
        """
        qs = ServicioRealizado.objects.filter(
            estado=ServicioRealizado.Estado.COMPLETADO
        ).select_related("servicio", "profesional", "cliente")

        if profesional_id:
            qs = qs.filter(profesional_id=profesional_id)

        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)

        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)

        qs = qs.order_by("-fecha", "-hora")

        # Cálculo de totales agregados
        total_servicios = qs.count()
        total_bruto = sum((s.precio_acordado for s in qs), Decimal("0.00"))
        total_comisiones = sum((s.monto_comision or Decimal("0.00") for s in qs), Decimal("0.00"))

        # Agrupación por profesional
        profesionales_map: Dict[int, Dict[str, Any]] = {}
        for s in qs:
            pid = s.profesional_id
            if pid not in profesionales_map:
                profesionales_map[pid] = {
                    "profesional": s.profesional,
                    "cantidad": 0,
                    "bruto": Decimal("0.00"),
                    "comision": Decimal("0.00"),
                    "pendiente_cantidad": 0,
                    "pendiente_bruto": Decimal("0.00"),
                    "pendiente_comision": Decimal("0.00"),
                }
            profesionales_map[pid]["cantidad"] += 1
            profesionales_map[pid]["bruto"] += s.precio_acordado
            profesionales_map[pid]["comision"] += (s.monto_comision or Decimal("0.00"))
            # Lo que todavía no entró en ninguna liquidación (lo que se asentaría ahora).
            if s.liquidacion_id is None:
                profesionales_map[pid]["pendiente_cantidad"] += 1
                profesionales_map[pid]["pendiente_bruto"] += s.precio_acordado
                profesionales_map[pid]["pendiente_comision"] += (s.monto_comision or Decimal("0.00"))

        por_profesional = sorted(
            profesionales_map.values(),
            key=lambda x: x["comision"],
            reverse=True,
        )

        # Agrupación por categoría de servicio
        categorias_map: Dict[str, Dict[str, Any]] = {}
        for s in qs:
            cat = s.servicio.categoria
            cat_label = s.servicio.get_categoria_display()
            if cat not in categorias_map:
                categorias_map[cat] = {
                    "categoria": cat,
                    "categoria_nombre": cat_label,
                    "cantidad": 0,
                    "bruto": Decimal("0.00"),
                    "comision": Decimal("0.00"),
                }
            categorias_map[cat]["cantidad"] += 1
            categorias_map[cat]["bruto"] += s.precio_acordado
            categorias_map[cat]["comision"] += (s.monto_comision or Decimal("0.00"))

        por_categoria = sorted(
            categorias_map.values(),
            key=lambda x: x["cantidad"],
            reverse=True,
        )

        return {
            "servicios": qs,
            "total_servicios": total_servicios,
            "total_bruto": total_bruto,
            "total_comisiones": total_comisiones,
            "por_profesional": por_profesional,
            "por_categoria": por_categoria,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "profesional_id": profesional_id,
        }

    @classmethod
    @transaction.atomic
    def cerrar_liquidacion_periodo(
        cls,
        profesional: Usuario,
        fecha_desde: date,
        fecha_hasta: date,
        liquidado_por: Usuario,
        observaciones: str = "",
    ) -> Liquidacion:
        """
        Asienta un comprobante de liquidación cerrada para una profesional
        y asocia los servicios efectuados en ese período.

        Solo computa las atenciones que todavía no fueron liquidadas, para no
        volver a pagar las incluidas en una liquidación anterior.

        Raises:
            ValueError: Si no hay atenciones pendientes de liquidar en el período.
        """
        resumen = cls.obtener_resumen_liquidacion(
            profesional_id=profesional.pk,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
        servicios_qs = resumen["servicios"].filter(liquidacion__isnull=True)
        totales = servicios_qs.aggregate(
            cantidad=Count("id"),
            bruto=Sum("precio_acordado"),
            comision=Sum("monto_comision"),
        )
        if not totales["cantidad"]:
            raise ValueError(
                f"No hay atenciones pendientes de liquidar para {profesional.nombre} "
                f"entre el {fecha_desde.strftime('%d/%m/%Y')} y el {fecha_hasta.strftime('%d/%m/%Y')}."
            )

        liquidacion = Liquidacion.objects.create(
            profesional=profesional,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            total_servicios=totales["cantidad"],
            total_bruto=totales["bruto"] or Decimal("0.00"),
            total_comision=totales["comision"] or Decimal("0.00"),
            estado=Liquidacion.Estado.PAGADA,
            liquidado_por=liquidado_por,
            observaciones=observaciones.strip(),
        )

        # Vincular los servicios atendidos a la liquidación
        servicios_qs.update(liquidacion=liquidacion)
        return liquidacion
