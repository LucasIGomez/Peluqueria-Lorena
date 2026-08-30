#!/usr/bin/env python
"""Django management command entry point — Peluquería Lorena."""
import os
import sys


def main() -> None:
    """Ejecuta tareas administrativas de Django."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. ¿Está instalado y "
            "disponible en la variable de entorno PYTHONPATH? "
            "¿Activaste el entorno virtual?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
