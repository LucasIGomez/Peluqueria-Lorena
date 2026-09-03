"""
Peluquería Lorena — Vistas (Views) del módulo de Usuarios.

Implementa:
1. Vistas Web SSR (Plantillas Django + Bootstrap 5):
   - Login y Logout de usuarios.
   - Registro público con validación de PIN para Administradora.
   - Panel de Gestión de Usuarios (CRUD exclusivo para Administradoras).
2. Endpoints de la API REST (DRF):
   - UsuarioViewSet: CRUD completo de usuarios (solo Administradora).
   - LoginView: Autenticación JWT con datos del usuario.
   - RegistroAPIView: Registro público vía API con validación de PIN.
   - PerfilView: Lectura/edición del perfil del usuario autenticado.
   - PasswordResetRequestView & PasswordResetConfirmView.
"""
from __future__ import annotations

from typing import Any
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView  # noqa: F401

from .forms import LoginForm, RegistroForm, UsuarioAdminForm, UsuarioEditForm
from .models import Usuario
from .permissions import EsAdministradora
from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PerfilUpdateSerializer,
    RegistroSerializer,
    UsuarioCreateSerializer,
    UsuarioSerializer,
    UsuarioUpdateSerializer,
)
from .services import UsuarioService


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR — Autenticación (Login, Logout, Registro)
# ──────────────────────────────────────────────────────────────


def login_view(request):
    """
    Vista Web de inicio de sesión.
    Autentica credenciales y establece la sesión del usuario.
    """
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            password = form.cleaned_data["password"]

            try:
                usuario = Usuario.objects.get(email=email)
            except Usuario.DoesNotExist:
                messages.error(request, "Correo electrónico o contraseña incorrectos.")
                return render(request, "usuarios/login.html", {"form": form})

            if not usuario.is_active:
                messages.error(request, "Esta cuenta ha sido desactivada. Contactá a la administración.")
                return render(request, "usuarios/login.html", {"form": form})

            if usuario.check_password(password):
                # Iniciar sesión Django
                auth_login(request, usuario)
                usuario.iniciar_sesion()
                messages.success(request, f"¡Bienvenida, {usuario.nombre}! Has iniciado sesión como {usuario.get_rol_display()}.")
                next_url = request.GET.get("next") or "index"
                return redirect(next_url)
            else:
                messages.error(request, "Correo electrónico o contraseña incorrectos.")
    else:
        form = LoginForm()

    return render(request, "usuarios/login.html", {"form": form})


def logout_view(request):
    """
    Vista Web para cerrar la sesión activa.
    """
    auth_logout(request)
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect("usuarios:login")


