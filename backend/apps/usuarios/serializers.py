"""
Peluquería Lorena — Serializers del módulo de Usuarios.

Define la serialización/deserialización de datos entre
las vistas (API) y los modelos de dominio.
"""
from __future__ import annotations

from typing import Any, Dict

from rest_framework import serializers

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer de lectura para el modelo Usuario.

    Excluye la contraseña y campos internos de Django.
    """

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "nombre",
            "rol",
            "is_active",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "date_joined",
        ]


class UsuarioCreateSerializer(serializers.ModelSerializer):
    """
    Serializer de escritura para crear usuarios.

    Recibe la contraseña en texto plano y valida el PIN de Administradora si aplica.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    admin_pin = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
        help_text="PIN requerido únicamente para registrar usuario con rol ADMINISTRADORA.",
    )

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "nombre",
            "password",
            "rol",
            "admin_pin",
        ]       
        read_only_fields = ["id"]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Valida que si el rol es Administradora se provea el PIN correcto."""
        from django.conf import settings

        rol = attrs.get("rol", Usuario.Rol.EMPLEADA)
        admin_pin = attrs.get("admin_pin")

        if rol == Usuario.Rol.ADMINISTRADORA:
            expected_pin = getattr(settings, "ADMIN_REGISTRATION_PIN", "1234")
            if not admin_pin or str(admin_pin).strip() != str(expected_pin).strip():
                raise serializers.ValidationError(
                    {"admin_pin": "El PIN de seguridad de Administradora es incorrecto."}
                )
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Usuario:
        """Crea el usuario usando el service para hashear la contraseña."""
        from .services import UsuarioService

        return UsuarioService.crear_usuario(**validated_data)


class RegistroSerializer(serializers.Serializer):
    """
    Serializer para registro público de nuevos usuarios.
    """

    nombre = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, style={"input_type": "password"})
    confirm_password = serializers.CharField(min_length=8, style={"input_type": "password"})
    rol = serializers.ChoiceField(choices=Usuario.Rol.choices, default=Usuario.Rol.EMPLEADA)
    admin_pin = serializers.CharField(required=False, allow_blank=True, style={"input_type": "password"})

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        from django.conf import settings

        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Las contraseñas no coinciden."})

        if Usuario.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "Ya existe un usuario registrado con este correo electrónico."})

        if attrs["rol"] == Usuario.Rol.ADMINISTRADORA:
            expected_pin = getattr(settings, "ADMIN_REGISTRATION_PIN", "1234")
            admin_pin = attrs.get("admin_pin")
            if not admin_pin or str(admin_pin).strip() != str(expected_pin).strip():
                raise serializers.ValidationError(
                    {"admin_pin": "El PIN de seguridad de Administradora es incorrecto."}
                )

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Usuario:
        from .services import UsuarioService

        validated_data.pop("confirm_password", None)
        return UsuarioService.crear_usuario(**validated_data)



class UsuarioUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualización parcial de usuarios.

    No permite modificar la contraseña por esta vía.
    """

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "nombre",
            "rol",
        ]
        read_only_fields = ["id"]


class PerfilUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para que el usuario edite su propio perfil.

    No permite cambiar el rol ni el email.
    """

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "nombre",
            "rol",
        ]
        read_only_fields = ["id", "email", "rol"]


class CambiarPasswordSerializer(serializers.Serializer):
    """Serializer para cambio de contraseña autenticado."""

    old_password = serializers.CharField(
        required=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        required=True,
        min_length=8,
        style={"input_type": "password"},
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer para solicitar reset de contraseña."""

    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer para confirmar reset de contraseña con token."""

    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        min_length=8,
        style={"input_type": "password"},
    )
