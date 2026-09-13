"""
Peluquería Lorena — Serializers del módulo de Caja y Ventas.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import CierreCaja, Cobro


class CobroSerializer(serializers.ModelSerializer):
    """Serializer de cobros para la API REST."""

    medio_pago_display = serializers.CharField(
        source="get_medio_pago_display", read_only=True
    )
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    def validate_porcentaje_descuento(self, valor):
        """El descuento manual debe estar entre 0 y 100%."""
        if valor is not None and (valor < 0 or valor > 100):
            raise serializers.ValidationError("El descuento debe estar entre 0 y 100%.")
        return valor

    class Meta:
        model = Cobro
        fields = [
            "id",
            "cliente_nombre",
            "tipo",
            "tipo_display",
            "medio_pago",
            "medio_pago_display",
            "cantidad",
            "precio_unitario",
            "subtotal",
            "porcentaje_descuento",
            "monto_descuento",
            "total",
            "fecha",
            "anulado",
            "fecha_creacion",
        ]
        read_only_fields = [
            "subtotal",
            "monto_descuento",
            "total",
            "anulado",
            "fecha_creacion",
        ]


class CierreCajaSerializer(serializers.ModelSerializer):
    """Serializer de cierres de caja para la API REST."""

    class Meta:
        model = CierreCaja
        fields = [
            "id",
            "fecha",
            "cantidad_cobros",
            "total_efectivo",
            "total_mercado_pago",
            "total_uala",
            "total_tarjeta_debito",
            "total_tarjeta_credito",
            "total_descuentos",
            "total_general",
            "observaciones",
            "fecha_creacion",
        ]
