"""
Peluquería Lorena — Tests de integración del módulo de Usuarios (API).

Valida el comportamiento de los endpoints REST completos:
- Login JWT (access + refresh + datos de usuario)
- Refresh token
- CRUD de usuarios con restricción por rol
- Acceso al perfil propio
- Denegación de acceso sin autenticación
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.usuarios.models import Usuario
from tests.factories.usuario_factory import (
    AdministradoraFactory,
    EmpleadaFactory,
    UsuarioFactory,
)


# ──────────────────────────────────────────────────────────────
# URLs base
# ──────────────────────────────────────────────────────────────
AUTH_LOGIN_URL = "/api/v1/usuarios/auth/login/"
AUTH_REFRESH_URL = "/api/v1/usuarios/auth/refresh/"
USUARIOS_URL = "/api/v1/usuarios/"
PERFIL_URL = "/api/v1/usuarios/perfil/"


# ──────────────────────────────────────────────────────────────
# Tests de Autenticación JWT
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLoginJWT:
    """Verifica el flujo de login con JWT."""

    def test_login_exitoso_retorna_tokens(self, api_client: APIClient) -> None:
        """Login con credenciales válidas retorna access y refresh tokens."""
        UsuarioFactory(email="login@test.com")
        response = api_client.post(
            AUTH_LOGIN_URL,
            {"email": "login@test.com", "password": "TestPass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert "usuario" in data

    def test_login_retorna_datos_de_usuario(self, api_client: APIClient) -> None:
        """El login incluye los datos del usuario autenticado."""
        UsuarioFactory(
            email="datos@test.com",
            nombre="María Test",
            rol=Usuario.Rol.EMPLEADA,
        )
        response = api_client.post(
            AUTH_LOGIN_URL,
            {"email": "datos@test.com", "password": "TestPass123!"},
            format="json",
        )
        data = response.json()
        usuario_data = data["usuario"]
        assert usuario_data["email"] == "datos@test.com"
        assert usuario_data["nombre"] == "María Test"
        assert usuario_data["rol"] == "EMPLEADA"

    def test_login_con_password_incorrecta_retorna_401(
        self, api_client: APIClient
    ) -> None:
        """Login con contraseña incorrecta retorna 401."""
        UsuarioFactory(email="badpw@test.com")
        response = api_client.post(
            AUTH_LOGIN_URL,
            {"email": "badpw@test.com", "password": "IncorrectaXYZ"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_con_email_inexistente_retorna_401(
        self, api_client: APIClient
    ) -> None:
        """Login con email que no existe retorna 401."""
        response = api_client.post(
            AUTH_LOGIN_URL,
            {"email": "noexiste@test.com", "password": "AnyPass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_usuario_inactivo_retorna_401(
        self, api_client: APIClient
    ) -> None:
        """Login con usuario desactivado retorna 401."""
        UsuarioFactory(email="inactivo@test.com", is_active=False)
        response = api_client.post(
            AUTH_LOGIN_URL,
            {"email": "inactivo@test.com", "password": "TestPass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRefreshToken:
    """Verifica el refresh de tokens JWT."""

    def test_refresh_retorna_nuevo_access_token(
        self, api_client: APIClient
    ) -> None:
        """POST con refresh token válido retorna un nuevo access token."""
        UsuarioFactory(email="refresh@test.com")
        login_response = api_client.post(
            AUTH_LOGIN_URL,
            {"email": "refresh@test.com", "password": "TestPass123!"},
            format="json",
        )
        refresh_token = login_response.json()["refresh"]

        response = api_client.post(
            AUTH_REFRESH_URL,
            {"refresh": refresh_token},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.json()


# ──────────────────────────────────────────────────────────────
# Tests de CRUD de Usuarios — Administradora
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCRUDUsuariosAdministradora:
    """Verifica que la Administradora tenga acceso CRUD completo."""

    def test_listar_usuarios(
        self, authenticated_client_administradora: APIClient
    ) -> None:
        """Administradora puede listar todos los usuarios."""
        # Crear algunos usuarios extra
        EmpleadaFactory(email="extra1@test.com")
        EmpleadaFactory(email="extra2@test.com")

        response = authenticated_client_administradora.get(USUARIOS_URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # La respuesta paginada contiene "results"
        assert "results" in data
        # Al menos 3 usuarios: admin + 2 extras
        assert data["count"] >= 3

    def test_crear_usuario(
        self, authenticated_client_administradora: APIClient
    ) -> None:
        """Administradora puede crear un nuevo usuario."""
        response = authenticated_client_administradora.post(
            USUARIOS_URL,
            {
                "nombre": "Nueva Empleada",
                "email": "nueva@test.com",
                "dni": "41222333",
                "rol": "EMPLEADA",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "nueva@test.com"
        assert data["rol"] == "EMPLEADA"
        # Ni la password ni el DNI se devuelven en la respuesta
        assert "password" not in data
        assert "dni" not in data

    def test_ver_detalle_usuario(
        self,
        authenticated_client_administradora: APIClient,
        usuario_empleada: Usuario,
    ) -> None:
        """Administradora puede ver el detalle de cualquier usuario."""
        url = f"{USUARIOS_URL}{usuario_empleada.pk}/"
        response = authenticated_client_administradora.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["email"] == usuario_empleada.email

    def test_actualizar_usuario(
        self,
        authenticated_client_administradora: APIClient,
        usuario_empleada: Usuario,
    ) -> None:
        """Administradora puede actualizar datos de cualquier usuario."""
        url = f"{USUARIOS_URL}{usuario_empleada.pk}/"
        response = authenticated_client_administradora.patch(
            url,
            {"nombre": "Nombre Actualizado"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["nombre"] == "Nombre Actualizado"

    def test_eliminar_usuario_soft_delete(
        self,
        authenticated_client_administradora: APIClient,
        usuario_empleada: Usuario,
    ) -> None:
        """Administradora puede eliminar (soft delete) un usuario."""
        url = f"{USUARIOS_URL}{usuario_empleada.pk}/"
        response = authenticated_client_administradora.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        usuario_empleada.refresh_from_db()
        assert usuario_empleada.is_active is False


# ──────────────────────────────────────────────────────────────
# Tests de CRUD de Usuarios — Empleada (acceso restringido)
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCRUDUsuariosEmpleada:
    """Verifica que la Empleada tenga acceso restringido."""

    def test_empleada_no_puede_listar_usuarios(
        self, authenticated_client_empleada: APIClient
    ) -> None:
        """Empleada NO puede listar todos los usuarios."""
        response = authenticated_client_empleada.get(USUARIOS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_empleada_no_puede_crear_usuarios(
        self, authenticated_client_empleada: APIClient
    ) -> None:
        """Empleada NO puede crear nuevos usuarios."""
        response = authenticated_client_empleada.post(
            USUARIOS_URL,
            {
                "nombre": "Intrusa",
                "email": "intrusa@test.com",
                "dni": "42333444",
                "rol": "EMPLEADA",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_empleada_no_puede_eliminar_usuarios(
        self,
        authenticated_client_empleada: APIClient,
        usuario_administradora: Usuario,
    ) -> None:
        """Empleada NO puede eliminar otros usuarios."""
        url = f"{USUARIOS_URL}{usuario_administradora.pk}/"
        response = authenticated_client_empleada.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ──────────────────────────────────────────────────────────────
# Tests de Perfil Propio
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPerfilPropio:
    """Verifica el acceso al perfil del usuario autenticado."""

    def test_empleada_puede_ver_su_perfil(
        self,
        authenticated_client_empleada: APIClient,
        usuario_empleada: Usuario,
    ) -> None:
        """Empleada puede ver su propio perfil."""
        response = authenticated_client_empleada.get(PERFIL_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["email"] == usuario_empleada.email

    def test_empleada_puede_editar_su_perfil(
        self,
        authenticated_client_empleada: APIClient,
    ) -> None:
        """Empleada puede editar su propio nombre."""
        response = authenticated_client_empleada.patch(
            PERFIL_URL,
            {"nombre": "Mi Nuevo Nombre"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["nombre"] == "Mi Nuevo Nombre"

    def test_empleada_no_puede_cambiar_su_rol(
        self,
        authenticated_client_empleada: APIClient,
    ) -> None:
        """Empleada NO puede auto-promover su rol."""
        response = authenticated_client_empleada.patch(
            PERFIL_URL,
            {"rol": "ADMINISTRADORA"},
            format="json",
        )
        # La vista debe ignorar el campo rol o denegar
        if response.status_code == status.HTTP_200_OK:
            assert response.json()["rol"] == "EMPLEADA"


# ──────────────────────────────────────────────────────────────
# Tests de Acceso Sin Autenticación
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAccesoSinAutenticacion:
    """Verifica que los endpoints protegidos rechacen acceso anónimo."""

    def test_listar_usuarios_sin_auth_retorna_401(
        self, api_client: APIClient
    ) -> None:
        """GET /usuarios/ sin token retorna 401."""
        response = api_client.get(USUARIOS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_perfil_sin_auth_retorna_401(
        self, api_client: APIClient
    ) -> None:
        """GET /perfil/ sin token retorna 401."""
        response = api_client.get(PERFIL_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
