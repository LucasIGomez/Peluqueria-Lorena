"""
Peluquería Lorena — Modelos del módulo de Clientes.

Define las entidades para:
1. Cliente: Agenda de clientas, datos de contacto, cumpleaños y preferencias.
2. TratamientoProgreso: Ficha de seguimiento de tratamientos multisesión.
3. EvolucionSesion: Registro técnico sesión a sesión (diagnóstico, fórmulas químicas, evolución).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from django.conf import settings
from django.db import models
from django.utils import timezone


class Cliente(models.Model):
    """
    Representa a una clienta de Peluquería Lorena.
    Almacena datos personales, fecha de nacimiento para promociones/saludos
    y notas de salud capilar o alergias.
    """

    nombre = models.CharField("nombre completo", max_length=200)
    telefono = models.CharField("teléfono / WhatsApp", max_length=50, db_index=True)
    email = models.EmailField("correo electrónico", blank=True, null=True)
    fecha_nacimiento = models.DateField("fecha de nacimiento", blank=True, null=True)
    notas_alergias = models.TextField(
        "alergias o sensibilidad",
        blank=True,
        help_text="Alergias conocidas a químicos o sensibilidad en cuero cabelludo.",
    )
    preferencias = models.TextField(
        "preferencias de estilo",
        blank=True,
        help_text="Preferencias de color, corte, productos favoritos o café.",
    )
    activo = models.BooleanField("activo", default=True)
    fecha_registro = models.DateTimeField("fecha de registro", default=timezone.now)

    class Meta:
        verbose_name = "clienta"
        verbose_name_plural = "clientas"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.telefono})"

    # ── Propiedades de dominio ──

    @property
    def es_cumpleanos_hoy(self) -> bool:
        """Determina si hoy es el cumpleaños de la clienta."""
        if not self.fecha_nacimiento:
            return False
        hoy = timezone.localdate()
        return (self.fecha_nacimiento.month == hoy.month) and (self.fecha_nacimiento.day == hoy.day)

    @property
    def dias_para_cumpleanos(self) -> Optional[int]:
        """Calcula cuántos días faltan para el próximo cumpleaños de la clienta."""
        if not self.fecha_nacimiento:
            return None
        hoy = timezone.localdate()
        try:
            proximo_cumple = date(hoy.year, self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        except ValueError:
            proximo_cumple = date(hoy.year, 2, 28)
        if proximo_cumple < hoy:
            try:
                proximo_cumple = date(hoy.year + 1, self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            except ValueError:
                proximo_cumple = date(hoy.year + 1, 2, 28)
        return (proximo_cumple - hoy).days

    @property
    def cumple_proximo(self) -> bool:
        """Indica si la clienta cumple años en los próximos 15 días."""
        dias = self.dias_para_cumpleanos
        return dias is not None and 0 <= dias <= 15

    @property
    def cumpleProximo(self) -> bool:
        return self.cumple_proximo

    @property
    def link_whatsapp(self) -> str:
        """Genera un enlace directo a WhatsApp saneando el número telefónico."""
        # Limpiar caracteres no numéricos
        solo_digitos = re.sub(r"\D", "", self.telefono)
        # Si no tiene código de país y empieza con 15 o similar en Argentina, adaptar
        if len(solo_digitos) == 10 and not solo_digitos.startswith("54"):
            solo_digitos = f"549{solo_digitos}"
        elif len(solo_digitos) == 11 and solo_digitos.startswith("11"):
            solo_digitos = f"549{solo_digitos}"
        return f"https://wa.me/{solo_digitos}"

    # ── Aliases camelCase ──

    @property
    def esCumpleanosHoy(self) -> bool:
        return self.es_cumpleanos_hoy

    @property
    def diasParaCumpleanos(self) -> Optional[int]:
        return self.dias_para_cumpleanos

    @property
    def linkWhatsapp(self) -> str:
        return self.link_whatsapp

    @property
    def fechaNacimiento(self) -> Optional[date]:
        return self.fecha_nacimiento

    @property
    def notasAlergias(self) -> str:
        return self.notas_alergias

    @property
    def fechaRegistro(self) -> timezone.datetime:
        return self.fecha_registro


class TratamientoProgreso(models.Model):
    """
    Ficha de seguimiento para procesos capilares que se desarrollan en varias sesiones
    (ej: decoloración progresiva, alisado por etapas, cronograma de nutrición).
    """

    class Estado(models.TextChoices):
        EN_PROGRESO = "EN_PROGRESO", "En Progreso"
        FINALIZADO = "FINALIZADO", "Finalizado"
        PAUSADO = "PAUSADO", "Pausado"

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="tratamientos_progreso",
        verbose_name="clienta",
    )
    titulo_tratamiento = models.CharField(
        "título del tratamiento",
        max_length=200,
        help_text="Ej: Decoloración en etapas a Rubio Manteca, Alisado Progresivo",
    )
    servicio_nombre = models.CharField(
        "servicio base",
        max_length=150,
        help_text="Nombre del servicio asociado (ej: Balayage, Alisado, etc.)",
    )
    total_sesiones_estimadas = models.PositiveIntegerField(
        "total de sesiones estimadas",
        default=1,
    )
    sesion_actual = models.PositiveIntegerField(
        "sesión actual",
        default=1,
    )
    estado = models.CharField(
        "estado",
        max_length=20,
        choices=Estado.choices,
        default=Estado.EN_PROGRESO,
    )
    notas_objetivo = models.TextField(
        "objetivo técnico",
        blank=True,
        help_text="Meta a alcanzar sin comprometer la resistencia capilar.",
    )
    fecha_inicio = models.DateField("fecha de inicio", default=timezone.now)
    fecha_finalizacion = models.DateField("fecha de finalización", blank=True, null=True)

    class Meta:
        verbose_name = "tratamiento en progreso"
        verbose_name_plural = "tratamientos en progreso"
        ordering = ["-fecha_inicio"]

    def __str__(self) -> str:
        return f"{self.titulo_tratamiento} — {self.cliente.nombre} ({self.sesion_actual}/{self.total_sesiones_estimadas})"

    @property
    def porcentaje_progreso(self) -> int:
        """Calcula el porcentaje de avance del tratamiento."""
        if self.total_sesiones_estimadas <= 0:
            return 100
        pct = int((self.sesion_actual / self.total_sesiones_estimadas) * 100)
        return min(pct, 100)

    @property
    def siguiente_numero_sesion(self) -> int:
        """Determina el número correlativo de la próxima sesión técnica a registrar."""
        if not self.sesiones_evolucion.exists():
            return 1
        return self.sesion_actual + 1

    # ── Aliases camelCase ──

    @property
    def siguienteNumeroSesion(self) -> int:
        return self.siguiente_numero_sesion

    @property
    def tituloTratamiento(self) -> str:
        return self.titulo_tratamiento

    @property
    def servicioNombre(self) -> str:
        return self.servicio_nombre

    @property
    def totalSesionesEstimadas(self) -> int:
        return self.total_sesiones_estimadas

    @property
    def sesionActual(self) -> int:
        return self.sesion_actual

    @property
    def porcentajeProgreso(self) -> int:
        return self.porcentaje_progreso

    @property
    def fechaInicio(self) -> date:
        return self.fecha_inicio


class EvolucionSesion(models.Model):
    """
    Registro técnico individual de cada sesión de un tratamiento multisesión.
    Registra diagnóstico de fibra, fórmulas químicas y recomendaciones.
    """

    tratamiento = models.ForeignKey(
        TratamientoProgreso,
        on_delete=models.CASCADE,
        related_name="sesiones_evolucion",
        verbose_name="tratamiento",
    )
    numero_sesion = models.PositiveIntegerField("número de sesión")
    fecha = models.DateField("fecha de la sesión", default=timezone.now)
    profesional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sesiones_realizadas",
        verbose_name="profesional",
    )
    diagnostico_fibra = models.TextField(
        "diagnóstico de la fibra capilar",
        help_text="Elasticidad, porosidad, tono base y tono alcanzado en la sesión.",
    )
    formula_quimica_utilizada = models.TextField(
        "fórmulas y productos aplicados",
        help_text="Proporciones (ej: 30g Deco + 60ml Ox 20 vol), matizadores, protectores de enlaces.",
    )
    tiempo_exposicion_minutos = models.PositiveIntegerField(
        "tiempo de exposición (minutos)",
        default=0,
    )
    resultado_obtenido = models.TextField("resultado obtenido")
    proxima_cita_recomendada = models.DateField(
        "próxima cita sugerida",
        blank=True,
        null=True,
    )
    indicaciones_hogar = models.TextField(
        "cuidados en el hogar",
        blank=True,
        help_text="Rutina recomendada (champú sin sulfatos, nutrición, protector térmico).",
    )
    fecha_registro = models.DateTimeField("fecha de registro", auto_now_add=True)

    class Meta:
        verbose_name = "evolución de sesión"
        verbose_name_plural = "evoluciones de sesión"
        ordering = ["numero_sesion", "fecha"]

    def __str__(self) -> str:
        return f"Sesión {self.numero_sesion} — {self.tratamiento.titulo_tratamiento} ({self.fecha})"

    # ── Aliases camelCase ──

    @property
    def numeroSesion(self) -> int:
        return self.numero_sesion

    @property
    def diagnosticoFibra(self) -> str:
        return self.diagnostico_fibra

    @property
    def formulaQuimicaUtilizada(self) -> str:
        return self.formula_quimica_utilizada

    @property
    def tiempoExposicionMinutos(self) -> int:
        return self.tiempo_exposicion_minutos

    @property
    def resultadoObtenido(self) -> str:
        return self.resultado_obtenido

    @property
    def proximaCitaRecomendada(self) -> Optional[date]:
        return self.proxima_cita_recomendada

    @property
    def indicacionesHogar(self) -> str:
        return self.indicaciones_hogar
