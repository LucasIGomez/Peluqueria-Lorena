"""
Peluquería Lorena — Serializadores DRF del módulo de Inventario.

Proporciona serialización y validación para la API REST de inventario.
"""
from rest_framework import serializers

from .models import MovimientoStock, Producto


class ProductoSerializer(serializers.ModelSerializer):
    """Serializador para operaciones sobre el modelo Producto."""

    esta_bajo_stock = serializers.BooleanField(read_only=True)
    stockActual = serializers.IntegerField(source="stock_actual", required=False)
    stockMinimo = serializers.IntegerField(source="stock_minimo", required=False)

    class Meta:
        model = Producto
        fields = [
            "id",
            "nombre",
            "descripcion",
            "precio",
            "unidad_medida",
            "stock_actual",
            "stock_minimo",
            "stockActual",
            "stockMinimo",
            "esta_bajo_stock",
            "activo",
            "creado_en",
            "actualizado_en",
        ]
        read_only_fields = ["id", "creado_en", "actualizado_en", "esta_bajo_stock"]

    def validate_precio(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio no puede ser negativo.")
        return value

    def validate_stock_actual(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock actual no puede ser negativo.")
        return value

    def validate_stock_minimo(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock mínimo no puede ser negativo.")
        return value


class MovimientoStockSerializer(serializers.ModelSerializer):
    """Serializador para el historial de movimientos de stock."""

    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    tipo_movimiento_display = serializers.CharField(source="get_tipo_movimiento_display", read_only=True)
    usuario_nombre = serializers.CharField(source="usuario.nombre", read_only=True, default=None)

    class Meta:
        model = MovimientoStock
        fields = [
            "id",
            "producto",
            "producto_nombre",
            "tipo_movimiento",
            "tipo_movimiento_display",
            "cantidad",
            "stock_previo",
            "stock_posterior",
            "motivo",
            "usuario",
            "usuario_nombre",
            "fecha",
        ]
        read_only_fields = [
            "id",
            "stock_previo",
            "stock_posterior",
            "fecha",
        ]


class DescuentoStockSerializer(serializers.Serializer):
    """
    RF 7.2: Serializador para registrar manualmente el consumo de stock
    al finalizar un servicio a través de la API.
    """

    producto_id = serializers.IntegerField(required=True)
    cantidad = serializers.IntegerField(min_value=1, default=1)
    motivo = serializers.CharField(required=True, max_length=500)
    tipo_movimiento = serializers.ChoiceField(
        choices=MovimientoStock.TipoMovimiento.choices,
        default=MovimientoStock.TipoMovimiento.DESCUENTO,
    )
