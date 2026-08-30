"""Configuración de la app de Usuarios."""
from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    """Configuración de la aplicación de usuarios."""

    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "apps.usuarios"
    verbose_name: str = "Usuarios"
