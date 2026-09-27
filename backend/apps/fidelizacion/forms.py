"""
Peluquería Lorena — Formularios del módulo de Beneficios y Fidelización (RF10).

Define formularios para:
- Configuración del motor de reglas por la administradora (RF 10.1).
- Filtros del panel de auditoría de beneficios otorgados.
- Canje manual de cupones en caja.
"""
from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.servicios.models import Servicio
from .models import BeneficioOtorgado, ReglaBeneficio


CLASE_CONTROL = {"class": "form-control"}
CLASE_SELECT = {"class": "form-select"}


class ReglaBeneficioForm(forms.ModelForm):
    """Alta y edición de reglas del motor de beneficios (RF 10.1)."""

    class Meta:
        model = ReglaBeneficio
        fields = [
            "nombre", "tipo", "descripcion", "activo",
            "min_visitas", "min_monto", "periodo_dias", "ventana_dias",
            "tipo_recompensa", "valor", "servicio_bonificado",
            "plantilla_mensaje", "dias_validez",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={**CLASE_CONTROL, "placeholder": "Ej: Cumpleaños 15% OFF"}),
            "tipo": forms.Select(attrs=CLASE_SELECT),
            "descripcion": forms.TextInput(attrs={**CLASE_CONTROL, "placeholder": "Notas internas (opcional)"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "min_visitas": forms.NumberInput(attrs={**CLASE_CONTROL, "min": "0"}),
            "min_monto": forms.NumberInput(attrs={**CLASE_CONTROL, "step": "0.01", "min": "0"}),
            "periodo_dias": forms.NumberInput(attrs={**CLASE_CONTROL, "min": "0", "placeholder": "0 = historial total"}),
            "ventana_dias": forms.NumberInput(attrs={**CLASE_CONTROL, "min": "0", "max": "30"}),
            "tipo_recompensa": forms.Select(attrs=CLASE_SELECT),
            "valor": forms.NumberInput(attrs={**CLASE_CONTROL, "step": "0.01", "min": "0"}),
            "servicio_bonificado": forms.Select(attrs=CLASE_SELECT),
            "plantilla_mensaje": forms.Textarea(attrs={**CLASE_CONTROL, "rows": 3}),
            "dias_validez": forms.NumberInput(attrs={**CLASE_CONTROL, "min": "1", "max": "365"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servicio_bonificado"].queryset = Servicio.objects.filter(activo=True).order_by("nombre")
        self.fields["servicio_bonificado"].required = False
        self.fields["descripcion"].required = False

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        tipo_recompensa = datos.get("tipo_recompensa")
        valor = datos.get("valor") or Decimal("0.00")
        servicio = datos.get("servicio_bonificado")
        min_visitas = datos.get("min_visitas") or 0
        min_monto = datos.get("min_monto") or Decimal("0.00")

        if tipo == ReglaBeneficio.Tipo.REGULARIDAD and not min_visitas and min_monto <= Decimal("0.00"):
            raise forms.ValidationError(
                "En reglas de REGULARIDAD debe exigir al menos visitas mínimas o un monto mínimo."
            )
        if tipo_recompensa == ReglaBeneficio.TipoRecompensa.PORCENTAJE and not (
            Decimal("0") < valor <= Decimal("100")
        ):
            raise forms.ValidationError("El porcentaje de descuento debe estar entre 0 y 100.")
        if tipo_recompensa == ReglaBeneficio.TipoRecompensa.MONTO_FIJO and valor <= Decimal("0"):
            raise forms.ValidationError("El monto fijo debe ser mayor a $0.")
        if tipo_recompensa == ReglaBeneficio.TipoRecompensa.SERVICIO and servicio is None:
            raise forms.ValidationError("Debe elegir el servicio bonificado para recompensas de tipo SERVICIO.")

        plantilla = (datos.get("plantilla_mensaje") or "").strip()
        if "{nombre_cliente}" not in plantilla:
            raise forms.ValidationError(
                "La plantilla debe incluir al menos la variable {nombre_cliente}."
            )
        datos["plantilla_mensaje"] = plantilla
        return datos

    def clean_valor(self) -> Decimal:
        valor = self.cleaned_data.get("valor")
        if valor is None or valor < Decimal("0.00"):
            raise forms.ValidationError("El valor debe ser mayor o igual a 0.")
        return valor

    def clean_dias_validez(self) -> int:
        dias = self.cleaned_data.get("dias_validez")
        if dias is None or dias < 1:
            raise forms.ValidationError("La vigencia del cupón debe ser de al menos 1 día.")
        if dias > 365:
            raise forms.ValidationError("La vigencia del cupón no puede superar 365 días.")
        return dias

    def clean_ventana_dias(self) -> int:
        dias = self.cleaned_data.get("ventana_dias")
        if dias is None or dias < 0:
            raise forms.ValidationError("La ventana de aviso no puede ser negativa.")
        return dias

    def clean_periodo_dias(self) -> int:
        dias = self.cleaned_data.get("periodo_dias")
        if dias is None or dias < 0:
            raise forms.ValidationError("El período de evaluación no puede ser negativo (0 = historial total).")
        return dias


class FiltroBeneficiosForm(forms.Form):
    """Filtros del panel de auditoría de beneficios otorgados."""

    busqueda = forms.CharField(
        label="Buscar",
        required=False,
        widget=forms.TextInput(attrs={**CLASE_CONTROL, "placeholder": "Clienta o código de cupón..."}),
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        required=False,
        choices=[("", "— Todos los tipos —")] + list(ReglaBeneficio.Tipo.choices),
        widget=forms.Select(attrs=CLASE_SELECT),
    )
    estado = forms.ChoiceField(
        label="Estado",
        required=False,
        choices=[("", "— Todos los estados —")] + list(BeneficioOtorgado.Estado.choices),
        widget=forms.Select(attrs=CLASE_SELECT),
    )


class CanjeBeneficioForm(forms.Form):
    """Canje manual de un cupón en caja."""

    observaciones = forms.CharField(
        label="Observaciones del canje (opcional)",
        required=False,
        widget=forms.Textarea(attrs={**CLASE_CONTROL, "rows": 2, "placeholder": "Ej: aplicado sobre corte + color..."}),
    )
