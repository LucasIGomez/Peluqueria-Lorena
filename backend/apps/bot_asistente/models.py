"""
Peluquería Lorena — Modelos del módulo de Bot Asistente (WhatsApp).

Define:
1. ConversacionBot: Sesión e historial de interacción por clienta/teléfono y control de escalado humano.
2. MensajeBot: Auditoría de mensajes entrantes y salientes, incluyendo la intención y payload de IA.
"""
from __future__ import annotations

from typing import Optional
from django.db import models
from django.utils import timezone


class ConversacionBot(models.Model):
    """
    Representa el canal o sesión activa de WhatsApp con un número telefónico.
    Permite identificar a la clienta y saber si la conversación fue derivada a una persona.
    """

    class Estado(models.TextChoices):
        INICIAL = "INICIAL", "Primer contacto"
        MENU = "MENU", "Menú principal ofrecido"
        EN_PROCESO = "EN_PROCESO", "En proceso de agendado o consulta"
        ESCALADO_HUMANO = "ESCALADO_HUMANO", "Derivado a atención humana"

    telefono_cliente = models.CharField("teléfono / WhatsApp", max_length=50, unique=True, db_index=True)
    nombre_remitente = models.CharField("nombre informado por WhatsApp", max_length=200, blank=True)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversaciones_bot",
        verbose_name="clienta vinculada",
    )
    estado = models.CharField(
        "estado de la sesión",
        max_length=30,
        choices=Estado.choices,
        default=Estado.INICIAL,
    )
    requiere_humano = models.BooleanField(
        "requiere atención humana",
        default=False,
        help_text="Marcado cuando la clienta pide hablar con Lorena/Zaira o ante quejas/reclamos.",
    )
    fecha_creacion = models.DateTimeField("fecha de inicio", auto_now_add=True)
    ultimo_mensaje_at = models.DateTimeField("última interacción", auto_now=True)

    class Meta:
        verbose_name = "conversación de bot"
        verbose_name_plural = "conversaciones de bot"
        ordering = ["-ultimo_mensaje_at"]

    def __str__(self) -> str:
        return f"Chat {self.nombre_remitente or self.telefono_cliente} ({self.get_estado_display()})"


class MensajeBot(models.Model):
    """
    Registro cronológico de mensajes intercambiados vía WhatsApp Business API.
    """

    class Direccion(models.TextChoices):
        ENTRANTE = "ENTRANTE", "Entrante (Clienta -> Bot)"
        SALIENTE = "SALIENTE", "Saliente (Bot -> Clienta)"

    conversacion = models.ForeignKey(
        ConversacionBot,
        on_delete=models.CASCADE,
        related_name="mensajes",
        verbose_name="conversación",
    )
    direccion = models.CharField(
        "dirección",
        max_length=15,
        choices=Direccion.choices,
    )
    contenido = models.TextField("contenido del mensaje")
    intencion = models.CharField("intención detectada", max_length=50, blank=True)
    payload_ia = models.JSONField("respuesta estructurada de IA", null=True, blank=True)
    fecha_creacion = models.DateTimeField("fecha y hora", auto_now_add=True)

    class Meta:
        verbose_name = "mensaje de bot"
        verbose_name_plural = "mensajes de bot"
        ordering = ["fecha_creacion"]

    def __str__(self) -> str:
        return f"[{self.get_direccion_display()}] {self.contenido[:40]}..."
