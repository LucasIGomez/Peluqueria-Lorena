"""
Peluquería Lorena — Comando para limpiar todos los productos e historial de stock.

Uso:
    python manage.py limpiar_inventario
    python manage.py limpiar_inventario --sin-confirmacion
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import MovimientoStock, Producto


class Command(BaseCommand):
    help = "Elimina de forma segura todos los productos y movimientos del inventario."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sin-confirmacion",
            action="store_true",
            help="Ejecuta el borrado sin solicitar confirmación interactiva.",
        )

    def handle(self, *args, **options):
        total_productos = Producto.objects.count()
        total_movimientos = MovimientoStock.objects.count()

        self.stdout.write(
            self.style.WARNING(
                f"\nSe encontraron {total_productos} productos y {total_movimientos} movimientos de stock registrados."
            )
        )

        if not options["sin_confirmacion"]:
            confirmacion = input("¿Estás seguro de que deseas eliminar TODOS los productos e historial? (s/N): ")
            if confirmacion.lower() not in ["s", "si", "y", "yes"]:
                self.stdout.write(self.style.NOTICE("Operación cancelada. No se modificó ningún dato."))
                return

        with transaction.atomic():
            # Eliminamos primero los movimientos por orden de dependencia (o cascada)
            movimientos_eliminados, _ = MovimientoStock.objects.all().delete()
            productos_eliminados, _ = Producto.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✔ Limpieza completada con éxito:\n"
                f"  - {movimientos_eliminados} movimientos de stock eliminados.\n"
                f"  - {productos_eliminados} productos eliminados.\n"
                f"El inventario ha quedado completamente en blanco y listo para usar."
            )
        )
