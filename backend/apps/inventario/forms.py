"""
Peluquería Lorena — Formularios del módulo de Inventario.

Define los formularios para:
- RF 7.1: Alta de productos (ProductoForm con stock inicial).
- RF 7.1: Edición de productos (ProductoEditForm sin stock actual, solo nombre, descripción, precio y stock mínimo).
- Agregar Stock / Reposición (AgregarStockForm).
- RF 7.2: Descuento manual de stock al finalizar servicio (ConsumoServicioForm).
"""
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError

from .models import MovimientoStock, Producto


class ProductoForm(forms.ModelForm):
    """Formulario para dar de alta nuevos productos en el catálogo con su stock inicial."""

    class Meta:
        model = Producto
        fields = ["nombre", "descripcion", "precio", "unidad_medida", "stock_actual", "stock_minimo"]
        labels = {
            "nombre": "Nombre del producto",
            "descripcion": "Descripción / Detalles",
            "precio": "Precio ($)",
            "unidad_medida": "¿Cómo se mide este producto?",
            "stock_actual": "Stock Inicial",
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
            "unidad_medida": forms.RadioSelect(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "stock_actual": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "Ej: 10 (unidades iniciales)",
                }
            ),
            "stock_minimo": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "Ej: 3 (alerta reposición)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["stock_actual"].initial = None
            self.fields["stock_minimo"].initial = None
            self.fields["stock_actual"].required = False
            self.fields["stock_minimo"].required = False

    def clean_precio(self) -> Decimal:
        precio = self.cleaned_data.get("precio")
        if precio is not None and precio < Decimal("0.00"):
            raise ValidationError("El precio no puede ser un valor negativo.")
        return precio

    def clean_stock_actual(self) -> int:
        stock = self.cleaned_data.get("stock_actual")
        if stock is None:
            return 0
        if stock < 0:
            raise ValidationError("El stock no puede ser un valor negativo.")
        return stock

    def clean_stock_minimo(self) -> int:
        stock = self.cleaned_data.get("stock_minimo")
        if stock is None:
            return 0
        if stock < 0:
            raise ValidationError("El stock mínimo no puede ser un valor negativo.")
        return stock


class ProductoEditForm(forms.ModelForm):
    """
    Formulario para editar productos existentes.
    Permite modificar únicamente nombre, descripción, precio y stock mínimo.
    El stock actual se modifica exclusivamente por Agregar/Descontar Stock.
    """

    class Meta:
        model = Producto
        fields = ["nombre", "descripcion", "precio", "unidad_medida", "stock_minimo"]
        labels = {
            "nombre": "Nombre del producto",
            "descripcion": "Descripción / Detalles",
            "precio": "Precio ($)",
            "unidad_medida": "¿Cómo se mide este producto?",
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
            "unidad_medida": forms.RadioSelect(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "stock_minimo": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "Ej: 3 (alerta reposición)",
                }
            ),
        }

    def clean_precio(self) -> Decimal:
        precio = self.cleaned_data.get("precio")
        if precio is not None and precio < Decimal("0.00"):
            raise ValidationError("El precio no puede ser un valor negativo.")
        return precio

    def clean_stock_minimo(self) -> int:
        stock = self.cleaned_data.get("stock_minimo")
        if stock is None:
            return 0
        if stock < 0:
            raise ValidationError("El stock mínimo no puede ser un valor negativo.")
        return stock


class AgregarStockForm(forms.Form):
    """Formulario para reponer o agregar existencias a un producto."""

    producto = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True).order_by("nombre"),
        label="Producto a reponer",
        empty_label="-- Seleccionar producto --",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cantidad = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Cantidad a agregar (unidades)",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )
    motivo = forms.CharField(
        label="Motivo u observaciones",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Ej: Compra a distribuidora, reposición mensual, factura N°...",
            }
        ),
        help_text="Opcional: Detalle de la compra o ingreso de mercadería.",
    )


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