def registro_view(request):
    """
    Vista Web para registro de nuevos usuarios.
    Si el rol elegido es Administradora, exige y valida el PIN de seguridad.
    """
    if request.user.is_authenticated and not request.user.es_administradora:
        return redirect("index")

    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                usuario = UsuarioService.crear_usuario(
                    nombre=form.cleaned_data["nombre"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    rol=form.cleaned_data["rol"],
                    admin_pin=form.cleaned_data.get("admin_pin"),
                    requiere_pin=True,
                )
                messages.success(
                    request,
                    f"¡Cuenta creada con éxito para {usuario.nombre}! Ya podés iniciar sesión.",
                )
                return redirect("usuarios:login")
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = RegistroForm()

    return render(request, "usuarios/registro.html", {"form": form})


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR — Panel de Gestión de Usuarios (Solo Administradora)
# ──────────────────────────────────────────────────────────────


def es_admin_check(user: Usuario) -> bool:
    """Helper que comprueba si el usuario autenticado es Administradora."""
    return user.is_authenticated and user.es_administradora


@login_required
@user_passes_test(es_admin_check, login_url="index")
def lista_usuarios_view(request):
    """
    Lista todos los usuarios del sistema (empleadas y administradoras).
    Exclusivo para usuarias con rol Administradora.
    """
    usuarios = Usuario.objects.all().order_by("-is_active", "nombre")
    total_empleadas = Usuario.objects.filter(rol=Usuario.Rol.EMPLEADA, is_active=True).count()
    total_admins = Usuario.objects.filter(rol=Usuario.Rol.ADMINISTRADORA, is_active=True).count()

    context = {
        "usuarios": usuarios,
        "total_empleadas": total_empleadas,
        "total_admins": total_admins,
    }
    return render(request, "usuarios/lista_usuarios.html", context)


@login_required
@user_passes_test(es_admin_check, login_url="index")
def crear_usuario_view(request):
    """
    Permite a la Administradora registrar un nuevo usuario desde el panel de gestión.
    """
    if request.method == "POST":
        form = UsuarioAdminForm(request.POST)
        if form.is_valid():
            try:
                usuario = UsuarioService.crear_usuario(
                    nombre=form.cleaned_data["nombre"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    rol=form.cleaned_data["rol"],
                    admin_pin=form.cleaned_data.get("admin_pin"),
                    requiere_pin=True,
                )
                messages.success(request, f"Usuario '{usuario.nombre}' ({usuario.get_rol_display()}) creado exitosamente.")
                return redirect("usuarios:lista_usuarios")
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = UsuarioAdminForm()

    return render(request, "usuarios/form_usuario.html", {"form": form, "accion": "Crear Nuevo Usuario"})


@login_required
@user_passes_test(es_admin_check, login_url="index")
def editar_usuario_view(request, pk: int):
    """
    Permite a la Administradora modificar los datos y rol de un usuario existente.
    """
    usuario = get_object_or_404(Usuario, pk=pk)

    if request.method == "POST":
        form = UsuarioEditForm(request.POST, instance=usuario)
        if form.is_valid():
            usuario_actualizado = form.save(commit=False)
            UsuarioService.actualizar_usuario(
                usuario=usuario,
                nombre=usuario_actualizado.nombre,
                email=usuario_actualizado.email,
                rol=usuario_actualizado.rol,
            )
            # Guardar estado activo si cambió
            usuario.is_active = form.cleaned_data["is_active"]
            usuario.save(update_fields=["is_active"])

            messages.success(request, f"Datos de '{usuario.nombre}' actualizados correctamente.")
            return redirect("usuarios:lista_usuarios")
    else:
        form = UsuarioEditForm(instance=usuario)

    return render(
        request,
        "usuarios/form_usuario.html",
        {"form": form, "usuario_edit": usuario, "accion": "Editar Usuario"},
    )


@login_required
@user_passes_test(es_admin_check, login_url="index")
def eliminar_usuario_view(request, pk: int):
    """
    Baja lógica de usuario (desactiva la cuenta preservando historial).
    """
    usuario = get_object_or_404(Usuario, pk=pk)

    if request.user.pk == usuario.pk:
        messages.error(request, "No podés desactivar tu propia cuenta administradora.")
        return redirect("usuarios:lista_usuarios")

    if request.method == "POST":
        nombre = usuario.nombre
        UsuarioService.eliminar_usuario(usuario)
        messages.success(request, f"El usuario '{nombre}' ha sido dado de baja (desactivado).")
        return redirect("usuarios:lista_usuarios")

    return render(request, "usuarios/eliminar_usuario.html", {"usuario_target": usuario})


# ── Alias camelCase para vistas Web ──
loginView = login_view
logoutView = logout_view
registroView = registro_view
listaUsuariosView = lista_usuarios_view
crearUsuarioView = crear_usuario_view
editarUsuarioView = editar_usuario_view
eliminarUsuarioView = eliminar_usuario_view


# ──────────────────────────────────────────────────────────────
# API REST (DRF ViewSets & Endpoints)
# ──────────────────────────────────────────────────────────────


class UsuarioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para operaciones CRUD sobre usuarios.
    Solo accesible por Administradoras autenticadas.
    """

    queryset = Usuario.objects.filter(is_active=True).order_by("nombre")
    permission_classes = [IsAuthenticated, EsAdministradora]

    def get_serializer_class(self) -> type:
        if self.action == "create":
            return UsuarioCreateSerializer
        if self.action in ("update", "partial_update"):
            return UsuarioUpdateSerializer
        return UsuarioSerializer

    def perform_destroy(self, instance: Usuario) -> None:
        UsuarioService.eliminar_usuario(instance)


class RegistroAPIView(APIView):
    """
    Endpoint API para registro público de usuarios.
    POST /api/v1/usuarios/auth/registro/
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        return Response(
            {
                "mensaje": f"Usuario {usuario.nombre} registrado con éxito.",
                "usuario": UsuarioSerializer(usuario).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    Vista de login que retorna tokens JWT y datos del usuario.
    POST /api/v1/usuarios/auth/login/
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email: str = request.data.get("email", "")
        password: str = request.data.get("password", "")

        try:
            usuario = Usuario.objects.get(email=email)
        except Usuario.DoesNotExist:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not usuario.is_active or not usuario.check_password(password):
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(usuario)
        usuario.iniciar_sesion()
        usuario_data = UsuarioSerializer(usuario).data

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "usuario": usuario_data,
            },
            status=status.HTTP_200_OK,
        )


class PerfilView(APIView):
    """
    Vista para lectura y edición del perfil del usuario autenticado.
    GET /api/v1/usuarios/perfil/ — Retorna datos del perfil.
    PATCH /api/v1/usuarios/perfil/ — Actualiza nombre.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UsuarioSerializer(request.user).data)

    def patch(self, request: Request) -> Response:
        serializer = PerfilUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UsuarioSerializer(request.user).data)


class PasswordResetRequestView(APIView):
    """Solicitud de recuperación de contraseña."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UsuarioService.solicitar_reset_password(serializer.validated_data["email"])
        return Response(
            {"detail": "Si el correo existe en nuestro sistema, recibirás un enlace de recuperación."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """Confirmación de reset de contraseña con token."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success = UsuarioService.confirmar_reset_password(
            serializer.validated_data["token"],
            serializer.validated_data["new_password"],
        )

        if not success:
            return Response({"detail": "Token inválido o expirado."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Contraseña actualizada correctamente."}, status=status.HTTP_200_OK)
