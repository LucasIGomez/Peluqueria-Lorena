"""
Peluquería Lorena — Vistas de la aplicación principal y Dashboard.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .dashboard_service import DashboardService


@login_required
def dashboard_view(request):
    """
    Pantalla de inicio / Dashboard principal del sistema (RF 2).

    Muestra:
    - RF 2.1: Turnos del día
    - RF 2.2: Resumen de ingresos acumulados (día, semana, mes)
    - RF 2.3: Alertas de stock crítico y reposición
    - RF 2.4: Próximos turnos agendados
    - RF 2.5: Cumpleaños del mes en curso
    """
    context = DashboardService.obtener_metricas()
    return render(request, "index.html", context)


def modulo_en_desarrollo(request, nombre_modulo="Módulo"):
    """Renderiza vista informativa para módulos en desarrollo."""
    return render(
        request,
        "modulo_no_disponible.html",
        {"nombre_modulo": nombre_modulo},
    )
