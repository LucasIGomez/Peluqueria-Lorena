"""
Peluquería Lorena — Comando para eliminar productos del inventario.

Uso:
    python manage.py eliminar_productos --todos
    python manage.py eliminar_productos --cantidad 50
    python manage.py eliminar_productos --todos --sin-confirmacion
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.inventario.models import MovimientoStock, Producto


class Command(BaseCommand):
    help = "Elimina productos y sus movimientos de stock asociados de forma segura."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cantidad",
            type=int,
            default=None,
            help="Número de productos más recientes a eliminar.",
        )
        parser.add_argument(
            "--todos",
            action="store_true",
            help="Elimina la totalidad de los productos e historial.",
        )
        parser.add_argument(
            "--sin-confirmacion",
            action="store_true",
            help="Ejecuta la eliminación sin solicitar confirmación interactiva.",
        )

    def handle(self, *args, **options):
        total_existente = Producto.objects.count()

        if total_existente == 0:
            self.stdout.write(self.style.NOTICE("No hay productos en el inventario para eliminar."))
            return

        cantidad = options["cantidad"]
        eliminar_todos = options["todos"] or (cantidad is None)

        if eliminar_todos:
            mensaje = f"Se van a eliminar TODOS los productos ({total_existente} productos)."
        else:
            cant_real = min(cantidad, total_existente)
            mensaje = f"Se van a eliminar los últimos {cant_real} productos creados (de {total_existente} totales)."

        self.stdout.write(self.style.WARNING(f"\n{mensaje}"))

        if not options["sin_confirmacion"]:
            confirmacion = input("¿Deseas continuar con la eliminación? (s/N): ")
            if confirmacion.lower() not in ["s", "si", "y", "yes"]:
                self.stdout.write(self.style.NOTICE("Operación cancelada. No se modificó ningún producto."))
                return

        with transaction.atomic():
            if eliminar_todos:
                mov_del, _ = MovimientoStock.objects.all().delete()
                prod_del, _ = Producto.objects.all().delete()
            else:
                cant_real = min(cantidad, total_existente)
                # Seleccionar los últimos productos creados por ID descendente
                ids_a_eliminar = list(
                    Producto.objects.order_by("-id")
                    .values_list("id", flat=True)[:cant_real]
                )
                mov_del, _ = MovimientoStock.objects.filter(producto_id__in=ids_a_eliminar).delete()
                prod_del, _ = Producto.objects.filter(id__in=ids_a_eliminar).delete()

        restantes = Producto.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✔ Eliminación completada:\n"
                f"  - Productos eliminados: {prod_del}\n"
                f"  - Movimientos asociados eliminados: {mov_del}\n"
                f"  - Productos restantes en inventario: {restantes}"
            )
        )
