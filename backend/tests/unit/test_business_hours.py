"""
Peluquería Lorena — Pruebas unitarias para BusinessHoursValidator.
"""
from datetime import datetime
import pytest
from apps.bot_asistente.handlers.business_hours import BusinessHoursValidator


class TestBusinessHoursValidator:
    """Verifica que el bot respete estrictamente los días y horarios comerciales."""

    def test_horario_comercial_valido(self) -> None:
        """Martes a Sábado entre 09:00 y 19:00 está dentro del horario comercial."""
        # 2026-09-22 es Martes (weekday 1)
        martes_10am = datetime(2026, 9, 22, 10, 30)
        assert BusinessHoursValidator.esta_en_horario(martes_10am) is True

        # 2026-09-26 es Sábado (weekday 5)
        sabado_18pm = datetime(2026, 9, 26, 18, 0)
        assert BusinessHoursValidator.esta_en_horario(sabado_18pm) is True

    def test_fuera_de_horario_por_hora_temprana_o_tardia(self) -> None:
        """Mismo día comercial pero antes de las 09:00 o después de las 19:00."""
        martes_temprano = datetime(2026, 9, 22, 8, 30)
        assert BusinessHoursValidator.esta_en_horario(martes_temprano) is False

        miercoles_noche = datetime(2026, 9, 23, 19, 30)
        assert BusinessHoursValidator.esta_en_horario(miercoles_noche) is False

    def test_dias_cerrados_domingo_y_lunes(self) -> None:
        """Domingos (weekday 6) y Lunes (weekday 0) el salón permanece cerrado."""
        domingo = datetime(2026, 9, 20, 14, 0)
        assert BusinessHoursValidator.esta_en_horario(domingo) is False

        lunes = datetime(2026, 9, 21, 14, 0)
        assert BusinessHoursValidator.esta_en_horario(lunes) is False

    def test_mensaje_fuera_de_horario_es_cordial_y_especifica_dias(self) -> None:
        """El mensaje cordial debe indicar días (Martes a Sábado) y horarios de atención."""
        mensaje = BusinessHoursValidator.obtener_mensaje_fuera_de_horario()
        assert "Martes a Sábado" in mensaje
        assert "09:00" in mensaje
        assert "19:00" in mensaje
        assert "Peluquería Lorena" in mensaje
