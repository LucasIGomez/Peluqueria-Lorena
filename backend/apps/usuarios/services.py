"""
Peluquería Lorena — Capa de servicios del módulo de Usuarios.

Encapsula la lógica de negocio separada de las vistas (views).
Todos los métodos son estáticos para facilitar el testing.
"""
from __future__ import annotations

from typing import Any, Optional

from django.db.models import QuerySet

from .models import Usuario


class UsuarioService:
    """
    Servicio de negocio para operaciones sobre el modelo Usuario.

    Centraliza la lógica de creación, actualización, eliminación
    y recuperación de credenciales.
    """

    # ── Creación ──

    @staticmethod
    def crear_usuario(
        nombre: str,
        email: str,
        password: str,
        rol: str = Usuario.Rol.EMPLEADA,
        dni: Optional[str] = None,
        **extra_fields: Any,
    ) -> Usuario:
        """
        Crea un nuevo usuario con contraseña hasheada.

        La creación de usuarios es exclusiva de la Administradora (se controla
        en la vista / permiso). La contraseña de acceso es el DNI de la persona.

        Args:
            nombre: Nombre completo del usuario.
            email: Correo electrónico único.
            password: Contraseña en texto plano (normalmente el DNI).
            rol: Rol del usuario (EMPLEADA o ADMINISTRADORA).
            dni: DNI de la persona; se guarda como dato y se usa como contraseña.
            **extra_fields: Campos adicionales.

        Returns:
            Instancia de Usuario persistida.

        Raises:
            ValueError: Si no se proporciona email.
        """
        if rol == Usuario.Rol.ADMINISTRADORA:
            extra_fields.setdefault("is_staff", True)

        return Usuario.objects.create_user(
            email=email,
            nombre=nombre,
            password=password,
            rol=rol,
            dni=dni,
            **extra_fields,
        )

    # ── Lectura ──

    @staticmethod
    def listar_usuarios(**filtros: Any) -> QuerySet[Usuario]:
        """
        Lista usuarios con filtros opcionales.

        Args:
            **filtros: Filtros de QuerySet (ej: rol='EMPLEADA').

        Returns:
            QuerySet de usuarios filtrado.
        """
        return Usuario.objects.filter(is_active=True, **filtros)

    @staticmethod
    def obtener_por_id(usuario_id: int) -> Optional[Usuario]:
        """
        Obtiene un usuario por su ID.

        Args:
            usuario_id: Identificador del usuario.

        Returns:
            Instancia de Usuario o None si no existe.
        """
        try:
            return Usuario.objects.get(pk=usuario_id, is_active=True)
        except Usuario.DoesNotExist:
            return None

    # ── Actualización ──

    @staticmethod
    def actualizar_usuario(
        usuario: Usuario,
        **campos: Any,
    ) -> Usuario:
        """
        Actualiza los campos de un usuario existente.

        Args:
            usuario: Instancia de Usuario a actualizar.
            **campos: Campos a modificar (nombre, email, rol, etc.).

        Returns:
            Instancia de Usuario actualizada.
        """
        campos_actualizables = ["nombre", "email", "rol", "dni"]
        update_fields: list[str] = []

        for campo, valor in campos.items():
            if campo in campos_actualizables and valor is not None:
                setattr(usuario, campo, valor)
                update_fields.append(campo)

        # Si cambió el DNI, actualizar también la contraseña (el DNI es la clave).
        if "dni" in update_fields and usuario.dni:
            usuario.set_password(usuario.dni)
            update_fields.append("password")

        # Si se cambia a administradora, activar is_staff
        if "rol" in update_fields:
            if usuario.rol == Usuario.Rol.ADMINISTRADORA:
                usuario.is_staff = True
            else:
                usuario.is_staff = False
            update_fields.append("is_staff")

        if update_fields:
            usuario.save(update_fields=update_fields)

        return usuario

    # ── Eliminación (Soft Delete) ──

    @staticmethod
    def eliminar_usuario(usuario: Usuario) -> None:
        """
        Desactiva un usuario (soft delete).

        No elimina el registro de la base de datos para preservar
        la integridad referencial con turnos, cobros, etc.

        Args:
            usuario: Instancia de Usuario a desactivar.
        """
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])

    # ── Cambio de Contraseña ──

    @staticmethod
    def cambiar_password(
        usuario: Usuario,
        old_password: str,
        new_password: str,
    ) -> bool:
        """
        Cambia la contraseña del usuario validando la actual.

        Args:
            usuario: Instancia de Usuario.
            old_password: Contraseña actual para verificación.
            new_password: Nueva contraseña.

        Returns:
            True si el cambio fue exitoso, False si la contraseña
            actual es incorrecta.
        """
        if not usuario.check_password(old_password):
            return False
        usuario.set_password(new_password)
        usuario.save(update_fields=["password"])
        return True

