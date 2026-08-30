"""
Peluquería Lorena — Factorías de datos para el módulo de Usuarios.

Utiliza factory_boy para generar instancias realistas de Usuario,
Empleada y Administradora para las suites de tests.
"""
import factory
from factory.django import DjangoModelFactory

from apps.usuarios.models import Administradora, Empleada, Usuario


class UsuarioFactory(DjangoModelFactory):
    """Factoría base para crear instancias de Usuario."""

    class Meta:
        model = Usuario
        django_get_or_create = ("email",)

    nombre = factory.Faker("name", locale="es_AR")
    email = factory.Faker("email")
    rol = Usuario.Rol.EMPLEADA
    is_active = True
    is_staff = False
    password = factory.PostGenerationMethodCall("set_password", "TestPass123!")


class EmpleadaFactory(UsuarioFactory):
    """Factoría para crear instancias de Empleada (proxy model)."""

    class Meta:
        model = Empleada
        django_get_or_create = ("email",)

    rol = Usuario.Rol.EMPLEADA


class AdministradoraFactory(UsuarioFactory):
    """Factoría para crear instancias de Administradora (proxy model)."""

    class Meta:
        model = Administradora
        django_get_or_create = ("email",)

    rol = Usuario.Rol.ADMINISTRADORA
    is_staff = True
