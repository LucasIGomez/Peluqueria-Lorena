from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Proveedor
from .forms import ProveedorForm

def lista_proveedores(request):
    proveedores = Proveedor.objects.all().order_by('nombre')
    return render(request, 'proveedores/lista_proveedores.html', {'proveedores': proveedores})

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

def eliminar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.delete()
        messages.success(request, 'Proveedor eliminado.')
        return redirect('proveedores:lista_proveedores')
    return render(request, 'proveedores/eliminar_proveedor.html', {'proveedor': proveedor})
