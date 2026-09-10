"""
Script directo para eliminar productos en Peluquería Lorena.

Uso:
    python eliminar_productos.py                 (elimina todos con confirmación)
    python eliminar_productos.py 50              (elimina los últimos 50 productos)
    python eliminar_productos.py --todos --si    (elimina todos sin pedir confirmación)
"""
import os
import sys
import argparse

# Configurar entorno de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.db import transaction
from apps.inventario.models import MovimientoStock, Producto


def eliminar(cantidad=None, todos=False, sin_confirmacion=False):
    total_existente = Producto.objects.count()

    if total_existente == 0:
        print("No hay productos en el inventario para eliminar.")
        return

    eliminar_todos = todos or (cantidad is None)

    if eliminar_todos:
        mensaje = f"Se van a eliminar TODOS los productos ({total_existente} productos)."
    else:
        cant_real = min(cantidad, total_existente)
        mensaje = f"Se van a eliminar los últimos {cant_real} productos creados (de {total_existente} totales)."

    print(f"\n{mensaje}")

    if not sin_confirmacion:
        confirmacion = input("¿Deseas continuar con la eliminación? (s/N): ")
        if confirmacion.lower() not in ["s", "si", "y", "yes"]:
            print("Operación cancelada. No se modificó ningún dato.")
            return

    with transaction.atomic():
        if eliminar_todos:
            mov_del, _ = MovimientoStock.objects.all().delete()
            prod_del, _ = Producto.objects.all().delete()
        else:
            cant_real = min(cantidad, total_existente)
            ids_a_eliminar = list(
                Producto.objects.order_by("-id")
                .values_list("id", flat=True)[:cant_real]
            )
            mov_del, _ = MovimientoStock.objects.filter(producto_id__in=ids_a_eliminar).delete()
            prod_del, _ = Producto.objects.filter(id__in=ids_a_eliminar).delete()

    restantes = Producto.objects.count()
    print(f"\n✔ Eliminación completada:")
    print(f"  - Productos eliminados: {prod_del}")
    print(f"  - Movimientos asociados eliminados: {mov_del}")
    print(f"  - Productos restantes en inventario: {restantes}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Eliminar productos del inventario de Peluquería Lorena.")
    parser.add_argument("cantidad_posicional", nargs="?", type=int, default=None, help="Cantidad de productos a eliminar (ej: 50).")
    parser.add_argument("--cantidad", "-c", type=int, default=None, help="Cantidad de productos a eliminar.")
    parser.add_argument("--todos", "-t", action="store_true", help="Eliminar todos los productos.")
    parser.add_argument("--si", "-y", "--sin-confirmacion", dest="sin_confirmacion", action="store_true", help="Omitir confirmación.")

    args = parser.parse_args()
    cant = args.cantidad if args.cantidad is not None else args.cantidad_posicional

    eliminar(cantidad=cant, todos=args.todos, sin_confirmacion=args.sin_confirmacion)
