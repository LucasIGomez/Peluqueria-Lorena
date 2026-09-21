from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bot_asistente.serializers import WhatsAppWebhookPayloadSerializer
from apps.bot_asistente.services import TurnoBotService


class WhatsAppWebhookView(APIView):
    """
    Controlador para el webhook de WhatsApp Business Cloud API.
    GET: Verificación de handshake de Meta (hub.challenge).
    POST: Recepción y procesamiento de mensajes entrantes.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        """
        Validación del webhook requerida por Meta Developers.
        """
        mode = request.query_params.get("hub.mode")
        verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        expected_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "")

        if mode == "subscribe" and verify_token == expected_token:
            return HttpResponse(challenge, content_type="text/plain", status=status.HTTP_200_OK)

        return HttpResponse("Token de verificación inválido", status=status.HTTP_403_FORBIDDEN)

    def post(self, request, *args, **kwargs):
        """
        Recepción de eventos y mensajes entrantes de WhatsApp.
        """
        serializer = WhatsAppWebhookPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": "error", "errores": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        info_mensaje = serializer.extraer_mensaje()
        telefono = info_mensaje.get("telefono")
        texto = info_mensaje.get("texto")
        nombre = info_mensaje.get("nombre", "Clienta")

        if not telefono or not texto:
            # Evento sin mensaje de texto útil (e.g. status de entrega o lectura de Meta)
            return Response({"status": "ignored", "detail": "Evento sin contenido de mensaje"}, status=status.HTTP_200_OK)

        bot_service = TurnoBotService()
        respuesta_bot = bot_service.procesar_mensaje(
            telefono=telefono,
            texto=texto,
            nombre_remitente=nombre,
        )

        return Response(
            {
                "status": "success",
                "respuesta": respuesta_bot,
            },
            status=status.HTTP_200_OK,
        )
