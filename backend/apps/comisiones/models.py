"""
Peluquería Lorena — Modelos del módulo de Comisiones y Liquidación (RF8).

Define las entidades de negocio para:
1. ConfiguracionComision: Porcentajes de comisión parametrizables por categoría de servicio (RF 8.1).
2. Liquidacion: Registro formal de liquidaciones periódicas por peluquera (RF 8.4).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models


class ConfiguracionComision(models.Model):
    """
    Parametrización del porcentaje de comisión por categoría de servicio (RF 8.1).
    Valores relevados por defecto:
    - Cortes: 50%
    - Trabajos técnicos (Color, Mechas, Tratamientos): 25%
    - Otros servicios: 25%
    """

    class CategoriaServicio(models.TextChoices):
        CORTES = "CORTES", "Cortes"
        COLOR = "COLOR", "Color"
        MECHAS = "MECHAS", "Mechas"
        TRATAMIENTOS = "TRATAMIENTOS", "Tratamientos Capilares"
        OTROS = "OTROS", "Otros Servicios"

    categoria = models.CharField(
        "categoría de servicio",
        max_length=30,
        choices=CategoriaServicio.choices,
        unique=True,
    )
    porcentaje = models.DecimalField(
        "porcentaje de comisión (%)",
        max_digits=5,
        decimal_places=2,
        help_text="Porcentaje sobre el presupuesto acordado a liquidar a la profesional.",
    )
    descripcion = models.CharField(
        "descripción / notas",
        max_length=200,
        blank=True,
    )
    activo = models.BooleanField("activo", default=True)
    fecha_actualizacion = models.DateTimeField("última actualización", auto_now=True)

    class Meta:
        verbose_name = "configuración de comisión"
        verbose_name_plural = "configuraciones de comisiones"
        ordering = ["categoria"]

    def __str__(self) -> str:
        return f"{self.get_categoria_display()}: {self.porcentaje}%"

    # ── Aliases camelCase ──

    @property
    def fechaActualizacion(self):
        return self.fecha_actualizacion


class Liquidacion(models.Model):
    """
    Asiento formal de la liquidación de comisiones a una profesional por período (RF 8.4).
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de Pago"
        PAGADA = "PAGADA", "Liquidada y Pagada"

    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="liquidaciones",
        verbose_name="peluquera / profesional",
    )
    fecha_desde = models.DateField("fecha desde", db_index=True)
    fecha_hasta = models.DateField("fecha hasta", db_index=True)
    total_servicios = models.PositiveIntegerField("cantidad de servicios", default=0)
    total_bruto = models.DecimalField(
        "total recaudado bruto",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_comision = models.DecimalField(
        "total comisión liquidada",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    estado = models.CharField(
        "estado",
        max_length=20,
        choices=Estado.choices,
        default=Estado.PAGADA,
    )
    fecha_registro = models.DateTimeField("fecha de liquidación", auto_now_add=True)
    liquidado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liquidaciones_emitidas",
        verbose_name="liquidado por (administradora)",
    )
    observaciones = models.TextField("observaciones", blank=True)

    class Meta:
        verbose_name = "liquidación de comisiones"
        verbose_name_plural = "liquidaciones de comisiones"
        ordering = ["-fecha_registro"]

    def __str__(self) -> str:
        return f"Liquidación {self.profesional.nombre} ({self.fecha_desde.strftime('%d/%m/%Y')} - {self.fecha_hasta.strftime('%d/%m/%Y')}): ${self.total_comision:,.2f}"

    # ── Aliases camelCase ──

    @property
    def fechaDesde(self):
        return self.fecha_desde

    @property
    def fechaHasta(self):
        return self.fecha_hasta

    @property
    def totalBruto(self) -> Decimal:
        return self.total_bruto

    @property
    def totalComision(self) -> Decimal:
        return self.total_comision

    @property
    def liquidadoPor(self) -> Any:
        return self.liquidado_por
