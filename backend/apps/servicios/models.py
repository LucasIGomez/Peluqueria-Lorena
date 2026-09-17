"""
Peluquería Lorena — Modelos del módulo de Servicios.

Define las entidades de negocio para:
1. Servicio: Catálogo oficial de servicios, precios base y duración estándar.
2. ConsentimientoInformado: Ficha de resguardo legal y diagnóstico técnico para
   procesos químicos delicados (decoloraciones y alisados).
3. ServicioRealizado: Control por día y horario de los servicios brindados,
   con personalización de precio y duración según cada clienta.
4. ConsumoInsumoCierre: Auditoría del descuento de insumos consolidado al cierre de la jornada.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.db import models
from django.utils import timezone


class Servicio(models.Model):
    """
    Representa un servicio del catálogo de Peluquería Lorena.
    Basado en el tarifario oficial del salón.
    """

    class Categoria(models.TextChoices):
        CORTES = "CORTES", "Cortes"
        COLOR = "COLOR", "Color"
        MECHAS = "MECHAS", "Mechas"
        TRATAMIENTOS = "TRATAMIENTOS", "Tratamientos Capilares"
        OTROS = "OTROS", "Otros Servicios"

    nombre = models.CharField("nombre del servicio", max_length=150, unique=True)
    categoria = models.CharField(
        "categoría",
        max_length=30,
        choices=Categoria.choices,
        default=Categoria.OTROS,
    )
    precio_base = models.DecimalField(
        "precio base (desde)",
        max_digits=10,
        decimal_places=2,
        help_text="Tarifa de referencia según lista oficial. Puede ajustarse por cliente.",
    )
    duracion_estimada_minutos = models.PositiveIntegerField(
        "duración estimada (minutos)",
        default=60,
        help_text="Tiempo promedio que demanda la realización del servicio.",
    )
    requiere_consentimiento = models.BooleanField(
        "requiere consentimiento informado",
        default=False,
        help_text="Marcar para decoloraciones, mechas complejas o alisados químicos.",
    )
    descripcion = models.TextField("descripción del servicio", blank=True)
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        ordering = ["categoria", "nombre"]

    def __str__(self) -> str:
        return f"{self.nombre} (${self.precio_base:,.2f})"

    # ── Aliases camelCase ──

    @property
    def precioBase(self) -> Decimal:
        return self.precio_base

    @property
    def duracionEstimadaMinutos(self) -> int:
        return self.duracion_estimada_minutos

    @property
    def requiereConsentimiento(self) -> bool:
        return self.requiere_consentimiento


class ConsentimientoInformado(models.Model):
    """
    Ficha legal de consentimiento informado para servicios químicos
    (coloración, decoloración, alisados, keratina, permanentes), con el
    texto acordado con Lorena y sus clientas.
    """

    class TipoProcedimiento(models.TextChoices):
        COLORACION = "COLORACION", "Coloración"
        DECOLORACION_MECHAS = "DECOLORACION_MECHAS", "Decoloración / Mechas"
        ALISADO = "ALISADO", "Alisado"
        KERATINA = "KERATINA", "Keratina / Tratamiento de Alisado"
        PERMANENTE = "PERMANENTE", "Permanente"
        OTRO = "OTRO", "Otro"

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consentimientos",
        verbose_name="clienta vinculada",
    )
    cliente_nombre = models.CharField("nombre y apellido", max_length=200)
    cliente_telefono = models.CharField("teléfono / WhatsApp", max_length=50, blank=True)
    cliente_dni = models.CharField("DNI", max_length=30, blank=True)

    tipo_procedimiento = models.CharField(
        "servicio solicitado",
        max_length=30,
        choices=TipoProcedimiento.choices,
        default=TipoProcedimiento.COLORACION,
    )
    otro_procedimiento_detalle = models.CharField(
        "detalle si el servicio es \"Otro\"", max_length=200, blank=True
    )

    # ── Conformidad y Resguardo Legal ──
    acepta_terminos = models.BooleanField(
        "conformidad y declaración jurada",
        default=True,
        help_text="La clienta declara haber comprendido la información y presta su conformidad para el servicio.",
    )
    firma_digital = models.TextField(
        "firma / aceptación digital",
        blank=True,
        help_text="Firma digital o texto de conformidad expresa.",
    )
    observaciones = models.TextField("observaciones del diagnóstico", blank=True)
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consentimientos_emitidos",
        verbose_name="profesional a cargo",
    )
    fecha_emision = models.DateTimeField("fecha y hora de emisión", auto_now_add=True)

    class Meta:
        verbose_name = "consentimiento informado"
        verbose_name_plural = "consentimientos informados"
        ordering = ["-fecha_emision"]

    def __str__(self) -> str:
        return f"Consentimiento: {self.cliente_nombre} — {self.get_tipo_procedimiento_display()} ({self.fecha_emision.strftime('%d/%m/%Y')})"

    # ── Aliases camelCase ──

    @property
    def clienteNombre(self) -> str:
        return self.cliente_nombre

    @property
    def clienteTelefono(self) -> str:
        return self.cliente_telefono

    @property
    def clienteDni(self) -> str:
        return self.cliente_dni

    @property
    def tipoProcedimiento(self) -> str:
        return self.tipo_procedimiento

    @property
    def aceptaTerminos(self) -> bool:
        return self.acepta_terminos

    @property
    def fechaEmision(self) -> timezone.datetime:
        return self.fecha_emision


class ServicioRealizado(models.Model):
    """
    Registro diario de cada servicio efectuado en el salón por día y horario.
    Permite personalizar el precio pactado y el tiempo según el tipo y largo de cabello.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_CURSO = "EN_CURSO", "En Curso"
        COMPLETADO = "COMPLETADO", "Completado"
        CANCELADO = "CANCELADO", "Cancelado"

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="servicios_realizados",
        verbose_name="servicio",
    )
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servicios_atendidos",
        verbose_name="clienta vinculada",
    )
    consentimiento = models.ForeignKey(
        ConsentimientoInformado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servicios_asociados",
        verbose_name="ficha de consentimiento",
    )
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trabajos_realizados",
        verbose_name="profesional asignada",
    )
    cliente_nombre = models.CharField("nombre de la clienta", max_length=200)
    cliente_telefono = models.CharField("teléfono de contacto", max_length=50, blank=True)
    fecha = models.DateField("fecha de atención", default=timezone.now, db_index=True)
    hora = models.TimeField("horario de inicio", default=timezone.now)
    precio_acordado = models.DecimalField(
        "precio acordado / cobrado",
        max_digits=10,
        decimal_places=2,
        help_text="Precio final pactado con la clienta según largo o volumen de cabello.",
    )
    duracion_minutos = models.PositiveIntegerField(
        "duración personalizada (minutos)",
        default=60,
        help_text="Tiempo asignado según complejidad del trabajo.",
    )
    estado = models.CharField(
        "estado del servicio",
        max_length=20,
        choices=Estado.choices,
        default=Estado.COMPLETADO,
    )
    notas = models.TextField("notas o especificaciones técnicas", blank=True)
    insumos_descontados = models.BooleanField(
        "insumos descontados en cierre de caja",
        default=False,
        help_text="Indica si este servicio ya fue computado en el cierre del día.",
    )
    fecha_creacion = models.DateTimeField("fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "servicio realizado"
        verbose_name_plural = "servicios realizados"
        ordering = ["-fecha", "-hora"]

    def __str__(self) -> str:
        return f"{self.servicio.nombre} a {self.cliente_nombre} ({self.fecha} {self.hora.strftime('%H:%M')}) - ${self.precio_acordado:,.2f}"

    # ── Aliases camelCase ──

    @property
    def clienteNombre(self) -> str:
        return self.cliente_nombre

    @property
    def precioAcordado(self) -> Decimal:
        return self.precio_acordado

    @property
    def duracionMinutos(self) -> int:
        return self.duracion_minutos

    @property
    def insumosDescontados(self) -> bool:
        return self.insumos_descontados


class ConsumoInsumoCierre(models.Model):
    """
    Auditoría del descuento masivo de insumos ejecutado al finalizar el día,
    computando la cantidad de personas atendidas por cada servicio.
    """

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="consumos_cierre",
        verbose_name="servicio",
    )
    fecha = models.DateField("fecha del cierre", db_index=True)
    producto = models.ForeignKey(
        "inventario.Producto",
        on_delete=models.CASCADE,
        related_name="consumos_servicios",
        verbose_name="insumo descontado",
    )
    cantidad = models.PositiveIntegerField("cantidad total consumida")
    cantidad_servicios_computados = models.PositiveIntegerField(
        "cantidad de personas atendidas",
        default=1,
    )
    usuario_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="responsable del cierre",
    )
    fecha_registro = models.DateTimeField("fecha y hora de registro", auto_now_add=True)

    class Meta:
        verbose_name = "consumo de insumo al cierre"
        verbose_name_plural = "consumos de insumos al cierre"
        ordering = ["-fecha", "-fecha_registro"]

    def __str__(self) -> str:
        return f"Cierre {self.fecha}: {self.cantidad} u. de {self.producto.nombre} ({self.cantidad_servicios_computados}x {self.servicio.nombre})"

    # ── Aliases camelCase ──

    @property
    def cantidadServiciosComputados(self) -> int:
        return self.cantidad_servicios_computados

    @property
    def usuarioResponsable(self) -> Any:
        return self.usuario_responsable
