"""
Peluquería Lorena — Formularios del módulo de Turnos (Agenda).
"""
from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.servicios.models import Servicio
from apps.usuarios.models import Usuario
from .models import Turno
from .services import TurnoService


class TurnoForm(forms.ModelForm):
    """Formulario para agendar o editar un turno."""

    fecha = forms.DateField(
        label="Fecha del Turno",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
        input_formats=["%Y-%m-%d"],
    )
    hora = forms.TimeField(
        label="Hora del Turno",
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )

    class Meta:
        model = Turno
        fields = [
            "cliente",
            "cliente_nombre",
            "cliente_telefono",
            "servicio",
            "profesional",
            "fecha",
            "hora",
            "duracion_minutos",
            "notas",
        ]
        widgets = {
            "cliente": forms.Select(attrs={"class": "form-select", "id": "id_cliente"}),
            "cliente_nombre": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nombre y apellido", "id": "id_cliente_nombre"}
            ),
            "cliente_telefono": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "WhatsApp / Teléfono"}
            ),
            "servicio": forms.Select(attrs={"class": "form-select", "id": "id_servicio"}),
            "profesional": forms.Select(attrs={"class": "form-select"}),
            "duracion_minutos": forms.NumberInput(attrs={"class": "form-control", "min": 5, "id": "id_duracion"}),
            "notas": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].required = False
        self.fields["cliente"].queryset = Cliente.objects.filter(activo=True).order_by("nombre")
        self.fields["profesional"].required = False
        self.fields["profesional"].queryset = Usuario.objects.filter(is_active=True).order_by("nombre")
        self.fields["servicio"].queryset = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
        self.fields["duracion_minutos"].required = False
        self.fields["fecha"].widget.attrs["min"] = timezone.localdate().isoformat()

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if fecha and fecha < timezone.localdate():
            raise forms.ValidationError("No se puede agendar un turno en una fecha pasada.")
        return fecha

    def clean(self):
        datos = super().clean()
        servicio = datos.get("servicio")
        if not datos.get("duracion_minutos") and servicio:
            datos["duracion_minutos"] = servicio.duracion_estimada_minutos

        profesional = datos.get("profesional")
        fecha = datos.get("fecha")
        hora = datos.get("hora")
        duracion = datos.get("duracion_minutos")
        if profesional and fecha and hora and duracion:
            excluir_pk = self.instance.pk if self.instance and self.instance.pk else None
            if TurnoService.hay_solapamiento(profesional, fecha, hora, duracion, excluir_pk=excluir_pk):
                self.add_error(
                    "profesional",
                    f"{profesional.nombre} ya tiene un turno asignado en ese horario.",
                )
        return datos
