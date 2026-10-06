"""
Peluquería Lorena — Utilidades compartidas entre los módulos.
"""
from __future__ import annotations

from typing import Any


def entero_o_none(valor: Any) -> int | None:
    """Convierte un parámetro recibido (URL o formulario) en un id entero válido, o None."""
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if 0 < numero < 2**63 else None
