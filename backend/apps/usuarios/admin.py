"""
Peluquería Lorena — Registro del modelo Usuario en Django Admin.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """Configuración del panel de administración para Usuario."""

    list_display = ("email", "nombre", "rol", "is_active", "date_joined")
    list_filter = ("rol", "is_active", "is_staff")
    search_fields = ("email", "nombre")
    ordering = ("-date_joined",)

    # Campos en el formulario de edición
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Información personal", {"fields": ("nombre",)}),
        (
            "Permisos",
            {
                "fields": (
                    "rol",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )

    # Campos en el formulario de creación
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nombre",
                    "rol",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
