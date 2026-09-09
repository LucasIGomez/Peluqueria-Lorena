"""
Peluquería Lorena — Formularios del módulo de Usuarios.

Define los formularios Django para login y para la gestión administrativa
(alta / edición) de usuarios. El alta de usuarios es exclusiva de la
Administradora; la contraseña de acceso de cada persona es su DNI.
"""
from __future__ import annotations

from django import forms

from .models import Usuario


def _validar_formato_dni(dni: str) -> str:
    """Normaliza y valida el formato del DNI (solo dígitos, 7 u 8)."""
    dni = (dni or "").strip().replace(".", "").replace(" ", "")
    if not dni.isdigit() or not (7 <= len(dni) <= 8):
        raise forms.ValidationError(
            "El DNI debe tener 7 u 8 dígitos, sin puntos ni espacios."
        )
    if len(set(dni)) == 1:
        # Rechaza DNI triviales como 00000000 (el de la cuenta inicial) o 11111111.
        raise forms.ValidationError("El DNI ingresado no es válido.")
    return dni


def _validar_nombre(nombre: str) -> str:
    """Valida que el nombre tenga contenido real (mín. 2 caracteres y una letra)."""
    nombre = (nombre or "").strip()
    if len(nombre) < 2 or not any(c.isalpha() for c in nombre):
        raise forms.ValidationError(
            "Ingresá un nombre válido (al menos 2 caracteres y una letra)."
        )
    return nombre


class LoginForm(forms.Form):
    """Formulario de inicio de sesión."""

    email = forms.EmailField(
        label="Correo Electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "ejemplo@peluquerialorena.com",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        max_length=128,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "••••••••",
            }
        ),
    )


class UsuarioAdminForm(forms.ModelForm):
    """Formulario para que la Administradora dé de alta un usuario."""

    dni = forms.CharField(
        label="DNI",
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej: 40123456",
                "inputmode": "numeric",
            }
        ),
        help_text="Sin puntos. Será la contraseña con la que la persona inicia sesión.",
    )

    class Meta:
        model = Usuario
        fields = ["nombre", "email", "rol", "dni"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "rol": forms.Select(attrs={"class": "form-select", "id": "id_rol_select"}),
        }

    def clean_nombre(self) -> str:
        return _validar_nombre(self.cleaned_data.get("nombre"))

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo electrónico.")
        return email

    def clean_dni(self) -> str:
        dni = _validar_formato_dni(self.cleaned_data.get("dni"))
        if Usuario.objects.filter(dni=dni).exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este DNI.")
        return dni


class UsuarioEditForm(forms.ModelForm):
    """Formulario para que la Administradora edite los datos de un usuario."""

    dni = forms.CharField(
        label="DNI",
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej: 40123456",
                "inputmode": "numeric",
            }
        ),
        help_text="Si lo cambiás, también cambia la contraseña de acceso de la persona.",
    )

    class Meta:
        model = Usuario
        fields = ["nombre", "email", "rol", "dni", "is_active"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "rol": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_nombre(self) -> str:
        return _validar_nombre(self.cleaned_data.get("nombre"))

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if (
            Usuario.objects.filter(email=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("Ya existe otro usuario con este correo electrónico.")
        return email

    def clean_dni(self) -> str:
        dni = _validar_formato_dni(self.cleaned_data.get("dni"))
        if (
            Usuario.objects.filter(dni=dni)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("Ya existe otro usuario registrado con este DNI.")
        return dni

    def clean(self) -> dict:
        """Impide dejar el sistema sin ninguna administradora activa."""
        cleaned = super().clean()
        if not self.instance.pk:
            return cleaned

        era_admin_activa = (
            self.instance.rol == Usuario.Rol.ADMINISTRADORA and self.instance.is_active
        )
        if era_admin_activa:
            sigue_admin_activa = (
                cleaned.get("rol") == Usuario.Rol.ADMINISTRADORA
                and cleaned.get("is_active", False)
            )
            if not sigue_admin_activa:
                hay_otra = (
                    Usuario.objects.filter(
                        rol=Usuario.Rol.ADMINISTRADORA, is_active=True
                    )
                    .exclude(pk=self.instance.pk)
                    .exists()
                )
                if not hay_otra:
                    raise forms.ValidationError(
                        "No podés dejar el sistema sin ninguna administradora activa. "
                        "Designá otra administradora antes de cambiar el rol o "
                        "desactivar esta cuenta."
                    )
        return cleaned
