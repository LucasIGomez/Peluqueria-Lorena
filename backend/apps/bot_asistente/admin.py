"""
Peluquería Lorena — Administración de Conversaciones y Mensajes del Bot Asistente.
"""
from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import ConversacionBot, MensajeBot


class MensajeBotInline(admin.TabularInline):
    model = MensajeBot
    extra = 0
    can_delete = False
    readonly_fields = ("direccion", "wamid", "contenido", "intencion", "fecha_creacion")
    fields = ("fecha_creacion", "direccion", "contenido", "intencion", "wamid")


@admin.register(ConversacionBot)
class ConversacionBotAdmin(admin.ModelAdmin):
    list_display = (
        "telefono_cliente",
        "nombre_remitente",
        "cliente",
        "estado",
        "requiere_humano_badge",
        "ultimo_mensaje_at",
        "link_whatsapp",
    )
    list_filter = ("requiere_humano", "estado", "ultimo_mensaje_at")
    search_fields = ("telefono_cliente", "nombre_remitente", "cliente__nombre")
    readonly_fields = ("fecha_creacion", "ultimo_mensaje_at")
    inlines = [MensajeBotInline]
    actions = ["marcar_atendido"]

    @admin.display(description="Requiere Atención", boolean=True)
    def requiere_humano_badge(self, obj):
        return obj.requiere_humano

    @admin.display(description="Chatear en WhatsApp")
    def link_whatsapp(self, obj):
        tel = obj.telefono_cliente
        return format_html(
            '<a class="button" href="https://wa.me/{}" target="_blank" rel="noopener noreferrer" style="background:#25D366;color:#fff;padding:4px 10px;border-radius:4px;text-decoration:none;font-weight:600;">'
            'Abrir WhatsApp</a>',
            tel,
        )

    @admin.action(description="Marcar como atendido (quitar alerta humana)")
    def marcar_atendido(self, request, queryset):
        filas = queryset.update(requiere_humano=False, estado=ConversacionBot.Estado.EN_PROCESO)
        self.message_user(request, f"{filas} conversación(es) marcada(s) como atendida(s).")


@admin.register(MensajeBot)
class MensajeBotAdmin(admin.ModelAdmin):
    list_display = ("conversacion", "direccion", "contenido_corto", "intencion", "wamid", "fecha_creacion")
    list_filter = ("direccion", "intencion", "fecha_creacion")
    search_fields = ("contenido", "wamid", "conversacion__telefono_cliente", "conversacion__nombre_remitente")
    readonly_fields = ("fecha_creacion",)

    @admin.display(description="Contenido")
    def contenido_corto(self, obj):
        return (obj.contenido[:60] + "...") if len(obj.contenido) > 60 else obj.contenido
