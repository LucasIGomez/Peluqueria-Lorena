"""
Peluquería Lorena — Comando de gestión para simular chat de WhatsApp con el bot asistente.

Permite probar el flujo conversacional completo en consola (menú numérico,
procesamiento con IA, consulta de catálogo y agendado de turnos) antes de
conectar las credenciales reales de Meta Cloud API.
"""
from django.core.management.base import BaseCommand
from apps.bot_asistente.services import TurnoBotService
from apps.bot_asistente.models import ConversacionBot


class Command(BaseCommand):
    help = "Inicia una consola interactiva para simular un chat de WhatsApp con el bot asistente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--telefono",
            type=str,
            default="5491122334455",
            help="Número de teléfono simulado (default: 5491122334455)",
        )
        parser.add_argument(
            "--nombre",
            type=str,
            default="Clienta Test",
            help="Nombre de la clienta remitente (default: Clienta Test)",
        )

    def handle(self, *args, **options):
        telefono = options["telefono"]
        nombre = options["nombre"]

        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(self.style.SUCCESS("🤖 SIMULADOR INTERACTIVO DE WHATSAPP — PELUQUERÍA LORENA"))
        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(f"📱 Teléfono remitente: {telefono}")
        self.stdout.write(f"👤 Nombre remitente:   {nombre}")
        self.stdout.write("💡 Escribí tu mensaje y presioná Enter.")
        self.stdout.write("💡 Escribí 'salir' o 'exit' para terminar la simulación.\n")

        # Mensaje de bienvenida inicial
        respuesta_inicial = TurnoBotService.procesar_mensaje(
            telefono=telefono,
            texto="Hola",
            nombre_remitente=nombre,
        )
        self.stdout.write(self.style.WARNING("🤖 Bot Lorena dice:"))
        self.stdout.write(respuesta_inicial)
        self.stdout.write("-" * 65)

        while True:
            try:
                mensaje_usuario = input(f"\n💬 {nombre}: ").strip()
            except (KeyboardInterrupt, EOFError):
                self.stdout.write("\nSimulación finalizada.")
                break

            if not mensaje_usuario:
                continue

            if mensaje_usuario.lower() in ("salir", "exit", "quit"):
                self.stdout.write(self.style.SUCCESS("¡Hasta luego! Simulación terminada."))
                break

            respuesta = TurnoBotService.procesar_mensaje(
                telefono=telefono,
                texto=mensaje_usuario,
                nombre_remitente=nombre,
            )

            # Consultar estado actual de la conversación
            conv = ConversacionBot.objects.filter(telefono_cliente=telefono).first()
            estado_info = f" [Estado: {conv.get_estado_display()} | Requiere humano: {conv.requiere_humano}]" if conv else ""

            self.stdout.write(self.style.WARNING(f"\n🤖 Bot Lorena{estado_info}:"))
            self.stdout.write(respuesta)
            self.stdout.write("-" * 65)
