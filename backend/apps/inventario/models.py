"""
Peluquería Lorena — Modelos del módulo de Inventario.

Implementa la gestión de productos e insumos de la peluquería y el
registro histórico/auditoría de movimientos de stock (consumo en servicios,
ventas directas, reposiciones y ajustes manuales) bajo POO.
"""
from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Producto(models.Model):
    """
    Modelo de dominio para los productos e insumos del salón de belleza.

    Permite controlar el inventario disponible, precios y umbrales de alerta
    de stock mínimo para reposición oportuna.
    """

    nombre = models.CharField(
        "nombre",
        max_length=200,
    )
    descripcion = models.TextField(
        "descripción",
        blank=True,
        null=True,
    )
    precio = models.DecimalField(
        "precio",
        max_digits=10,
        decimal_places=2,
    )
    stock_actual = models.IntegerField(
        "stock actual",
        default=0,
        db_column="stockActual",
    )
    stock_minimo = models.IntegerField(
        "stock mínimo",
        default=0,
        db_column="stockMinimo",
    )
    class UnidadMedida(models.TextChoices):
        UNIDAD = "UNIDAD", "Unidades (u.)"
        LITRO = "LITRO", "Litros (L)"
        MILILITRO = "ML", "Mililitros (ml)"
        KILOGRAMO = "KG", "Kilogramos (kg)"
        GRAMO = "G", "Gramos (g)"

    unidad_medida = models.CharField(
        "unidad de medida",
        max_length=10,
        choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
        help_text="Indica si el stock se cuenta en unidades o en cantidad (litros, ml, kg, g).",
    )
    activo = models.BooleanField(
        "activo",
        default=True,
        help_text="Indica si el producto está disponible (baja lógica).",
    )
    creado_en = models.DateTimeField(
        "creado en",
        default=timezone.now,
    )
    actualizado_en = models.DateTimeField(
        "actualizado en",
        auto_now=True,
    )

    class Meta:
        db_table = "inventario_producto"
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return f"{self.nombre} (Stock: {self.stock_actual} {self.unidad_abreviatura})"

    @property
    def unidad_abreviatura(self) -> str:
        """Abreviatura corta para mostrar junto al stock (u., L, ml, kg, g)."""
        return {
            "UNIDAD": "u.",
            "LITRO": "L",
            "ML": "ml",
            "KG": "kg",
            "G": "g",
        }.get(self.unidad_medida, "u.")

    # ── Compatibilidad con nombres anteriores (camelCase) ──

    @property
    def stockActual(self) -> int:
        """Alias de compatibilidad para stock_actual."""
        return self.stock_actual

    @stockActual.setter
    def stockActual(self, value: int) -> None:
        self.stock_actual = value

    @property
    def stockMinimo(self) -> int:
        """Alias de compatibilidad para stock_minimo."""
        return self.stock_minimo

    @stockMinimo.setter
    def stockMinimo(self, value: int) -> None:
        self.stock_minimo = value

    # ── Métodos de Dominio POO ──

    def descontar_stock(self, cantidad: int) -> bool:
        """
        Disminuye el stock actual del producto si hay suficiente existencia.

        Args:
            cantidad: Cantidad positiva de unidades a descontar.

        Returns:
            True si el descuento fue exitoso, False si no hay stock suficiente.
        """
        if cantidad <= 0:
            raise ValueError("La cantidad a descontar debe ser mayor a cero.")

        if self.stock_actual >= cantidad:
            self.stock_actual -= cantidad
            self.save(update_fields=["stock_actual", "actualizado_en"])
            return True
        return False

    def descontarStock(self, cantidad: int) -> bool:
        """Alias de compatibilidad para descontar_stock."""
        return self.descontar_stock(cantidad)

    def reponer_stock(self, cantidad: int) -> None:
        """
        Aumenta el stock actual del producto tras una compra o reposición.

        Args:
            cantidad: Cantidad positiva de unidades a ingresar.
        """
        if cantidad <= 0:
            raise ValueError("La cantidad a reponer debe ser mayor a cero.")

        self.stock_actual += cantidad
        self.save(update_fields=["stock_actual", "actualizado_en"])

    def verificar_stock_minimo(self) -> bool:
        """
        Verifica si el stock actual alcanzó o está por debajo del stock mínimo.

        Returns:
            True si el producto está en nivel crítico (<= stock_minimo).
        """
        return self.stock_actual <= self.stock_minimo

    def verificarStockMinimo(self) -> bool:
        """Alias de compatibilidad para verificar_stock_minimo."""
        return self.verificar_stock_minimo()

    @property
    def esta_bajo_stock(self) -> bool:
        """Propiedad que indica si el producto requiere reposición."""
        return self.verificar_stock_minimo()

    def dar_de_baja(self) -> None:
        """Realiza una baja lógica desactivando el producto."""
        self.activo = False
        self.save(update_fields=["activo", "actualizado_en"])

    def reactivar(self) -> None:
        """Reactiva un producto previamente dado de baja."""
        self.activo = True
        self.save(update_fields=["activo", "actualizado_en"])


class MovimientoStock(models.Model):
    """
    Registro histórico de auditoría para cada movimiento y consumo de stock.

    Permite la trazabilidad total del consumo de insumos en servicios (RF 7.2),
    ventas directas, reposiciones y ajustes manuales.
    """

    class TipoMovimiento(models.TextChoices):
        ALTA_PRODUCTO = "ALTA_PRODUCTO", "Producto añadido"
        BAJA_PRODUCTO = "BAJA_PRODUCTO", "Producto eliminado"
        REPOSICION = "REPOSICION", "Reposición de Stock"
        DESCUENTO = "DESCUENTO", "Descuento de Stock"
        CAMBIO_NOMBRE = "CAMBIO_NOMBRE", "Cambio de nombre"
        CAMBIO_DESCRIPCION = "CAMBIO_DESCRIPCION", "Cambio de descripción"
        CAMBIO_PRECIO = "CAMBIO_PRECIO", "Cambio de precio"
        CAMBIO_STOCK_MINIMO = "CAMBIO_STOCK_MINIMO", "Cambio de stock mínimo"

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="movimientos",
        verbose_name="producto",
    )
    tipo_movimiento = models.CharField(
        "tipo de movimiento",
        max_length=30,
        choices=TipoMovimiento.choices,
        default=TipoMovimiento.DESCUENTO,
    )
    cantidad = models.PositiveIntegerField(
        "cantidad",
    )
    stock_previo = models.IntegerField(
        "stock previo",
    )
    stock_posterior = models.IntegerField(
        "stock posterior",
    )
    motivo = models.TextField(
        "motivo o detalle del servicio",
        blank=True,
        null=True,
        help_text="Descripción del servicio realizado, motivo del ajuste o referencia.",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="movimientos_stock",
        verbose_name="usuario que registró",
    )
    fecha = models.DateTimeField(
        "fecha del movimiento",
        default=timezone.now,
    )

    class Meta:
        db_table = "inventario_movimiento_stock"
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"
        ordering = ["-fecha"]

    def __str__(self) -> str:
        return f"{self.get_tipo_movimiento_display()} — {self.producto.nombre} ({self.cantidad} u.)"
