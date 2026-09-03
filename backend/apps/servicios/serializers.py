"""
Peluquería Lorena — Serializers del módulo de Servicios.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Servicio


class ServicioSerializer(serializers.ModelSerializer):
    """Serializer del catálogo de servicios para la API REST."""

    class Meta:
        model = Servicio
        fields = [
            "id",
            "nombre",
            "categoria",
            "precio_base",
            "duracion_estimada_minutos",
            "requiere_consentimiento",
            "descripcion",
            "activo",
        ]
