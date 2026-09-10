"""
Script directo para generar productos de prueba en Peluquería Lorena.

Uso:
    python generar_productos.py
    python generar_productos.py 50
    python generar_productos.py 20 --limpiar
"""
import os
import sys
import argparse
import random
from decimal import Decimal

# Configurar entorno de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.db import models, transaction
from django.utils import timezone
from apps.inventario.models import MovimientoStock, Producto
from apps.inventario.management.commands.generar_productos import CATALOGO_BASE


def generar(cantidad=50, limpiar=False):
    if cantidad <= 0:
        print("La cantidad debe ser mayor a 0.")
        return

    if limpiar:
        print("Limpiando inventario antes de generar...")
        with transaction.atomic():
            MovimientoStock.objects.all().delete()
            Producto.objects.all().delete()
        print("✔ Inventario anterior limpiado.")

    print(f"Generando {cantidad} productos en la base de datos...")

    creados = 0
    total_catalogo = len(CATALOGO_BASE)

    with transaction.atomic():
        for i in range(cantidad):
            base = CATALOGO_BASE[i % total_catalogo]
            ciclo = i // total_catalogo

            nombre = base["nombre"]
            if ciclo > 0:
                nombre = f"{nombre} (Lote #{ciclo + 1})"

            unidad = base["unidad"]
            precio = Decimal(str(base["precio"]))

            r = random.random()
            if unidad == "UNIDAD":
                stock_min = random.choice([3, 5, 8, 10])
                if r < 0.10:
                    stock_act = 0
                elif r < 0.30:
                    stock_act = random.randint(1, stock_min)
                else:
                    stock_act = random.randint(stock_min + 2, stock_min + 30)
            elif unidad in ["LITRO", "KG"]:
                stock_min = random.choice([2, 3, 5])
                if r < 0.10:
                    stock_act = 0
                elif r < 0.30:
                    stock_act = random.randint(1, stock_min)
                else:
                    stock_act = random.randint(stock_min + 1, stock_min + 15)
            else:  # ML, G
                stock_min = random.choice([100, 200, 500])
                if r < 0.10:
                    stock_act = 0
                elif r < 0.30:
                    stock_act = random.randint(50, stock_min)
                else:
                    stock_act = random.randint(stock_min + 100, stock_min + 2500)

            producto = Producto.objects.create(
                nombre=nombre,
                descripcion=base.get("desc", ""),
                precio=precio,
                stock_actual=stock_act,
                stock_minimo=stock_min,
                unidad_medida=unidad,
                activo=True,
                creado_en=timezone.now(),
            )

            MovimientoStock.objects.create(
                producto=producto,
                tipo_movimiento=MovimientoStock.TipoMovimiento.ALTA_PRODUCTO,
                cantidad=stock_act,
                stock_previo=0,
                stock_posterior=stock_act,
                motivo=f"Alta inicial en catálogo ({stock_act} {producto.unidad_abreviatura}).",
                fecha=timezone.now(),
            )
            creados += 1

    total_actual = Producto.objects.count()
    print(f"\n✔ ¡Generación completada exitosamente!")
    print(f"  - Productos creados: {creados}")
    print(f"  - Total actual en base de datos: {total_actual}")
    print("Todos los productos cuentan con métricas, precios y trazabilidad en el historial.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generar productos de prueba en Peluquería Lorena.")
    parser.add_argument("cantidad_posicional", nargs="?", type=int, default=None, help="Cantidad de productos a generar (ej: 50).")
    parser.add_argument("--cantidad", "-c", type=int, default=None, help="Cantidad de productos a generar (ej: 50).")
    parser.add_argument("--limpiar", "-l", action="store_true", help="Elimina los productos anteriores antes de generar.")

    args = parser.parse_args()
    cantidad = args.cantidad or args.cantidad_posicional or 50

    generar(cantidad=cantidad, limpiar=args.limpiar)
