"""
Peluquería Lorena — Formularios del módulo de Inventario.

Define los formularios para:
- RF 7.1: Alta y edición de productos (ProductoForm).
- RF 7.2: Descuento manual de stock al finalizar servicio (ConsumoServicioForm).
- Auditoría: Ajuste y reposición de stock (AjusteStockForm).
"""
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError

from .models import MovimientoStock, Producto


class ProductoForm(forms.ModelForm):
    """Formulario para dar de alta y editar productos en el inventario."""

    class Meta:
        model = Producto
        fields = ["nombre", "descripcion", "precio", "stock_actual", "stock_minimo"]
        labels = {
            "nombre": "Nombre del producto",
            "descripcion": "Descripción / Detalles",
            "precio": "Precio ($)",
            "stock_actual": "Stock Actual",
            "stock_minimo": "Stock Mínimo (Alerta)",
        }
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Shampoo Matizador 500ml",
                    "required": True,
                }
            ),
            "descripcion": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Información adicional, marca, uso recomendado...",
                }
            ),
            "precio": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "stock_actual": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "0",
                }
            ),
            "stock_minimo": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "0",
                }
            ),
        }

    def clean_precio(self) -> Decimal:
        precio = self.cleaned_data.get("precio")
        if precio is not None and precio < Decimal("0.00"):
            raise ValidationError("El precio no puede ser un valor negativo.")
        return precio

    def clean_stock_actual(self) -> int:
        stock = self.cleaned_data.get("stock_actual")
        if stock is not None and stock < 0:
            raise ValidationError("El stock actual no puede ser un valor negativo.")
        return stock

    def clean_stock_minimo(self) -> int:
        stock = self.cleaned_data.get("stock_minimo")
        if stock is not None and stock < 0:
            raise ValidationError("El stock mínimo no puede ser un valor negativo.")
        return stock


class ConsumoServicioForm(forms.Form):
    """
    RF 7.2: Formulario para registrar manualmente el consumo de stock
    al finalizar un servicio en el salón.
    """

    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by("nombre"),
        label="Producto / Insumo consumido",
        empty_label="-- Seleccionar producto --",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cantidad = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Cantidad consumida (unidades)",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )
    detalle_servicio = forms.CharField(
        label="Detalle del servicio realizado",
        required=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Ej: Tintura y decoloración en servicio de Balayage para Clienta Sofía...",
            }
        ),
        help_text="Indica el servicio, clienta o tratamiento donde se utilizó el insumo.",
    )

    def clean(self) -> dict:
        cleaned_data = super().clean()
        producto = cleaned_data.get("producto")
        cantidad = cleaned_data.get("cantidad")

        if producto and cantidad:
            if producto.stock_actual < cantidad:
                raise ValidationError(
                    f"No hay suficiente stock disponible de '{producto.nombre}'. "
                    f"Existencia actual: {producto.stock_actual} unidades, solicitadas: {cantidad}."
                )
        return cleaned_data


class AjusteStockForm(forms.Form):
    """Formulario para reposición de mercadería o ajuste manual de inventario."""

    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by("nombre"),
        label="Producto",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tipo_movimiento = forms.ChoiceField(
        choices=[
            (MovimientoStock.TipoMovimiento.REPOSICION, "Reposición / Entrada de stock"),
            (MovimientoStock.TipoMovimiento.AJUSTE_MANUAL, "Ajuste manual (salida/merma)"),
            (MovimientoStock.TipoMovimiento.VENTA_DIRECTA, "Venta directa a cliente"),
        ],
        label="Tipo de operación",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cantidad = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Cantidad de unidades",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )
    motivo = forms.CharField(
        required=False,
        label="Motivo u observaciones",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Factura proveedor, merma por vencimiento, venta mostrador...",
            }
        ),
    )

    def clean(self) -> dict:
        cleaned_data = super().clean()
        producto = cleaned_data.get("producto")
        tipo = cleaned_data.get("tipo_movimiento")
        cantidad = cleaned_data.get("cantidad")

        if producto and cantidad and tipo in (
            MovimientoStock.TipoMovimiento.AJUSTE_MANUAL,
            MovimientoStock.TipoMovimiento.VENTA_DIRECTA,
        ):
            if producto.stock_actual < cantidad:
                raise ValidationError(
                    f"Stock insuficiente para descontar {cantidad} u. de '{producto.nombre}'. "
                    f"Stock actual: {producto.stock_actual}."
                )
        return cleaned_data
