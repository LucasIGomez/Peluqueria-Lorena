from django.contrib import admin

from .models import Turno


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ("cliente_nombre", "servicio", "fecha", "hora", "profesional", "estado")
    list_filter = ("estado", "fecha", "profesional")
    search_fields = ("cliente_nombre", "cliente_telefono")
    date_hierarchy = "fecha"
