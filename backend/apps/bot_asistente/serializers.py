from rest_framework import serializers


class WhatsAppWebhookPayloadSerializer(serializers.Serializer):
    """
    Serializador para validar y deserializar eventos entrantes desde Meta Cloud API (WhatsApp).
    Permite formato anidado estándar de Meta o formato simplificado para integraciones directas/tests.
    """
    object = serializers.CharField(required=False, default="whatsapp_business_account")
    entry = serializers.ListField(child=serializers.DictField(), required=False)

    # Campos directos de conveniencia (para pruebas o webhooks simplificados)
    from_number = serializers.CharField(required=False)
    text = serializers.CharField(required=False)

    def extraer_mensaje(self) -> dict:
        """
        Extrae el remitente y texto del mensaje entrante, contemplando formato estándar de Meta y simplificado.
        Retorna un dict con:
            - 'telefono': str
            - 'texto': str
            - 'nombre': str (opcional)
        """
        data = self.validated_data

        # Caso directo/simplificado
        if data.get("from_number") and data.get("text"):
            return {
                "telefono": data["from_number"],
                "texto": data["text"],
                "nombre": data.get("name", "Clienta")
            }

        # Formato oficial Meta Cloud API
        entries = data.get("entry", [])
        if entries:
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    contacts = value.get("contacts", [])
                    nombre = contacts[0].get("profile", {}).get("name", "Clienta") if contacts else "Clienta"

                    if messages:
                        msg = messages[0]
                        msg_type = msg.get("type", "text")
                        telefono = msg.get("from", "")

                        texto = ""
                        if msg_type == "text":
                            texto = msg.get("text", {}).get("body", "")
                        elif msg_type == "interactive":
                            interactive = msg.get("interactive", {})
                            if interactive.get("type") == "button_reply":
                                texto = interactive.get("button_reply", {}).get("id", "")
                            elif interactive.get("type") == "list_reply":
                                texto = interactive.get("list_reply", {}).get("id", "")

                        if telefono and texto:
                            return {
                                "telefono": telefono,
                                "texto": texto,
                                "nombre": nombre
                            }

        return {
            "telefono": "",
            "texto": "",
            "nombre": "Clienta"
        }
