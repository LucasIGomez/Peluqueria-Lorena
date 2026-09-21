"""
Peluquería Lorena — Pruebas de integración para el webhook de WhatsApp Business API.
"""
from unittest.mock import patch
import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.bot_asistente.ai.interpreter import BotResponseSchema, IntencionEnum
from apps.bot_asistente.models import ConversacionBot, MensajeBot
from apps.servicios.models import Servicio
from apps.turnos.models import Turno


@pytest.mark.django_db
class TestWhatsAppWebhookIntegration:
    """Verifica el flujo completo del webhook (verificación Meta y procesamiento de mensajes)."""

    def test_verificacion_webhook_get_exitoso(self) -> None:
        """Meta envía GET con hub.mode, hub.verify_token y hub.challenge."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")
        token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "pelulorena_whatsapp_token_seguro")

        response = client.get(
            url,
            {
                "hub.mode": "subscribe",
                "hub.verify_token": token,
                "hub.challenge": "1234567890",
            },
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == "1234567890"

    def test_verificacion_webhook_get_token_invalido(self) -> None:
        """Si el verify token no coincide, debe rechazar con 403 Forbidden."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")

        response = client.get(
            url,
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "token_falso_incorrecto",
                "hub.challenge": "1234567890",
            },
        )
        assert response.status_code == 403

    def test_webhook_post_procesa_mensaje_entrante(self) -> None:
        """Meta envía POST con payload JSON del mensaje de WhatsApp."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")

        # Payload estándar de WhatsApp Cloud API
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"display_phone_number": "5491122334455", "phone_number_id": "100200300"},
                                "contacts": [{"profile": {"name": "Valeria Clienta"}, "wa_id": "5491122334455"}],
                                "messages": [
                                    {
                                        "from": "5491122334455",
                                        "id": "wamid.HBgLM...",
                                        "timestamp": "1726950000",
                                        "text": {"body": "Hola! Quiero sacar turno"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

        with patch("apps.bot_asistente.services.TurnoBotService._esta_en_horario", return_value=True):
            response = client.post(url, data=payload, format="json")

        assert response.status_code == 200
        assert response.data.get("status") == "success"

        # Debe haberse creado la conversación y registrado los mensajes
        conversacion = ConversacionBot.objects.get(telefono_cliente="5491122334455")
        assert conversacion is not None
        assert MensajeBot.objects.filter(conversacion=conversacion).count() >= 1
