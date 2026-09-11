"""
Peluquería Lorena — Formularios del módulo de Caja y Ventas.
"""
from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.inventario.models import Producto
from apps.servicios.models import Servicio, ServicioRealizado
from apps.usuarios.models import Usuario
from .models import Cobro


class CobroForm(forms.Form):
    """Formulario de registro de cobro con medio de pago."""

    TIPO_CHOICES = Cobro.Tipo.choices
    MEDIO_CHOICES = Cobro.MedioPago.choices

    tipo = forms.ChoiceField(
        label="Tipo de cobro",
        choices=TIPO_CHOICES,
        initial=Cobro.Tipo.SERVICIO,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_tipo"}),
    )
    cliente = forms.ModelChoiceField(
        label="Clienta registrada (opcional)",
        queryset=Cliente.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_cliente"}),
    )
    cliente_nombre = forms.CharField(
        label="Nombre de la clienta",
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre y apellido", "id": "id_cliente_nombre"}
        ),
    )
    profesional = forms.ModelChoiceField(
        label="Profesional que cobra",
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    servicio = forms.ModelChoiceField(
        label="Servicio del catálogo",
        queryset=Servicio.objects.filter(activo=True).order_by("categoria", "nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_servicio"}),
    )
    servicio_realizado = forms.ModelChoiceField(
        label="Atención del día (opcional)",
        queryset=ServicioRealizado.objects.all().order_by("-fecha", "-hora"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_servicio_realizado"}),
    )
    producto = forms.ModelChoiceField(
        label="Producto a vender",
        queryset=Producto.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_producto"}),
    )
    cantidad = forms.IntegerField(
        label="Cantidad",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "id": "id_cantidad"}),
    )
    precio_unitario = forms.DecimalField(
        label="Precio unitario ($)",
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "min": 0, "id": "id_precio_unitario"}
        ),
    )
    medio_pago = forms.ChoiceField(
        label="Medio de pago",
        choices=MEDIO_CHOICES,
        initial=Cobro.MedioPago.EFECTIVO,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_medio_pago"}),
    )
    fecha = forms.DateField(
        label="Fecha de cobro",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        if tipo == Cobro.Tipo.PRODUCTO and not datos.get("producto"):
            self.add_error("producto", "Seleccioná el producto a vender.")
        if tipo == Cobro.Tipo.SERVICIO and not datos.get("precio_unitario"):
            if not datos.get("servicio") and not datos.get("servicio_realizado"):
                self.add_error(
                    "precio_unitario",
                    "Indicá el precio o seleccioná el servicio cobrado.",
                )
        return datos


class CierreCajaForm(forms.Form):
    """Confirmación del cierre de caja diario."""

    fecha = forms.DateField(
        label="Fecha del cierre",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    observaciones = forms.CharField(
        label="Observaciones del cierre",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 2, "placeholder": "Diferencias, faltantes, notas..."}
        ),
    )


class ReporteMediosForm(forms.Form):
    """Filtros del reporte por medio de pago."""

    fecha_desde = forms.DateField(
        label="Desde",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    fecha_hasta = forms.DateField(
        label="Hasta",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def clean(self):
        datos = super().clean()
        desde = datos.get("fecha_desde")
        hasta = datos.get("fecha_hasta")
        if desde and hasta and desde > hasta:
            raise forms.ValidationError("La fecha inicial no puede ser posterior a la final.")
        return datos
