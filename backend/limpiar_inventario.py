"""
Script directo para limpiar productos e historial de stock en Peluquería Lorena.

Uso:
    python limpiar_inventario.py
"""
import os
import sys
import django

# Configurar entorno de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from apps.inventario.models import MovimientoStock, Producto
from django.db import transaction

def limpiar():
    total_prod = Producto.objects.count()
    total_mov = MovimientoStock.objects.count()
    print(f"Estado actual: {total_prod} productos, {total_mov} movimientos de stock.")
    
    with transaction.atomic():
        mov_del, _ = MovimientoStock.objects.all().delete()
        prod_del, _ = Producto.objects.all().delete()
        
    print(f"✔ Limpieza exitosa: {prod_del} productos y {mov_del} movimientos eliminados.")
    print("El inventario está listo y limpio.")

if __name__ == "__main__":
    limpiar()
