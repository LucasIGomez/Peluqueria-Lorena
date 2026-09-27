"""Peluquería Lorena — Admin del módulo de Beneficios y Fidelización (RF10)."""
from django.contrib import admin

from .models import BeneficioOtorgado, MensajeBeneficio, ReglaBeneficio


@admin.register(ReglaBeneficio)
class ReglaBeneficioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "tipo_recompensa", "valor", "activo", "fecha_actualizacion")
    list_filter = ("tipo", "tipo_recompensa", "activo")
    search_fields = ("nombre", "descripcion")


@admin.register(BeneficioOtorgado)
class BeneficioOtorgadoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "cliente", "tipo", "estado", "fecha_vencimiento", "fecha_otorgamiento")
    list_filter = ("tipo", "estado")
    search_fields = ("codigo", "cliente__nombre", "cliente__telefono")
    readonly_fields = ("codigo", "fecha_otorgamiento", "fecha_canje")


@admin.register(MensajeBeneficio)
class MensajeBeneficioAdmin(admin.ModelAdmin):
    list_display = ("beneficio", "cliente", "canal", "estado_envio", "fecha_creacion")
    list_filter = ("canal", "estado_envio")
    search_fields = ("cliente__nombre", "contenido")
