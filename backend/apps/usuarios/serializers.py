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

    Recibe la contraseña en texto plano y la hashea en el método create().
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "nombre",
            "password",
            "rol",
        ]       
        read_only_fields = ["id"]

    def create(self, validated_data: Dict[str, Any]) -> Usuario:
        """Crea el usuario usando el service para hashear la contraseña."""
        from .services import UsuarioService

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
