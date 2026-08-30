"""
Peluquería Lorena — Vistas (Views) del módulo de Usuarios.

Implementa los endpoints de la API REST:
- UsuarioViewSet: CRUD completo de usuarios (solo Administradora).
- LoginView: Autenticación JWT con datos del usuario.
- PerfilView: Lectura/edición del perfil del usuario autenticado.
- PasswordResetRequestView: Solicitud de reset de contraseña.
- PasswordResetConfirmView: Confirmación de reset con token.
"""
from __future__ import annotations

from typing import Any

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView  # noqa: F401

from .models import Usuario
from .permissions import EsAdministradora
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PerfilUpdateSerializer,
    UsuarioCreateSerializer,
    UsuarioSerializer,
    UsuarioUpdateSerializer,
)
from .services import UsuarioService


# ──────────────────────────────────────────────────────────────
# CRUD de Usuarios (solo Administradora)
# ──────────────────────────────────────────────────────────────


class UsuarioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operaciones CRUD sobre usuarios.

    Solo accesible por Administradoras. Usa el servicio
    de negocio para la lógica de eliminación (soft delete).
    """

    queryset = Usuario.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated, EsAdministradora]

    def get_serializer_class(self) -> type:
        """Retorna el serializer según la acción."""
        if self.action == "create":
            return UsuarioCreateSerializer
        if self.action in ("update", "partial_update"):
            return UsuarioUpdateSerializer
        return UsuarioSerializer

    def perform_destroy(self, instance: Usuario) -> None:
        """Ejecuta soft delete via el servicio de negocio."""
        UsuarioService.eliminar_usuario(instance)


# ──────────────────────────────────────────────────────────────
# Autenticación JWT — Login
# ──────────────────────────────────────────────────────────────


class LoginView(APIView):
    """
    Vista de login que retorna tokens JWT y datos del usuario.

    POST /api/v1/usuarios/auth/login/
    Body: { "email": "...", "password": "..." }
    Response: { "access": "...", "refresh": "...", "usuario": {...} }
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Autentica al usuario y retorna tokens + datos."""
        email: str = request.data.get("email", "")
        password: str = request.data.get("password", "")

        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not usuario.is_active:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not usuario.check_password(password):
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Generar tokens JWT
        refresh = RefreshToken.for_user(usuario)

        # Registrar inicio de sesión
        usuario.iniciar_sesion()

        # Serializar datos del usuario
        usuario_data = UsuarioSerializer(usuario).data

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "usuario": usuario_data,
            },
            status=status.HTTP_200_OK,
        )


# ──────────────────────────────────────────────────────────────
# Perfil del Usuario Autenticado
# ──────────────────────────────────────────────────────────────


class PerfilView(APIView):
    """
    Vista para lectura y edición del perfil del usuario autenticado.

    GET /api/v1/usuarios/perfil/ — Retorna datos del perfil.
    PATCH /api/v1/usuarios/perfil/ — Actualiza nombre (no rol ni email).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """Retorna los datos del usuario autenticado."""
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request: Request) -> Response:
        """Actualiza los datos del perfil del usuario autenticado."""
        serializer = PerfilUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Re-serializar con el serializer de lectura para respuesta limpia
        return Response(UsuarioSerializer(request.user).data)


# ──────────────────────────────────────────────────────────────
# Password Reset — Solicitud
# ──────────────────────────────────────────────────────────────


class PasswordResetRequestView(APIView):
    """
    Solicitud de recuperación de contraseña.

    POST /api/v1/usuarios/auth/password-reset/
    Body: { "email": "..." }

    Siempre retorna 200 para no revelar la existencia de cuentas.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Genera token de reset y envía correo."""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email: str = serializer.validated_data["email"]
        UsuarioService.solicitar_reset_password(email)

        return Response(
            {
                "detail": (
                    "Si el correo existe en nuestro sistema, "
                    "recibirás un enlace de recuperación."
                )
            },
            status=status.HTTP_200_OK,
        )


# ──────────────────────────────────────────────────────────────
# Password Reset — Confirmación
# ──────────────────────────────────────────────────────────────


class PasswordResetConfirmView(APIView):
    """
    Confirmación de reset de contraseña con token.

    POST /api/v1/usuarios/auth/password-reset-confirm/
    Body: { "token": "...", "new_password": "..." }
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """Valida el token y establece la nueva contraseña."""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token: str = serializer.validated_data["token"]
        new_password: str = serializer.validated_data["new_password"]

        success = UsuarioService.confirmar_reset_password(token, new_password)

        if not success:
            return Response(
                {"detail": "Token inválido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Contraseña actualizada correctamente."},
            status=status.HTTP_200_OK,
        )
