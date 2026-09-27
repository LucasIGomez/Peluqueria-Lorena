"""
Peluquería Lorena — Modelos del módulo de Beneficios y Fidelización (RF10).

Define las entidades de negocio para:
1. ReglaBeneficio (RF 10.1): Motor de reglas parametrizable por la administradora
   (tipo CUMPLEAÑOS / REGULARIDAD, umbrales, recompensa y plantilla de mensaje).
2. BeneficioOtorgado (RF 10.2 / RF 10.3): Cupón/beneficio asignado a una clienta,
   con código único, vigencia y estado (DISPONIBLE, CANJEADO, VENCIDO).
3. MensajeBeneficio: Historial de avisos generados (mock WhatsApp/Email extensible),
   que garantiza un solo envío anual por cumpleaños y auditoría de cada disparo.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from django.db import models
from django.utils import timezone


class ReglaBeneficio(models.Model):
    """
    Configuración del motor de reglas de fidelización (RF 10.1).

    La administradora define umbrales y recompensas sin tocar código:
    - CUMPLEAÑOS: se dispara a clientas con cumpleaños dentro de `ventana_dias`.
    - REGULARIDAD: se dispara al alcanzar `min_visitas` o `min_monto` consumido
      dentro de los últimos `periodo_dias` (0 o nulo = historial completo).
    """

    class Tipo(models.TextChoices):
        CUMPLEANOS = "CUMPLEANOS", "Beneficio de Cumpleaños"
        REGULARIDAD = "REGULARIDAD", "Beneficio por Regularidad"

    class TipoRecompensa(models.TextChoices):
        PORCENTAJE = "PORCENTAJE", "Porcentaje de descuento (%)"
        MONTO_FIJO = "MONTO_FIJO", "Monto fijo de descuento ($)"
        SERVICIO = "SERVICIO", "Servicio bonificado (sin cargo)"

    nombre = models.CharField(
        "nombre de la regla",
        max_length=150,
        help_text="Ej: Cumpleaños 15% OFF, Clienta fiel 3 visitas.",
    )
    tipo = models.CharField(
        "tipo de beneficio",
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.CUMPLEANOS,
        db_index=True,
    )
    descripcion = models.CharField(
        "descripción / notas internas",
        max_length=250,
        blank=True,
    )
    activo = models.BooleanField("regla activa", default=True, db_index=True)

    # ── Criterios de regularidad (RF 10.3) ──
    min_visitas = models.PositiveIntegerField(
        "mínimo de visitas (turnos/atenciones completadas)",
        default=3,
        help_text="Cantidad mínima de visitas completadas para disparar el beneficio. Solo aplica a REGULARIDAD.",
    )
    min_monto = models.DecimalField(
        "monto total mínimo consumido ($)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alternativa o complemento a visitas: monto acumulado mínimo. 0 = no se exige monto.",
    )
    periodo_dias = models.PositiveIntegerField(
        "período de evaluación (días hacia atrás)",
        default=30,
        help_text="Ventana móvil de análisis. Ej: 30 = últimos 30 días. 0 = todo el historial de la clienta.",
    )

    # ── Criterio de cumpleaños (RF 10.2) ──
    ventana_dias = models.PositiveIntegerField(
        "ventana de aviso previo (días)",
        default=5,
        help_text="Con cuántos días de anticipación se otorga el beneficio de cumpleaños. Solo aplica a CUMPLEAÑOS.",
    )

    # ── Recompensa ──
    tipo_recompensa = models.CharField(
        "tipo de recompensa",
        max_length=20,
        choices=TipoRecompensa.choices,
        default=TipoRecompensa.PORCENTAJE,
    )
    valor = models.DecimalField(
        "valor de la recompensa",
        max_digits=12,
        decimal_places=2,
        default=Decimal("10.00"),
        help_text="Si es PORCENTAJE: 0–100. Si es MONTO_FIJO: pesos $. Si es SERVICIO: se ignora y se usa el servicio bonificado.",
    )
    servicio_bonificado = models.ForeignKey(
        "servicios.Servicio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reglas_bonificacion",
        verbose_name="servicio bonificado",
        help_text="Solo cuando la recompensa es SERVICIO bonificado.",
    )

    # ── Mensajería y vigencia ──
    plantilla_mensaje = models.TextField(
        "plantilla de mensaje personalizada",
        default=(
            "Hola {nombre_cliente}, ¡Peluquería Lorena te saluda! "
            "Tenés un beneficio de {descuento} con el código {codigo}, "
            "válido hasta el {fecha_limite}. ¡Te esperamos!"
        ),
        help_text="Variables disponibles: {nombre_cliente}, {descuento}, {codigo}, {fecha_limite}.",
    )
    dias_validez = models.PositiveIntegerField(
        "vigencia del cupón (días)",
        default=7,
        help_text="Cuántos días permanece DISPONIBLE el beneficio desde su otorgamiento.",
    )

    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("última actualización", auto_now=True)

    class Meta:
        verbose_name = "regla de beneficio"
        verbose_name_plural = "reglas de beneficios"
        ordering = ["tipo", "nombre"]

    def __str__(self) -> str:
        estado = "Activa" if self.activo else "Inactiva"
        return f"{self.nombre} ({self.get_tipo_display()} — {estado})"

    def clean(self) -> None:
        """Validación de dominio: la vigencia nunca puede ser de 0 días."""
        from django.core.exceptions import ValidationError
        if self.dias_validez is not None and self.dias_validez < 1:
            raise ValidationError({"dias_validez": "La vigencia del cupón debe ser de al menos 1 día."})

    # ── Descripción legible de la recompensa ──
    @property
    def descripcion_recompensa(self) -> str:
        """Texto corto de la recompensa para mensajes y auditoría."""
        if self.tipo_recompensa == self.TipoRecompensa.PORCENTAJE:
            return f"{self.valor:,.2f}% OFF".replace(",", "X").replace(".", ",").replace("X", ".")
        if self.tipo_recompensa == self.TipoRecompensa.MONTO_FIJO:
            return f"${self.valor:,.2f} OFF".replace(",", "X").replace(".", ",").replace("X", ".")
        if self.servicio_bonificado:
            return f"{self.servicio_bonificado.nombre} sin cargo"
        return "Servicio bonificado"

    @property
    def descripcionRecompensa(self) -> str:
        return self.descripcion_recompensa


# Alias exigido por la especificación (nombre alternativo del motor de reglas).
BeneficioConfiguracion = ReglaBeneficio


class BeneficioOtorgado(models.Model):
    """
    Cupón/beneficio asignado a una clienta (RF 10.2 y RF 10.3).

    Registra fecha de asignación, expiración, código único y estado, lo que
    permite garantizar un solo envío anual por cumpleaños y auditar cada
    disparo por regularidad.
    """

    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        CANJEADO = "CANJEADO", "Canjeado"
        VENCIDO = "VENCIDO", "Vencido"

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.CASCADE,
        related_name="beneficios",
        verbose_name="clienta beneficiaria",
    )
    regla = models.ForeignKey(
        ReglaBeneficio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_otorgados",
        verbose_name="regla aplicada",
    )
    tipo = models.CharField(
        "tipo de beneficio (foto al otorgar)",
        max_length=20,
        choices=ReglaBeneficio.Tipo.choices,
        db_index=True,
    )
    codigo = models.CharField(
        "código de cupón",
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Código único para canje en caja (ej: CUM-A1B2C3).",
    )
    descripcion_beneficio = models.CharField(
        "detalle de la recompensa otorgada",
        max_length=250,
        help_text="Foto del beneficio al momento del otorgamiento (ej: 15,00% OFF).",
    )
    # Foto de la recompensa para canje en caja sin depender de la regla viva.
    tipo_recompensa = models.CharField(
        "tipo de recompensa (foto)",
        max_length=20,
        choices=ReglaBeneficio.TipoRecompensa.choices,
        default=ReglaBeneficio.TipoRecompensa.PORCENTAJE,
    )
    valor = models.DecimalField(
        "valor otorgado (foto)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    mensaje_renderizado = models.TextField(
        "mensaje personalizado enviado",
        blank=True,
        help_text="Texto final con variables ya reemplazadas.",
    )
    estado = models.CharField(
        "estado del beneficio",
        max_length=20,
        choices=Estado.choices,
        default=Estado.DISPONIBLE,
        db_index=True,
    )
    # Evita envíos repetidos: año del cumpleaños o ciclo de regularidad.
    ciclo_referencia = models.CharField(
        "ciclo de referencia (anti-duplicados)",
        max_length=20,
        db_index=True,
        help_text="Para CUMPLEAÑOS: año (ej: 2026). Para REGULARIDAD: período evaluado.",
    )
    # Métricas de auditoría al momento del disparo por regularidad.
    visitas_contadas = models.PositiveIntegerField(
        "visitas contabilizadas",
        default=0,
    )
    monto_acumulado = models.DecimalField(
        "monto acumulado evaluado ($)",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fecha_otorgamiento = models.DateTimeField("fecha de asignación", auto_now_add=True)
    fecha_vencimiento = models.DateField("fecha de expiración", db_index=True)
    fecha_canje = models.DateTimeField("fecha de canje", null=True, blank=True)
    canjeado_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_canjeados",
        verbose_name="canjeado por (profesional)",
    )
    observaciones = models.TextField("observaciones de canje", blank=True)

    class Meta:
        verbose_name = "beneficio otorgado"
        verbose_name_plural = "beneficios otorgados"
        ordering = ["-fecha_otorgamiento"]
        constraints = [
            models.UniqueConstraint(
                fields=["cliente", "regla", "ciclo_referencia"],
                name="unico_beneficio_por_ciclo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} — {self.cliente.nombre} ({self.get_estado_display()})"

    # ── Lógica de dominio ──
    @property
    def esta_vigente(self) -> bool:
        """Indica si el cupón sigue canjeable (disponible y sin vencer)."""
        return self.estado == self.Estado.DISPONIBLE and self.fecha_vencimiento >= timezone.localdate()

    @property
    def estaVigente(self) -> bool:
        return self.esta_vigente

    def marcar_vencido(self) -> None:
        """Marca el beneficio como vencido si pasó su fecha límite."""
        if self.estado == self.Estado.DISPONIBLE and self.fecha_vencimiento < timezone.localdate():
            self.estado = self.Estado.VENCIDO
            self.save(update_fields=["estado"])

    def canjear(self, profesional=None, observaciones: str = "") -> None:
        """
        Canjea el beneficio en caja.

        Raises:
            ValueError: Si el cupón no está vigente.
        """
        if not self.esta_vigente:
            raise ValueError(f"El cupón {self.codigo} no está vigente (estado: {self.get_estado_display()}).")
        self.estado = self.Estado.CANJEADO
        self.fecha_canje = timezone.now()
        if profesional is not None:
            self.canjeado_por = profesional
        if observaciones:
            self.observaciones = observaciones.strip()
        self.save(update_fields=["estado", "fecha_canje", "canjeado_por", "observaciones"])


# Alias de historial exigido por la especificación.
HistorialBeneficio = BeneficioOtorgado


class MensajeBeneficio(models.Model):
    """
    Historial de avisos generados por cada beneficio (RF 10.2 / RF 10.3).

    El servicio de mensajería (mock extensible) registra aquí cada mensaje listo
    para despachar por WhatsApp/Email, con su estado de envío para auditoría.
    """

    class Canal(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        EMAIL = "EMAIL", "Email"
        MANUAL = "MANUAL", "Aviso manual en salón"

    class EstadoEnvio(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de envío"
        ENVIADO = "ENVIADO", "Enviado / Simulado"
        FALLIDO = "FALLIDO", "Fallido"

    beneficio = models.ForeignKey(
        BeneficioOtorgado,
        on_delete=models.CASCADE,
        related_name="mensajes",
        verbose_name="beneficio avisado",
    )
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.CASCADE,
        related_name="mensajes_beneficios",
        verbose_name="clienta destinataria",
    )
    canal = models.CharField(
        "canal de aviso",
        max_length=20,
        choices=Canal.choices,
        default=Canal.WHATSAPP,
    )
    destinatario = models.CharField(
        "destinatario (teléfono o email)",
        max_length=200,
        blank=True,
    )
    contenido = models.TextField("contenido del mensaje")
    estado_envio = models.CharField(
        "estado del envío",
        max_length=20,
        choices=EstadoEnvio.choices,
        default=EstadoEnvio.PENDIENTE,
        db_index=True,
    )
    detalle_error = models.TextField("detalle del error", blank=True)
    fecha_creacion = models.DateTimeField("fecha de registro", auto_now_add=True)
    fecha_envio = models.DateTimeField("fecha de envío", null=True, blank=True)

    class Meta:
        verbose_name = "mensaje de beneficio"
        verbose_name_plural = "historial de mensajes de beneficios"
        ordering = ["-fecha_creacion"]

    def __str__(self) -> str:
        return f"Aviso {self.get_canal_display()} a {self.cliente.nombre} ({self.get_estado_envio_display()})"

    # ── Aliases camelCase ──
    @property
    def estadoEnvio(self) -> str:
        return self.estado_envio

    @property
    def fechaEnvio(self):
        return self.fecha_envio
