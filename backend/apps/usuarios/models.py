"""
Peluquería Lorena — Modelos del módulo de Usuarios.

Implementa el modelo de dominio con herencia (POO):
- Usuario (AbstractBaseUser): modelo concreto con campo `rol`.
- Empleada (Proxy): métodos operativos.
- Administradora (Proxy de Empleada): métodos de gestión completa.

Se usa Single Table Inheritance manual con Proxy Models para mantener
una sola tabla en la BD y respetar la jerarquía de clases del diagrama.
"""
from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


# ──────────────────────────────────────────────────────────────
# Manager personalizado
# ──────────────────────────────────────────────────────────────


class UsuarioManager(BaseUserManager["Usuario"]):
    """Manager personalizado que usa email como identificador único."""

    def create_user(
        self,
        email: str,
        nombre: str,
        password: Optional[str] = None,
        **extra_fields: Any,
    ) -> "Usuario":
        """
        Crea y retorna un usuario con email y contraseña hasheada.

        Args:
            email: Dirección de correo electrónico (obligatorio).
            nombre: Nombre completo del usuario.
            password: Contraseña en texto plano (se hashea automáticamente).
            **extra_fields: Campos adicionales del modelo.

        Returns:
            Instancia de Usuario persistida en la BD.

        Raises:
            ValueError: Si no se proporciona email.
        """
        if not email:
            raise ValueError("El email es obligatorio.")
        email = self.normalize_email(email)
        user = self.model(email=email, nombre=nombre, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        nombre: str,
        password: Optional[str] = None,
        **extra_fields: Any,
    ) -> "Usuario":
        """
        Crea y retorna un superusuario (Administradora).

        Fuerza is_staff=True, is_superuser=True y rol=ADMINISTRADORA.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("rol", Usuario.Rol.ADMINISTRADORA)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True.")

        return self.create_user(email, nombre, password, **extra_fields)


# ──────────────────────────────────────────────────────────────
# Modelo base: Usuario
# ──────────────────────────────────────────────────────────────


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Modelo de usuario personalizado para Peluquería Lorena.

    Usa email como campo de autenticación (USERNAME_FIELD).
    Incluye un campo `rol` con dos opciones: ADMINISTRADORA y EMPLEADA.

    Attributes:
        email: Dirección de correo electrónico única.
        nombre: Nombre completo del usuario.
        rol: Rol del usuario en el sistema.
        is_active: Indica si el usuario está activo (soft delete).
        is_staff: Permite acceso al panel de administración.
        date_joined: Fecha de registro en el sistema.
    """

    class Rol(models.TextChoices):
        """Roles disponibles en el sistema."""

        ADMINISTRADORA = "ADMINISTRADORA", "Administradora"
        EMPLEADA = "EMPLEADA", "Empleada"

    # ── Campos del modelo ──
    email = models.EmailField(
        "correo electrónico",
        unique=True,
        db_index=True,
    )
    nombre = models.CharField(
        "nombre completo",
        max_length=255,
    )
    rol = models.CharField(
        "rol",
        max_length=20,
        choices=Rol.choices,
        default=Rol.EMPLEADA,
    )
    is_active = models.BooleanField(
        "activo",
        default=True,
    )
    is_staff = models.BooleanField(
        "es staff",
        default=False,
    )
    date_joined = models.DateTimeField(
        "fecha de registro",
        default=timezone.now,
    )

    # ── Configuración del modelo ──
    objects = UsuarioManager()
    USERNAME_FIELD: str = "email"
    REQUIRED_FIELDS: list[str] = ["nombre"]

    class Meta:
        db_table = "usuarios"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.email})"

    # ── Propiedades de dominio ──

    @property
    def es_administradora(self) -> bool:
        """Retorna True si el usuario tiene rol de Administradora."""
        return self.rol == self.Rol.ADMINISTRADORA

    @property
    def es_empleada(self) -> bool:
        """Retorna True si el usuario es Empleada o Administradora."""
        return self.rol in (self.Rol.EMPLEADA, self.Rol.ADMINISTRADORA)

    # ── Métodos de autenticación ──

    def iniciar_sesion(self) -> dict[str, str]:
        """
        Registra el inicio de sesión del usuario.

        Returns:
            Diccionario con datos básicos del usuario autenticado.
        """
        self.last_login = timezone.now()
        self.save(update_fields=["last_login"])
        return {
            "id": str(self.pk),
            "email": self.email,
            "nombre": self.nombre,
            "rol": self.rol,
        }

    def cerrar_sesion(self) -> bool:
        """
        Registra el cierre de sesión del usuario.

        Returns:
            True si la operación fue exitosa.
        """
        return True


# ──────────────────────────────────────────────────────────────
# Proxy Model: Empleada
# ──────────────────────────────────────────────────────────────


