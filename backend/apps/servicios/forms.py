"""
Peluquería Lorena — Formularios del módulo de Servicios.

Define formularios Django para:
- Administración de servicios del catálogo oficial.
- Registro de atención diaria con personalización de precio y tiempo por clienta.
- Ficha de consentimiento informado legal/técnico (decoloración y alisado).
"""
from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.usuarios.models import Usuario
from .models import ConsentimientoInformado, Servicio, ServicioRealizado


class ServicioForm(forms.ModelForm):
    """Formulario para crear o editar un servicio en el catálogo."""

    class Meta:
        model = Servicio
        fields = [
            "nombre",
            "categoria",
            "precio_base",
            "duracion_estimada_minutos",
            "requiere_consentimiento",
            "descripcion",
            "activo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Balayage Rubio Dorado"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "precio_base": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "duracion_estimada_minutos": forms.NumberInput(attrs={"class": "form-control", "min": 5}),
            "requiere_consentimiento": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ServicioRealizadoForm(forms.ModelForm):
    """
    Formulario para asentar un servicio brindado por día y horario,
    permitiendo ajustar el precio y duración en minutos para la clienta.
    """

    fecha = forms.DateField(
        label="Fecha de Atención",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
        input_formats=["%Y-%m-%d"],
    )
    hora = forms.TimeField(
        label="Horario de Inicio",
        widget=forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
    )

    class Meta:
        model = ServicioRealizado
        fields = [
            "servicio",
            "cliente",
            "cliente_nombre",
            "cliente_telefono",
            "profesional",
            "fecha",
            "hora",
            "precio_acordado",
            "duracion_minutos",
            "estado",
            "consentimiento",
            "notas",
        ]
        widgets = {
            "servicio": forms.Select(attrs={"class": "form-select", "id": "id_servicio_select"}),
            "cliente": forms.Select(attrs={"class": "form-select", "id": "id_cliente_select"}),
            "cliente_nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre de la clienta"}),
            "cliente_telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "WhatsApp / Teléfono"}),
            "profesional": forms.Select(attrs={"class": "form-select"}),
            "precio_acordado": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "id": "id_precio_acordado"}),
            "duracion_minutos": forms.NumberInput(attrs={"class": "form-control", "min": 5, "id": "id_duracion_minutos"}),
            "estado": forms.Select(attrs={"class": "form-select"}),
            "consentimiento": forms.Select(attrs={"class": "form-select"}),
            "notas": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Largo de cabello, tono base o detalles específicos."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].required = False
        self.fields["consentimiento"].required = False
        self.fields["cliente"].queryset = Cliente.objects.filter(activo=True).order_by("nombre")
        self.fields["profesional"].queryset = Usuario.objects.filter(is_active=True).order_by("nombre")
        self.fields["servicio"].queryset = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
        self.fields["fecha"].widget.attrs["max"] = timezone.localdate().isoformat()

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("No se puede registrar una atención en una fecha futura.")
        if fecha:
            from apps.pagos.services import CajaService

            if CajaService.caja_esta_cerrada(fecha):
                raise forms.ValidationError(
                    f"La caja del {fecha.strftime('%d/%m/%Y')} ya está cerrada. "
                    "Para registrar una atención de ese día hay que reabrir la caja primero."
                )
        return fecha


class ConsentimientoInformadoForm(forms.ModelForm):
    """
    Formulario legal y técnico de consentimiento informado para decoloración y alisado.
    """

    class Meta:
        model = ConsentimientoInformado
        fields = [
            "cliente",
            "cliente_nombre",
            "cliente_telefono",
            "cliente_dni",
            "tipo_procedimiento",
            "profesional",
            # Factores ajenos
            "ha_usado_henna_o_sales_metalicas",
            "tiene_alisados_o_permanentes_previos",
            "detalle_quimicos_previos",
            "tiene_decoloraciones_previas",
            "alergias_o_sensibilidad_cuero_cabelludo",
            "detalle_alergias",
            "embarazo_o_lactancia",
            "medicacion_o_tratamiento_medico",
            # Diagnóstico
            "prueba_mecha_realizada",
            "resultado_prueba_mecha",
            "elasticidad_cabello",
            "porosidad_cabello",
            # Conformidad
            "acepta_terminos",
            "firma_digital",
            "observaciones",
        ]
        widgets = {
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "cliente_nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre completo"}),
            "cliente_telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Teléfono de contacto"}),
            "cliente_dni": forms.TextInput(attrs={"class": "form-control", "placeholder": "DNI / Documento"}),
            "tipo_procedimiento": forms.Select(attrs={"class": "form-select"}),
            "profesional": forms.Select(attrs={"class": "form-select"}),
            # Checkboxes
            "ha_usado_henna_o_sales_metalicas": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tiene_alisados_o_permanentes_previos": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "detalle_quimicos_previos": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Marcas, fechas o tipos de productos previos."}),
            "tiene_decoloraciones_previas": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "alergias_o_sensibilidad_cuero_cabelludo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "detalle_alergias": forms.TextInput(attrs={"class": "form-control", "placeholder": "Persulfato, amoníaco, etc."}),
            "embarazo_o_lactancia": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "medicacion_o_tratamiento_medico": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            # Diagnóstico
            "prueba_mecha_realizada": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "resultado_prueba_mecha": forms.Select(attrs={"class": "form-select"}),
            "elasticidad_cabello": forms.Select(attrs={"class": "form-select"}),
            "porosidad_cabello": forms.Select(attrs={"class": "form-select"}),
            "acepta_terminos": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "firma_digital": forms.TextInput(attrs={"class": "form-control", "placeholder": "Aclaración o conformidad expresa de la clienta"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].required = False
        self.fields["cliente"].queryset = Cliente.objects.filter(activo=True).order_by("nombre")
        self.fields["profesional"].queryset = Usuario.objects.filter(is_active=True).order_by("nombre")
