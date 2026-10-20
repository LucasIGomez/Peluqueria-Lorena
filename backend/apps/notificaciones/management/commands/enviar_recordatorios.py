"""
Peluquería Lorena — Comando de recordatorios de turno (RF 12.4).

Debe ejecutarse cada 10 minutos mediante cron o un timer del sistema, por ejemplo:
    */10 * * * * /var/www/peluqueria_lorena/backend/venv/bin/python /var/www/peluqueria_lorena/backend/manage.py enviar_recordatorios

Ejemplos:
    python manage.py enviar_recordatorios
    python manage.py enviar_recordatorios --anticipacion 30
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.notificaciones.services import NotificacionService


class Command(BaseCommand):
    help = "Envía por WhatsApp el recordatorio de los turnos que empiezan en la próxima hora (RF 12.4)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--anticipacion",
            type=int,
            default=None,
            help="Minutos de anticipación (defecto: RECORDATORIO_TURNO_ANTICIPACION_MINUTOS, 60).",
        )

    def handle(self, *args, **options):
        resumen = NotificacionService.enviar_recordatorios_turnos(anticipacion_minutos=options["anticipacion"])
        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios: {resumen['enviadas']} enviados, {resumen['fallidas']} fallidos, "
            f"{resumen['omitidas']} ya enviados."
        ))
