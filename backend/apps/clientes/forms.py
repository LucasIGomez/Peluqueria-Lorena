"""
Peluquería Lorena — Formularios del módulo de Clientes.

Define formularios Django para:
- Alta y edición de clientas.
- Creación de fichas de tratamiento multisesión.
- Carga de evolución y diagnóstico técnico sesión a sesión.
"""
from __future__ import annotations

from django import forms
from .models import Cliente, EvolucionSesion, TratamientoProgreso


class ClienteForm(forms.ModelForm):
    """Formulario para registrar o editar datos de una clienta."""

    fecha_nacimiento = forms.DateField(
        label="Fecha de Nacimiento",
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
        help_text="Útil para saludos personalizados, regalos o descuentos por cumpleaños.",
    )

    class Meta:
        model = Cliente
        fields = [
            "nombre",
            "telefono",
            "email",
            "fecha_nacimiento",
            "notas_alergias",
            "preferencias",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Romina Fernández"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: 1123456789 (WhatsApp)"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "romina@ejemplo.com"}),
            "notas_alergias": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Alergias a persulfatos, amoníaco, cuero cabelludo sensible, etc.",
                }
            ),
            "preferencias": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Tono preferido, tipo de peinado o productos favoritos.",
                }
            ),
        }


class TratamientoProgresoForm(forms.ModelForm):
    """Formulario para iniciar una ficha de seguimiento de proceso químico por etapas."""

    class Meta:
        model = TratamientoProgreso
        fields = [
            "titulo_tratamiento",
            "servicio_nombre",
            "total_sesiones_estimadas",
            "notas_objetivo",
        ]
        widgets = {
            "titulo_tratamiento": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej: Balayage Rubio Vainilla en 2 etapas"}
            ),
            "servicio_nombre": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej: Mechas Balayage / Alisado"}
            ),
            "total_sesiones_estimadas": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "notas_objetivo": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Aclarar a altura 8 sin dañar la elasticidad de medios a puntas.",
                }
            ),
        }


class EvolucionSesionForm(forms.ModelForm):
    """Formulario técnico para registrar la evolución de una sesión."""

    proxima_cita_recomendada = forms.DateField(
        label="Próxima Cita Sugerida",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    class Meta:
        model = EvolucionSesion
        fields = [
            "numero_sesion",
            "diagnostico_fibra",
            "formula_quimica_utilizada",
            "tiempo_exposicion_minutos",
            "resultado_obtenido",
            "proxima_cita_recomendada",
            "indicaciones_hogar",
        ]
        widgets = {
            "numero_sesion": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "diagnostico_fibra": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Base natural 4, porosidad media, buena elasticidad.",
                }
            ),
            "formula_quimica_utilizada": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "30g Polvo Decolorante + 60ml Ox 20 vol + Protector plex.",
                }
            ),
            "tiempo_exposicion_minutos": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "resultado_obtenido": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Aclaración uniforme a altura 7. Fibra íntegra.",
                }
            ),
            "indicaciones_hogar": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Usar mascarilla ácida, evitar agua muy caliente y secador a máxima temperatura.",
                }
            ),
        }
