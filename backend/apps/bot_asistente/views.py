from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bot_asistente.handlers.whatsapp_client import enviar_mensaje_whatsapp
from apps.bot_asistente.serializers import WhatsAppWebhookPayloadSerializer
from apps.bot_asistente.services import TurnoBotService

logger = logging.getLogger(__name__)


class WhatsAppWebhookView(APIView):
    """
    Controlador para el webhook de WhatsApp Business Cloud API.
    GET: Verificación de handshake de Meta (hub.challenge).
    POST: Recepción y procesamiento de mensajes entrantes con validación de firma HMAC-SHA256.
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

        if not expected_token:
            logger.warning("WHATSAPP_VERIFY_TOKEN no está configurado en settings.")
            return HttpResponse("Configuración incompleta", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if mode == "subscribe" and verify_token == expected_token:
            return HttpResponse(challenge, content_type="text/plain", status=status.HTTP_200_OK)

        return HttpResponseForbidden("Token de verificación inválido")

    def _validar_firma(self, request) -> bool:
        """
        Valida la firma criptográfica X-Hub-Signature-256 enviada por Meta en los headers.
        """
        app_secret = getattr(settings, "WHATSAPP_APP_SECRET", "")
        if not app_secret:
            # Si no hay secreto configurado (entorno local sin integración configurada), permitir
            return True

        signature_header = (
            request.headers.get("X-Hub-Signature-256")
            or request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
        )

        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("Petición de webhook rechazada: encabezado X-Hub-Signature-256 ausente o con formato inválido.")
            return False

        body = request.body
        expected_signature = "sha256=" + hmac.new(
            app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature_header, expected_signature):
            logger.warning("Petición de webhook rechazada: firma HMAC-SHA256 inválida.")
            return False

        return True

    def post(self, request, *args, **kwargs):
        """
        Recepción de eventos y mensajes entrantes de WhatsApp.
        """
        # 1. Seguridad: Validación de firma HMAC-SHA256
        if not self._validar_firma(request):
            return HttpResponseForbidden("Firma no válida")

        # 2. Deserialización y extracción de mensaje
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

        # 3. Procesamiento en el servicio de dominio
        bot_service = TurnoBotService()
        respuesta_bot = bot_service.procesar_mensaje(
            telefono=telefono,
            texto=texto,
            nombre_remitente=nombre,
        )

        # 4. Envío de respuesta saliente a Meta Cloud API
        enviado_ok = enviar_mensaje_whatsapp(destinatario=telefono, texto=respuesta_bot)
        if not enviado_ok:
            logger.warning(
                "La respuesta del bot no pudo ser entregada a Meta Cloud API para el teléfono %s.",
                telefono,
            )

        return Response(
            {
                "status": "success",
                "respuesta": respuesta_bot,
                "mensaje_enviado": enviado_ok,
            },
            status=status.HTTP_200_OK,
        )
