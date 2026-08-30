"""
Peluquería Lorena — Permisos personalizados para el módulo de Usuarios.

Define clases de permisos basados en rol para proteger
los endpoints de la API.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import Usuario


class EsAdministradora(BasePermission):
    """
    Permite acceso solo a usuarios con rol ADMINISTRADORA.

    Se usa para endpoints de gestión: CRUD de usuarios,
    cierre de caja, gestión de proveedores, reportes, etc.
    """

    message = "Solo las administradoras pueden realizar esta acción."

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Verifica que el usuario autenticado sea Administradora."""
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.rol == Usuario.Rol.ADMINISTRADORA


class EsEmpleadaOAdministradora(BasePermission):
    """
    Permite acceso a usuarios con rol EMPLEADA o ADMINISTRADORA.

    Se usa para endpoints operativos: agenda, cobros, trabajos, etc.
    """

    message = "Debe ser empleada o administradora para realizar esta acción."

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Verifica que el usuario autenticado sea Empleada o Administradora."""
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.rol in (
            Usuario.Rol.EMPLEADA,
            Usuario.Rol.ADMINISTRADORA,
        )
