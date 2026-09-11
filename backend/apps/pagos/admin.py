"""
Peluquería Lorena — Admin del módulo de Caja y Ventas.
"""
from django.contrib import admin

from .models import CierreCaja, Cobro


@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fecha",
        "cliente_nombre",
        "tipo",
        "medio_pago",
        "total",
        "anulado",
        "profesional",
    )
    list_filter = ("fecha", "tipo", "medio_pago", "anulado")
    search_fields = ("cliente_nombre",)
    readonly_fields = ("subtotal", "porcentaje_descuento", "monto_descuento", "total")


@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "cantidad_cobros", "total_general", "responsable")
    readonly_fields = (
        "cantidad_cobros",
        "total_efectivo",
        "total_mercado_pago",
        "total_uala",
        "total_tarjeta_debito",
        "total_tarjeta_credito",
        "total_descuentos",
        "total_general",
    )
