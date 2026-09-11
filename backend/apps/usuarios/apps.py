"""Configuración de la app de Usuarios."""
from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    """Configuración de la aplicación de usuarios."""

    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "apps.usuarios"
    verbose_name: str = "Usuarios"

    def ready(self) -> None:
        """Inicializaciones globales del sistema."""
        try:
            import django.utils.dates as django_dates

            # Sobrescribir traducción arcaica de Django ("setiembre" -> "septiembre")
            django_dates.MONTHS[9] = "septiembre"
            django_dates.MONTHS_ALT[9] = "septiembre"
            django_dates.MONTHS_3[9] = "sep"
            django_dates.MONTHS_AP[9] = "sept."
        except Exception:
            pass
