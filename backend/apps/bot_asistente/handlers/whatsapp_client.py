"""
Peluquería Lorena — Cliente de integración para Meta Cloud API (WhatsApp Business).

Gestiona la comunicación saliente con la API oficial de WhatsApp:
- Envío de mensajes de texto simple.
- Envío de mensajes interactivos con botones (Quick Reply).
- Envío de listas interactivas.
- Confirmación de lectura (marcar mensaje como leído / doble tilde azul).
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppCloudApiClient:
    """
    Cliente oficial para interactuar con Meta Cloud API (Graph API v19.0+).
    """

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
        api_version: str = "v19.0",
    ) -> None:
        self.phone_number_id = phone_number_id or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
        self.access_token = access_token or getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        self.api_version = api_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    @property
    def esta_configurado(self) -> bool:
        """Determina si las credenciales de conexión con Meta están cargadas."""
        return bool(self.phone_number_id and self.access_token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _post(self, endpoint: str, payload: dict[str, Any]) -> bool:
        if not self.esta_configurado:
            logger.warning(
                "WhatsAppCloudApiClient no configurado: falta WHATSAPP_PHONE_NUMBER_ID o WHATSAPP_ACCESS_TOKEN."
            )
            return False

        url = f"{self.base_url}/{self.phone_number_id}/{endpoint}"
        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=10)
            if response.status_code in (200, 201):
                return True

            logger.error(
                "Meta Cloud API error (%s) en %s: %s",
                response.status_code,
                endpoint,
                response.text,
            )
            return False
        except requests.RequestException as exc:
            logger.error("Error de conexión con Meta Cloud API en %s: %s", endpoint, str(exc))
            return False

    def enviar_texto(self, destinatario: str, texto: str) -> bool:
        """Envía un mensaje de texto plano a un número de WhatsApp (formato internacional)."""
        if not destinatario or not texto:
            return False

        payload = {
            "messaging_product": "whatsapp",
            "to": destinatario,
            "type": "text",
            "text": {"body": texto},
        }
        return self._post("messages", payload)

    def enviar_botones(
        self,
        destinatario: str,
        texto_cuerpo: str,
        botones: List[tuple[str, str]],
    ) -> bool:
        """
        Envía un mensaje con hasta 3 botones de respuesta rápida (Quick Reply).
        botones: lista de tuplas (id_boton, titulo_boton), ej: [("1", "Confirmar"), ("2", "Cancelar")]
        """
        if not destinatario or not texto_cuerpo or not botones:
            return False

        botones_payload = []
        for boton_id, boton_titulo in botones[:3]:
            botones_payload.append(
                {
                    "type": "reply",
                    "reply": {
                        "id": boton_id,
                        "title": boton_titulo[:20],  # Meta limita títulos a 20 caracteres
                    },
                }
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": destinatario,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto_cuerpo},
                "action": {"buttons": botones_payload},
            },
        }
        return self._post("messages", payload)

    def marcar_como_leido(self, message_id: str) -> bool:
        """Marca un mensaje entrante como leído (doble tilde azul)."""
        if not message_id or not self.esta_configurado:
            return False

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return self._post("messages", payload)


def enviar_mensaje_whatsapp(destinatario: str, texto: str) -> bool:
    """
    Fachada directa para compatibilidad con vistas y servicios existentes.
    """
    cliente = WhatsAppCloudApiClient()
    return cliente.enviar_texto(destinatario=destinatario, texto=texto)
