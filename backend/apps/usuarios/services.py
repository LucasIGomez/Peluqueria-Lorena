"""
Peluquería Lorena — Capa de servicios del módulo de Usuarios.

Encapsula la lógica de negocio separada de las vistas (views).
Todos los métodos son estáticos para facilitar el testing.
"""
from __future__ import annotations

import secrets
from typing import Any, Optional

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import QuerySet

from .models import PasswordResetToken, Usuario


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
        admin_pin: Optional[str] = None,
        requiere_pin: bool = False,
        **extra_fields: Any,
    ) -> Usuario:
        """
        Crea un nuevo usuario con contraseña hasheada y validación de PIN para Administradora.

        Args:
            nombre: Nombre completo del usuario.
            email: Correo electrónico único.
            password: Contraseña en texto plano.
            rol: Rol del usuario (EMPLEADA o ADMINISTRADORA).
            admin_pin: PIN de seguridad requerido si el rol es ADMINISTRADORA.
            requiere_pin: Si es True, exige obligatoriamente el PIN para rol ADMINISTRADORA.
            **extra_fields: Campos adicionales.

        Returns:
            Instancia de Usuario persistida.

        Raises:
            ValueError: Si el PIN para Administradora es inválido o no se proporciona email.
        """
        if admin_pin is None:
            admin_pin = extra_fields.pop("admin_pin", extra_fields.pop("adminPin", None))

        # Si el rol es Administradora, validar el PIN si se requiere o si fue provisto
        if rol == Usuario.Rol.ADMINISTRADORA:
            expected_pin = getattr(settings, "ADMIN_REGISTRATION_PIN", "1234")
            if requiere_pin or admin_pin is not None:
                if not admin_pin or str(admin_pin).strip() != str(expected_pin).strip():
                    raise ValueError("El PIN de seguridad para registrar Administradora es incorrecto.")
            extra_fields.setdefault("is_staff", True)

        return Usuario.objects.create_user(
            email=email,
            nombre=nombre,
            password=password,
            rol=rol,
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
        campos_actualizables = ["nombre", "email", "rol"]
        update_fields: list[str] = []

        for campo, valor in campos.items():
            if campo in campos_actualizables and valor is not None:
                setattr(usuario, campo, valor)
                update_fields.append(campo)

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

    # ── Reset de Contraseña ──

    @staticmethod
    def solicitar_reset_password(email: str) -> None:
        """
        Genera un token de reset y envía un correo al usuario.

        Si el email no existe, no hace nada (para no revelar
        la existencia de cuentas).

        Args:
            email: Correo electrónico del usuario.
        """
        try:
            usuario = Usuario.objects.get(email=email, is_active=True)
        except Usuario.DoesNotExist:
            return

        # Generar token seguro
        token_value = secrets.token_urlsafe(32)

        # Invalidar tokens anteriores
        PasswordResetToken.objects.filter(
            usuario=usuario, used=False
        ).update(used=True)

        # Crear nuevo token
        PasswordResetToken.objects.create(
            usuario=usuario,
            token=token_value,
        )

        # Enviar correo con el token
        reset_url = f"token={token_value}"
        send_mail(
            subject="Recuperación de contraseña — Peluquería Lorena",
            message=(
                f"Hola {usuario.nombre},\n\n"
                f"Solicitaste restablecer tu contraseña.\n"
                f"Usá el siguiente enlace para establecer una nueva contraseña:\n\n"
                f"https://peluquerialorena.com/reset-password?{reset_url}\n\n"
                f"Si no solicitaste este cambio, ignorá este correo.\n\n"
                f"— Peluquería Lorena"
            ),
            from_email=getattr(
                settings, "DEFAULT_FROM_EMAIL", "noreply@peluquerialorena.com"
            ),
            recipient_list=[usuario.email],
            fail_silently=False,
        )

    @staticmethod
    def confirmar_reset_password(
        token: str,
        new_password: str,
    ) -> bool:
        """
        Confirma el reset de contraseña con un token válido.

        Args:
            token: Token de recuperación recibido por correo.
            new_password: Nueva contraseña.

        Returns:
            True si el reset fue exitoso, False si el token es
            inválido o expirado.
        """
        try:
            reset_token = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            return False

        if not reset_token.is_valid():
            return False

        # Cambiar contraseña
        usuario = reset_token.usuario
        usuario.set_password(new_password)
        usuario.save(update_fields=["password"])

        # Marcar token como usado
        reset_token.used = True
        reset_token.save(update_fields=["used"])

        return True
