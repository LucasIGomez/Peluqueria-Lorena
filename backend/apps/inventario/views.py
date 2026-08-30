from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Producto
from .forms import ProductoForm

def lista_productos(request):
    productos = Producto.objects.all().order_by('nombre')
    return render(request, 'inventario/lista_productos.html', {'productos': productos})

def crear_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto registrado exitosamente.')
            return redirect('inventario:lista_productos')
    else:
        form = ProductoForm()
    return render(request, 'inventario/form_producto.html', {'form': form, 'accion': 'Registrar'})

def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado exitosamente.')
            return redirect('inventario:lista_productos')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'inventario/form_producto.html', {'form': form, 'accion': 'Editar'})

def eliminar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto.delete()
        messages.success(request, 'Producto eliminado.')
        return redirect('inventario:lista_productos')
    return render(request, 'inventario/eliminar_producto.html', {'producto': producto})
