"""
Peluquería Lorena — Modelos del módulo de Caja y Ventas.

Registra los cobros de servicios y las ventas de productos, con medio de pago,
descuento automático del 10% para efectivo y billeteras virtuales,
cierre de caja diario y reporte de ingresos por medio de pago.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Cobro(models.Model):
    """
    Registro de un cobro en caja: servicio prestado o producto vendido.

    El total se calcula como subtotal menos descuento automático
    (10% si el medio de pago es efectivo, Mercado Pago o Ualá).
    """

    class Tipo(models.TextChoices):
        SERVICIO = "SERVICIO", "Servicio"
        PRODUCTO = "PRODUCTO", "Producto"

    class MedioPago(models.TextChoices):
        EFECTIVO = "EFECTIVO", "Efectivo"
        MERCADO_PAGO = "MERCADO_PAGO", "Billetera Virtual — Mercado Pago"
        UALA = "UALA", "Billetera Virtual — Ualá"
        TARJETA_DEBITO = "TARJETA_DEBITO", "Tarjeta de Débito"
        TARJETA_CREDITO = "TARJETA_CREDITO", "Tarjeta de Crédito"

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cobros",
        verbose_name="clienta vinculada",
    )
    cliente_nombre = models.CharField("nombre de la clienta", max_length=200)
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cobros_registrados",
        verbose_name="profesional que cobra",
    )
    tipo = models.CharField(
        "tipo de cobro",
        max_length=10,
        choices=Tipo.choices,
        default=Tipo.SERVICIO,
        db_index=True,
    )
    servicio = models.ForeignKey(
        "servicios.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cobros",
        verbose_name="servicio cobrado",
    )
    servicio_realizado = models.ForeignKey(
        "servicios.ServicioRealizado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cobros",
        verbose_name="atención vinculada",
    )
    producto = models.ForeignKey(
        "inventario.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ventas",
        verbose_name="producto vendido",
    )
    cantidad = models.PositiveIntegerField("cantidad", default=1)
    precio_unitario = models.DecimalField("precio unitario", max_digits=10, decimal_places=2)
    subtotal = models.DecimalField("subtotal", max_digits=10, decimal_places=2)
    porcentaje_descuento = models.DecimalField(
        "porcentaje de descuento",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    monto_descuento = models.DecimalField(
        "monto de descuento",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total = models.DecimalField("total cobrado", max_digits=10, decimal_places=2, db_index=True)
    medio_pago = models.CharField(
        "medio de pago",
        max_length=20,
        choices=MedioPago.choices,
        default=MedioPago.EFECTIVO,
        db_index=True,
    )
    fecha = models.DateField("fecha de cobro", default=timezone.localdate, db_index=True)
    observaciones = models.TextField("observaciones", blank=True)
    cierre = models.ForeignKey(
        "pagos.CierreCaja",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cobros",
        verbose_name="cierre de caja",
    )
    anulado = models.BooleanField("anulado", default=False, db_index=True)
    fecha_creacion = models.DateTimeField("fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "cobro"
        verbose_name_plural = "cobros"
        ordering = ["-fecha", "-fecha_creacion"]

    def __str__(self) -> str:
        estado = "ANULADO" if self.anulado else self.get_medio_pago_display()
        return f"Cobro {self.get_tipo_display()} a {self.cliente_nombre} — ${self.total:,.2f} ({estado})"

    # ── Aliases camelCase ──

    @property
    def clienteNombre(self) -> str:
        return self.cliente_nombre

    @property
    def precioUnitario(self) -> Decimal:
        return self.precio_unitario

    @property
    def porcentajeDescuento(self) -> Decimal:
        return self.porcentaje_descuento

    @property
    def montoDescuento(self) -> Decimal:
        return self.monto_descuento

    @property
    def medioPago(self) -> str:
        return self.medio_pago

    @property
    def fechaCreacion(self):
        return self.fecha_creacion


class CierreCaja(models.Model):
    """
    Cierre de caja diario: consolida los cobros del día
    discriminados por medio de pago.
    """

    fecha = models.DateField("fecha del cierre", unique=True, db_index=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cierres_caja",
        verbose_name="responsable del cierre",
    )
    cantidad_cobros = models.PositiveIntegerField("cantidad de cobros", default=0)
    total_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_mercado_pago = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_uala = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_tarjeta_debito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_tarjeta_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_descuentos = models.DecimalField(
        "total otorgado en descuentos", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_general = models.DecimalField(
        "total general del día", max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    observaciones = models.TextField("observaciones del cierre", blank=True)
    fecha_creacion = models.DateTimeField("fecha y hora del cierre", auto_now_add=True)

    class Meta:
        verbose_name = "cierre de caja"
        verbose_name_plural = "cierres de caja"
        ordering = ["-fecha"]

    def __str__(self) -> str:
        return f"Cierre {self.fecha.strftime('%d/%m/%Y')} — ${self.total_general:,.2f} ({self.cantidad_cobros} cobros)"

    # ── Aliases camelCase ──

    @property
    def cantidadCobros(self) -> int:
        return self.cantidad_cobros

    @property
    def totalGeneral(self) -> Decimal:
        return self.total_general

    @property
    def totalDescuentos(self) -> Decimal:
        return self.total_descuentos

    def totales_por_medio(self) -> dict[str, Decimal]:
        """Retorna el consolidado discriminado por medio de pago."""
        return {
            Cobro.MedioPago.EFECTIVO: self.total_efectivo,
            Cobro.MedioPago.MERCADO_PAGO: self.total_mercado_pago,
            Cobro.MedioPago.UALA: self.total_uala,
            Cobro.MedioPago.TARJETA_DEBITO: self.total_tarjeta_debito,
            Cobro.MedioPago.TARJETA_CREDITO: self.total_tarjeta_credito,
        }

    def totalesPorMedio(self) -> dict[str, Decimal]:
        return self.totales_por_medio()
