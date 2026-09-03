"""
Peluquería Lorena — Formularios del módulo de Usuarios.

Define los formularios Django para login, registro con validación de PIN
y gestión administrativa (CRUD) de usuarios.
"""
from __future__ import annotations

from typing import Any
from django import forms
from django.conf import settings
from .models import Usuario


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
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "••••••••",
            }
        ),
    )


class RegistroForm(forms.Form):
    """Formulario público para registro de nuevos usuarios."""

    nombre = forms.CharField(
        label="Nombre Completo",
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ej: Lorena Gómez",
            }
        ),
    )
    email = forms.EmailField(
        label="Correo Electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "correo@peluquerialorena.com",
            }
        ),
    )
    rol = forms.ChoiceField(
        label="Rol en el Sistema",
        choices=Usuario.Rol.choices,
        initial=Usuario.Rol.EMPLEADA,
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "id_rol_select",
            }
        ),
    )
    admin_pin = forms.CharField(
        label="PIN de Administradora (Solo si el rol es Administradora)",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "PIN de seguridad",
                "id": "id_admin_pin_input",
            }
        ),
        help_text="Requerido únicamente para activar cuenta de Administradora (por defecto: 1234).",
    )
    password = forms.CharField(
        label="Contraseña",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Mínimo 8 caracteres",
            }
        ),
    )
    confirm_password = forms.CharField(
        label="Confirmar Contraseña",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Repetí tu contraseña",
            }
        ),
    )

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este correo electrónico.")
        return email

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        rol = cleaned_data.get("rol")
        admin_pin = cleaned_data.get("admin_pin")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Las contraseñas no coinciden.")

        if rol == Usuario.Rol.ADMINISTRADORA:
            expected_pin = getattr(settings, "ADMIN_REGISTRATION_PIN", "1234")
            if not admin_pin or str(admin_pin).strip() != str(expected_pin).strip():
                self.add_error("admin_pin", "El PIN de seguridad de Administradora es incorrecto.")

        return cleaned_data


class UsuarioAdminForm(forms.ModelForm):
    """Formulario para que la Administradora cree usuarios desde el panel de gestión."""

    password = forms.CharField(
        label="Contraseña Inicial",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Mínimo 8 caracteres",
            }
        ),
    )
    admin_pin = forms.CharField(
        label="PIN de Administradora",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "PIN (si el rol es Administradora)",
            }
        ),
    )

    class Meta:
        model = Usuario
        fields = ["nombre", "email", "rol"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "rol": forms.Select(attrs={"class": "form-select", "id": "id_rol_select"}),
        }

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con este correo electrónico.")
        return email

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        rol = cleaned_data.get("rol")
        admin_pin = cleaned_data.get("admin_pin")

        if rol == Usuario.Rol.ADMINISTRADORA:
            expected_pin = getattr(settings, "ADMIN_REGISTRATION_PIN", "1234")
            if not admin_pin or str(admin_pin).strip() != str(expected_pin).strip():
                self.add_error("admin_pin", "El PIN de seguridad de Administradora es incorrecto.")

        return cleaned_data


class UsuarioEditForm(forms.ModelForm):
    """Formulario para que la Administradora edite los datos de un usuario."""

    class Meta:
        model = Usuario
        fields = ["nombre", "email", "rol", "is_active"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "rol": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
