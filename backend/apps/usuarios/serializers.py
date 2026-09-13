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
    Serializer de escritura para crear usuarios (solo Administradora).

    El DNI se guarda como dato y además es la contraseña de acceso.
    """

    dni = serializers.CharField(write_only=True, min_length=7, max_length=8)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "email",
            "nombre",
            "rol",
            "dni",
        ]
        read_only_fields = ["id"]

    def validate_nombre(self, value: str) -> str:
        value = (value or "").strip()
        if len(value) < 2 or not any(c.isalpha() for c in value):
            raise serializers.ValidationError(
                "Ingresá un nombre válido (al menos 2 caracteres y una letra)."
            )
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo electrónico.")
        return value

    def validate_dni(self, value: str) -> str:
        value = value.strip().replace(".", "").replace(" ", "")
        if not value.isdigit() or not (7 <= len(value) <= 8):
            raise serializers.ValidationError("El DNI debe tener 7 u 8 dígitos.")
        if len(set(value)) == 1:
            raise serializers.ValidationError("El DNI ingresado no es válido.")
        if Usuario.objects.filter(dni=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este DNI.")
        return value

    def create(self, validated_data: Dict[str, Any]) -> Usuario:
        """Crea el usuario usando el service (el DNI es la contraseña)."""
        from .services import UsuarioService

        dni = validated_data["dni"]
        return UsuarioService.crear_usuario(
            nombre=validated_data["nombre"],
            email=validated_data["email"],
            password=dni,
            rol=validated_data.get("rol", Usuario.Rol.EMPLEADA),
            dni=dni,
        )


class UsuarioUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualización parcial de usuarios.

    No permite modificar la contraseña ni el DNI por esta vía.
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

    def validate_nombre(self, value: str) -> str:
        value = (value or "").strip()
        if len(value) < 2 or not any(c.isalpha() for c in value):
            raise serializers.ValidationError(
                "Ingresá un nombre válido (al menos 2 caracteres y una letra)."
            )
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        qs = Usuario.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe otro usuario con este correo electrónico.")
        return value

    def validate_rol(self, value: str) -> str:
        # No permitir degradar a la última administradora activa.
        instancia = self.instance
        if (
            instancia
            and instancia.rol == Usuario.Rol.ADMINISTRADORA
            and instancia.is_active
            and value != Usuario.Rol.ADMINISTRADORA
        ):
            hay_otra = (
                Usuario.objects.filter(rol=Usuario.Rol.ADMINISTRADORA, is_active=True)
                .exclude(pk=instancia.pk)
                .exists()
            )
            if not hay_otra:
                raise serializers.ValidationError(
                    "No podés dejar el sistema sin ninguna administradora activa."
                )
        return value


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