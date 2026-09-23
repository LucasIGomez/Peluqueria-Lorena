"""
Peluquería Lorena — Cliente de integración para Meta Cloud API (WhatsApp Business).

Envía mensajes salientes a las clientas usando la API Graph de Meta.
"""
from __future__ import annotations

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def enviar_mensaje_whatsapp(destinatario: str, texto: str) -> bool:
    """
    Envía un mensaje de texto por WhatsApp a través de la API oficial de Meta Cloud.

    Args:
        destinatario: Número de teléfono en formato E.164 (ej: '5491122334455').
        texto: Contenido del mensaje a enviar.

    Returns:
        bool: True si el mensaje fue aceptado por Meta (código 200/201), False en caso contrario.
    """
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")

    if not phone_number_id or not access_token:
        logger.warning(
            "No se puede enviar mensaje por WhatsApp: WHATSAPP_PHONE_NUMBER_ID o WHATSAPP_ACCESS_TOKEN no están configurados."
        )
        return False

    if not destinatario or not texto:
        logger.warning("Intento de envío de WhatsApp con destinatario o texto vacíos.")
        return False

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "text",
        "text": {"body": texto},
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in (200, 201):
            logger.info("Mensaje de WhatsApp enviado exitosamente a %s.", destinatario)
            return True

        logger.error(
            "Error devuelto por Meta Cloud API (%s): %s",
            response.status_code,
            response.text,
        )
        return False

    except requests.RequestException as exc:
        logger.error(
            "Falla de conexión al enviar mensaje de WhatsApp a %s: %s",
            destinatario,
            str(exc),
        )
        return False
