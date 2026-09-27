"""
Peluquería Lorena — Formularios del módulo de Comisiones y Liquidación (RF8).

Define formularios para:
- Parametrización de comisiones por categoría (RF 8.1).
- Registro rápido e intuitivo de trabajos por cada peluquera (RF 8.3).
- Filtros para el reporte y cierre de liquidación (RF 8.4).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django import forms
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.servicios.models import Servicio, ServicioRealizado
from apps.usuarios.models import Usuario
from .models import ConfiguracionComision, Liquidacion


class ConfiguracionComisionForm(forms.ModelForm):
    """Formulario para editar el porcentaje de comisión de una categoría de servicio."""

    class Meta:
        model = ConfiguracionComision
        fields = ["porcentaje", "descripcion", "activo"]
        widgets = {
            "porcentaje": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100"}
            ),
            "descripcion": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Detalle explicativo"}
            ),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_porcentaje(self) -> Decimal:
        pct = self.cleaned_data.get("porcentaje")
        if pct is None or pct < Decimal("0.00") or pct > Decimal("100.00"):
            raise forms.ValidationError("El porcentaje debe encontrarse entre 0% y 100%.")
        return pct


class RegistroTrabajoForm(forms.ModelForm):
    """
    Formulario simple para que la peluquera asiente de forma rápida
    el servicio realizado para el cálculo automático de su comisión (RF 8.3).
    """

    fecha = forms.DateField(
        label="Fecha de Atención",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
        input_formats=["%Y-%m-%d"],
    )
    hora = forms.TimeField(
        label="Horario",
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )

    class Meta:
        model = ServicioRealizado
        fields = [
            "servicio",
            "profesional",
            "cliente",
            "cliente_nombre",
            "cliente_telefono",
            "precio_acordado",
            "fecha",
            "hora",
            "notas",
        ]
        widgets = {
            "servicio": forms.Select(attrs={"class": "form-select", "id": "id_servicio_select"}),
            "profesional": forms.Select(attrs={"class": "form-select", "id": "id_profesional_select"}),
            "cliente": forms.Select(attrs={"class": "form-select", "id": "id_cliente_select"}),
            "cliente_nombre": forms.TextInput(
                attrs={"class": "form-control", "id": "id_cliente_nombre", "placeholder": "Nombre de la clienta atendida"}
            ),
            "cliente_telefono": forms.TextInput(
                attrs={"class": "form-control", "id": "id_cliente_telefono", "placeholder": "Teléfono / WhatsApp (opcional)"}
            ),
            "precio_acordado": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "id": "id_precio_acordado", "placeholder": "Presupuesto pactado ($)"}
            ),
            "notas": forms.Textarea(
                attrs={"class": "form-control", "id": "id_notas", "rows": 2, "placeholder": "Especificaciones técnicas o detalles del servicio (opcional)"}
            ),
        }

    def __init__(self, *args, user: Optional[Usuario] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["cliente"].required = False
        self.fields["cliente_telefono"].required = False
        self.fields["notas"].required = False

        self.fields["servicio"].queryset = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
        self.fields["cliente"].queryset = Cliente.objects.filter(activo=True).order_by("nombre")
        self.fields["profesional"].queryset = Usuario.objects.filter(is_active=True).order_by("nombre")

        # Horario actual por defecto
        if not self.initial.get("hora"):
            self.initial["hora"] = timezone.localtime().strftime("%H:%M")

        # Si el usuario es Empleada, fijar su profesional y no permitir modificarlo
        if user and not user.es_administradora:
            self.fields["profesional"].initial = user
            self.fields["profesional"].widget = forms.HiddenInput()
            self.fields["profesional"].required = False

    def clean_profesional(self) -> Usuario:
        if self.user and not self.user.es_administradora:
            return self.user
        prof = self.cleaned_data.get("profesional")
        if not prof:
            raise forms.ValidationError("Debe indicar la profesional a cargo.")
        return prof

    def clean_precio_acordado(self) -> Decimal:
        precio = self.cleaned_data.get("precio_acordado")
        if precio is None or precio < Decimal("0.00"):
            raise forms.ValidationError("El precio acordado debe ser mayor o igual a $0.")
        return precio


class FiltroLiquidacionForm(forms.Form):
    """Filtros para el reporte de liquidación de comisiones (RF 8.4)."""

    profesional = forms.ModelChoiceField(
        label="Peluquera / Profesional",
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre"),
        required=False,
        empty_label="— Todas las profesionales —",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha_desde = forms.DateField(
        label="Fecha Desde",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
        input_formats=["%Y-%m-%d"],
    )
    fecha_hasta = forms.DateField(
        label="Fecha Hasta",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
        input_formats=["%Y-%m-%d"],
    )