class Empleada(Usuario):
    """
    Proxy model para Empleadas.

    Hereda de Usuario y agrega métodos operativos específicos
    sin crear una tabla adicional en la base de datos.
    """

    class Meta:
        proxy = True
        verbose_name = "empleada"
        verbose_name_plural = "empleadas"

    # ── Métodos operativos ──

    def consultar_agenda(self) -> dict[str, Any]:
        """
        Consulta la agenda de turnos de la empleada.

        Returns:
            Diccionario con los turnos asignados.
        """
        # TODO: Integrar con módulo de Turnos en próxima etapa
        return {"empleada_id": self.pk, "turnos": []}

    def gestionar_clientas(self) -> dict[str, Any]:
        """
        Accede a la gestión de clientas asignadas.

        Returns:
            Diccionario con datos de clientas.
        """
        # TODO: Integrar con módulo de Clientes en próxima etapa
        return {"empleada_id": self.pk, "clientas": []}

    def registrar_cobro(self, **kwargs: Any) -> dict[str, Any]:
        """
        Registra un cobro realizado por la empleada.

        Returns:
            Diccionario con datos del cobro registrado.
        """
        # TODO: Integrar con módulo de Pagos en próxima etapa
        return {"empleada_id": self.pk, "cobro": kwargs}

    def registrar_trabajo(self, **kwargs: Any) -> dict[str, Any]:
        """
        Registra un trabajo/servicio realizado por la empleada.

        Returns:
            Diccionario con datos del trabajo registrado.
        """
        # TODO: Integrar con módulo de Servicios en próxima etapa
        return {"empleada_id": self.pk, "trabajo": kwargs}


# ──────────────────────────────────────────────────────────────
# Proxy Model: Administradora
# ──────────────────────────────────────────────────────────────


class Administradora(Empleada):
    """
    Proxy model para Administradoras.

    Hereda de Empleada (que hereda de Usuario) y agrega métodos
    de gestión completa del sistema.
    """

    class Meta:
        proxy = True
        verbose_name = "administradora"
        verbose_name_plural = "administradoras"

    # ── Métodos de gestión ──

    def gestionar_usuarios(self) -> dict[str, Any]:
        """
        Accede a la gestión completa de usuarios (CRUD).

        Returns:
            Diccionario con datos de gestión de usuarios.
        """
        return {"admin_id": self.pk, "accion": "gestionar_usuarios"}

    def gestionar_servicios(self) -> dict[str, Any]:
        """
        Accede a la gestión de servicios del salón.

        Returns:
            Diccionario con datos de gestión de servicios.
        """
        # TODO: Integrar con módulo de Servicios en próxima etapa
        return {"admin_id": self.pk, "accion": "gestionar_servicios"}

    def cerrar_caja(self) -> dict[str, Any]:
        """
        Realiza el cierre de caja diario.

        Returns:
            Diccionario con datos del cierre de caja.
        """
        # TODO: Integrar con módulo de Pagos en próxima etapa
        return {"admin_id": self.pk, "accion": "cerrar_caja"}

    def gestionar_proveedores(self) -> dict[str, Any]:
        """
        Accede a la gestión de proveedores.

        Returns:
            Diccionario con datos de gestión de proveedores.
        """
        # TODO: Integrar con módulo de Inventario en próxima etapa
        return {"admin_id": self.pk, "accion": "gestionar_proveedores"}

    def generar_reportes(self) -> dict[str, Any]:
        """
        Genera reportes del sistema.

        Returns:
            Diccionario con datos de reportes.
        """
        # TODO: Integrar con módulo de Reportes en próxima etapa
        return {"admin_id": self.pk, "accion": "generar_reportes"}

    def configurar_beneficios(self) -> dict[str, Any]:
        """
        Configura el sistema de beneficios y fidelización.

        Returns:
            Diccionario con datos de configuración de beneficios.
        """
        # TODO: Integrar con módulo de Clientes/Fidelización en próxima etapa
        return {"admin_id": self.pk, "accion": "configurar_beneficios"}


# ──────────────────────────────────────────────────────────────
# Modelo: Token de Reset de Password
# ──────────────────────────────────────────────────────────────


class PasswordResetToken(models.Model):
    """
    Token temporal para recuperación de contraseña.

    Se genera al solicitar un reset y expira según la configuración
    PASSWORD_RESET_TOKEN_EXPIRY_HOURS.
    """

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
        verbose_name="usuario",
    )
    token = models.CharField(
        "token",
        max_length=255,
        unique=True,
        db_index=True,
    )
    created_at = models.DateTimeField(
        "creado en",
        auto_now_add=True,
    )
    used = models.BooleanField(
        "utilizado",
        default=False,
    )

    class Meta:
        db_table = "password_reset_tokens"
        verbose_name = "token de reset de password"
        verbose_name_plural = "tokens de reset de password"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Reset token para {self.usuario.email}"

    def is_expired(self) -> bool:
        """Verifica si el token ha expirado."""
        from django.conf import settings

        expiry_hours: int = getattr(
            settings, "PASSWORD_RESET_TOKEN_EXPIRY_HOURS", 24
        )
        from datetime import timedelta

        return timezone.now() > self.created_at + timedelta(hours=expiry_hours)

    def is_valid(self) -> bool:
        """Verifica si el token es válido (no usado y no expirado)."""
        return not self.used and not self.is_expired()
