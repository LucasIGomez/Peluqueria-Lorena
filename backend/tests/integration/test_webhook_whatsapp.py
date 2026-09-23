"""
Peluquería Lorena — Pruebas de integración para el webhook de WhatsApp Business API.
Valida handshake GET, verificación criptográfica de firma HMAC-SHA256 y envío saliente a Meta Cloud API.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch
import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.bot_asistente.models import ConversacionBot, MensajeBot


def _calcular_firma_hmac(cuerpo_bytes: bytes, secreto: str) -> str:
    """Helper para calcular el header X-Hub-Signature-256."""
    return "sha256=" + hmac.new(secreto.encode("utf-8"), cuerpo_bytes, hashlib.sha256).hexdigest()


@pytest.mark.django_db
class TestWhatsAppWebhookIntegration:
    """Verifica el flujo completo del webhook (verificación Meta, seguridad HMAC y procesamiento de mensajes)."""

    def _payload_mensaje_estandar(self, texto: str = "Hola! Quiero sacar turno") -> dict:
        return {
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
                                        "text": {"body": texto},
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

    def test_verificacion_webhook_get_exitoso(self) -> None:
        """Meta envía GET con hub.mode, hub.verify_token y hub.challenge."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")
        token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "test_verify_token")

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

    def test_webhook_post_rechaza_sin_firma_cuando_hay_secret(self) -> None:
        """Si WHATSAPP_APP_SECRET está configurado y el request no trae firma, debe rechazar con 403."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")
        payload = self._payload_mensaje_estandar()
        cuerpo_json = json.dumps(payload)

        with patch("apps.bot_asistente.services.TurnoBotService._esta_en_horario", return_value=True):
            response = client.post(
                url,
                data=cuerpo_json,
                content_type="application/json",
            )
        assert response.status_code == 403
        assert b"Firma no" in response.content

    def test_webhook_post_rechaza_firma_invalida_o_adulterada(self) -> None:
        """Si el request trae una firma que no coincide con el HMAC del cuerpo, debe rechazar con 403."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")
        payload = self._payload_mensaje_estandar()
        cuerpo_json = json.dumps(payload)

        with patch("apps.bot_asistente.services.TurnoBotService._esta_en_horario", return_value=True):
            response = client.post(
                url,
                data=cuerpo_json,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256="sha256=firma_falsa_manipulada_1234567890",
            )
        assert response.status_code == 403
        assert b"Firma no" in response.content

    def test_webhook_post_acepta_con_firma_valida_y_procesa(self) -> None:
        """Con firma HMAC-SHA256 correcta, procesa el mensaje y retorna 200 OK."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")
        payload = self._payload_mensaje_estandar("Hola, quiero saber los precios")
        cuerpo_json = json.dumps(payload)
        cuerpo_bytes = cuerpo_json.encode("utf-8")

        secret = getattr(settings, "WHATSAPP_APP_SECRET", "test_secret_key_12345")
        firma_correcta = _calcular_firma_hmac(cuerpo_bytes, secret)

        with patch("apps.bot_asistente.services.TurnoBotService._esta_en_horario", return_value=True), \
             patch("apps.bot_asistente.views.enviar_mensaje_whatsapp", return_value=True) as mock_envio:
            response = client.post(
                url,
                data=cuerpo_json,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256=firma_correcta,
            )

        assert response.status_code == 200
        assert response.data.get("status") == "success"
        assert response.data.get("mensaje_enviado") is True
        mock_envio.assert_called_once()

        # Verifica persistencia
        conversacion = ConversacionBot.objects.get(telefono_cliente="5491122334455")
        assert conversacion is not None
        assert MensajeBot.objects.filter(conversacion=conversacion).count() >= 1

    def test_webhook_post_dispara_envio_saliente_a_meta_cloud_api(self) -> None:
        """Confirma que enviar_mensaje_whatsapp realice la llamada HTTP POST a Graph API con payload correcto."""
        client = APIClient()
        url = reverse("bot_asistente:webhook")
        payload = self._payload_mensaje_estandar("Hola")
        cuerpo_json = json.dumps(payload)
        cuerpo_bytes = cuerpo_json.encode("utf-8")

        secret = getattr(settings, "WHATSAPP_APP_SECRET", "test_secret_key_12345")
        firma_correcta = _calcular_firma_hmac(cuerpo_bytes, secret)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"messages": [{"id": "wamid.out123"}]}

        with patch("apps.bot_asistente.services.TurnoBotService._esta_en_horario", return_value=True), \
             patch("requests.post", return_value=mock_resp) as mock_requests_post:
            response = client.post(
                url,
                data=cuerpo_json,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256=firma_correcta,
            )

        assert response.status_code == 200
        mock_requests_post.assert_called_once()

        # Verificar parámetros de llamada saliente a Meta
        args, kwargs = mock_requests_post.call_args
        url_llamada = args[0]
        assert "graph.facebook.com" in url_llamada
        assert getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "100200300") in url_llamada

        headers_enviados = kwargs.get("headers", {})
        assert "Bearer" in headers_enviados.get("Authorization", "")

        payload_enviado = kwargs.get("json", {})
        assert payload_enviado.get("messaging_product") == "whatsapp"
        assert payload_enviado.get("to") == "5491122334455"
        assert "text" in payload_enviado
