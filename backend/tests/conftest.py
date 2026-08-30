"""
Peluquería Lorena — Fixtures compartidos para pytest.

Define fixtures reutilizables para toda la suite de tests:
- Clientes de API (con y sin autenticación)
- Usuarios pre-creados por rol
- Headers de autenticación JWT
"""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.template.context import BaseContext

# Compatibilidad de copy(context) en Python 3.14 + Django 5.1
def _compat_basecontext_copy(self):
    duplicate = object.__new__(self.__class__)
    duplicate.dicts = self.dicts[:]
    return duplicate

BaseContext.__copy__ = _compat_basecontext_copy

from apps.usuarios.models import Usuario
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.fixture
def api_client() -> APIClient:
    """Cliente de API sin autenticación."""
    return APIClient()


@pytest.fixture
def usuario_empleada(db) -> Usuario:
    """Crea y retorna una Empleada con credenciales de prueba."""
    return EmpleadaFactory(
        email="empleada@peluquerialorena.com",
        nombre="María López",
    )


@pytest.fixture
def usuario_administradora(db) -> Usuario:
    """Crea y retorna una Administradora con credenciales de prueba."""
    return AdministradoraFactory(
        email="admin@peluquerialorena.com",
        nombre="Lorena García",
    )


@pytest.fixture
def auth_headers_empleada(
    usuario_empleada: Usuario,
) -> dict[str, str]:
    """Retorna headers con JWT de autenticación para la Empleada."""
    refresh = RefreshToken.for_user(usuario_empleada)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def auth_headers_administradora(
    usuario_administradora: Usuario,
) -> dict[str, str]:
    """Retorna headers con JWT de autenticación para la Administradora."""
    refresh = RefreshToken.for_user(usuario_administradora)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def authenticated_client_empleada(
    api_client: APIClient,
    usuario_empleada: Usuario,
) -> APIClient:
    """Cliente de API autenticado como Empleada."""
    refresh = RefreshToken.for_user(usuario_empleada)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def authenticated_client_administradora(
    api_client: APIClient,
    usuario_administradora: Usuario,
) -> APIClient:
    """Cliente de API autenticado como Administradora."""
    refresh = RefreshToken.for_user(usuario_administradora)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client
