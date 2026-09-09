"""
Agrega el campo `dni` al modelo Usuario y crea la cuenta de Administradora
inicial con datos genéricos.

La contraseña de acceso de cada usuario es su DNI. La cuenta inicial usa
datos placeholder ("00000000") que la dueña debe reemplazar por los reales
apenas ingrese al sistema (Panel de Gestión de Usuarios → editar).
"""
from django.contrib.auth.hashers import make_password
from django.db import migrations, models

EMAIL_ADMIN_INICIAL = "admin@peluquerialorena.com"
DNI_ADMIN_INICIAL = "00000000"


def crear_admin_inicial(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    # Si ya existe alguna administradora, no se hace nada.
    if Usuario.objects.filter(rol="ADMINISTRADORA").exists():
        return
    Usuario.objects.create(
        email=EMAIL_ADMIN_INICIAL,
        nombre="Administradora",
        dni=DNI_ADMIN_INICIAL,
        rol="ADMINISTRADORA",
        is_staff=True,
        is_superuser=True,
        is_active=True,
        password=make_password(DNI_ADMIN_INICIAL),
    )


def borrar_admin_inicial(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Usuario.objects.filter(
        email=EMAIL_ADMIN_INICIAL, dni=DNI_ADMIN_INICIAL
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="dni",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Documento Nacional de Identidad. Es la contraseña de "
                    "acceso del usuario (definida por la Administradora al "
                    "crear la cuenta)."
                ),
                max_length=15,
                null=True,
                unique=True,
                verbose_name="DNI",
            ),
        ),
        migrations.RunPython(crear_admin_inicial, borrar_admin_inicial),
    ]
