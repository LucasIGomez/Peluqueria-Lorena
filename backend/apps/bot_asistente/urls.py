from django.urls import path
from apps.bot_asistente.views import WhatsAppWebhookView

app_name = "bot_asistente"

urlpatterns = [
    path("webhook/", WhatsAppWebhookView.as_view(), name="webhook"),
]
