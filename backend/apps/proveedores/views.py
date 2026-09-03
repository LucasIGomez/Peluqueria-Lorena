from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Proveedor
from .forms import ProveedorForm
from apps.inventario.models import Producto
from apps.inventario.services import InventarioService, InventarioError
import json
from django.http import JsonResponse

@login_required
def lista_proveedores(request):
    proveedores = Proveedor.objects.all().order_by('nombre')
    return render(request, 'proveedores/lista_proveedores.html', {'proveedores': proveedores})

@login_required
def crear_proveedor(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor registrado exitosamente.')
            return redirect('proveedores:lista_proveedores')
    else:
        form = ProveedorForm()
    return render(request, 'proveedores/form_proveedor.html', {'form': form, 'accion': 'Registrar'})

@login_required
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado exitosamente.')
            return redirect('proveedores:lista_proveedores')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'proveedores/form_proveedor.html', {'form': form, 'accion': 'Editar'})

@login_required
def eliminar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.delete()
        messages.success(request, 'Proveedor eliminado.')
        return redirect('proveedores:lista_proveedores')
    return render(request, 'proveedores/eliminar_proveedor.html', {'proveedor': proveedor})

@login_required
def generar_orden(request):
    proveedores = Proveedor.objects.all().order_by('nombre')
    productos = Producto.objects.filter(activo=True).order_by('nombre')
    return render(request, 'proveedores/generar_orden.html', {
        'proveedores': proveedores,
        'productos': productos,
    })

@login_required
def crear_producto_ajax(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            producto = InventarioService.crear_producto(
                nombre=data.get('nombre'),
                descripcion=data.get('descripcion'),
                precio=data.get('precio', 0),
                stock_actual=0,
                stock_minimo=data.get('stock_minimo', 5),
                usuario=request.user
            )
            return JsonResponse({'id': producto.pk, 'nombre': producto.nombre})
        except InventarioError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': 'Error inesperado.'}, status=500)
    return JsonResponse({'error': 'Método no permitido'}, status=405)
