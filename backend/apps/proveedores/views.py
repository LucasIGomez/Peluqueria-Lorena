from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Proveedor
from .forms import ProveedorForm
from apps.inventario.models import Producto
from apps.inventario.services import InventarioService, InventarioError
import json
import io
import os
import subprocess
import tempfile
import shutil
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

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
def descargar_orden_compra(request):
    """
    Genera y descarga el archivo Word (.docx) de la Orden de Compra
    a partir de la plantilla adaptada para Peluquería Lorena.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Datos JSON inválidos.'}, status=400)

    proveedor_id = data.get('proveedor_id')
    items_raw = data.get('productos', [])

    if not items_raw:
        return JsonResponse({'error': 'La orden de compra no contiene productos.'}, status=400)

    proveedor = None
    if proveedor_id:
        proveedor = Proveedor.objects.filter(pk=proveedor_id).first()

    # Datos institucionales del salón / dueña (configurados en settings.DATOS_PELUQUERIA)
    datos_salon = getattr(settings, 'DATOS_PELUQUERIA', {})
    duena_nombre = datos_salon.get('NOMBRE_DUENA', 'Lorena Yanil Ortigoza')
    duena_cuit = datos_salon.get('CUIT_DUENA', '27-29327958-1')
    peluqueria_telefono = datos_salon.get('TELEFONO', '+54 9 297 534-9278')
    duena_email = datos_salon.get('EMAIL', 'lrnortigoza@gmail.com')
    fecha_emision = timezone.now().strftime('%d/%m/%Y')

    proveedor_nombre = proveedor.nombre if proveedor else "Sin asignar"
    proveedor_contacto = proveedor.contacto if (proveedor and proveedor.contacto) else "No especificado"

    productos = []
    for item in items_raw:
        cantidad = item.get('cantidad', 1)
        unidad = str(item.get('unidad') or '').strip()
        nombre = str(item.get('nombre', '')).strip()
        productos.append({
            'nombre': nombre,
            'cantidad': f"{cantidad} {unidad}".strip() if unidad else cantidad,
            'cantidad_num': cantidad,
            'unidad': unidad,
        })

    # Rutas candidatas para la plantilla Word
    rutas_plantilla = [
        os.path.join(settings.BASE_DIR, 'apps', 'proveedores', 'templates_docx', 'plantilla_orden_compra.docx'),
        os.path.join(settings.BASE_DIR.parent, 'plantilla_orden_compra.docx'),
        os.path.join(settings.BASE_DIR.parent, 'plantilla_factura.docx'),
    ]

    plantilla_encontrada = None
    for ruta in rutas_plantilla:
        if os.path.exists(ruta):
            plantilla_encontrada = ruta
            break

    if not plantilla_encontrada:
        return JsonResponse({'error': 'No se encontró la plantilla Word de orden de compra en el servidor.'}, status=500)

    try:
        from docxtpl import DocxTemplate
    except ImportError:
        return JsonResponse({
            'error': "La librería 'docxtpl' no está instalada en el entorno virtual. Ejecuta 'pip install -r requirements.txt' en el servidor."
        }, status=500)

    try:
        doc = DocxTemplate(plantilla_encontrada)
        contexto = {
            'duena_nombre': duena_nombre,
            'duena_cuit': duena_cuit,
            'peluqueria_telefono': peluqueria_telefono,
            'duena_email': duena_email,
            'fecha_emision': fecha_emision,
            'proveedor_nombre': proveedor_nombre,
            'proveedor_contacto': proveedor_contacto,
            'productos': productos,
        }
        doc.render(contexto)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_docx = os.path.join(temp_dir, "orden.docx")
            doc.save(temp_docx)

            cmd_libreoffice = shutil.which('libreoffice') or shutil.which('soffice')
            if not cmd_libreoffice:
                return JsonResponse({
                    'error': "LibreOffice no está instalado en el servidor para convertir a PDF. Ejecuta en la terminal de la YOGA: sudo apt install -y libreoffice-writer-nogui"
                }, status=500)

            # Ejecutar conversión headless de LibreOffice
            res = subprocess.run(
                [cmd_libreoffice, '--headless', '--convert-to', 'pdf', temp_docx, '--outdir', temp_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30
            )

            temp_pdf = os.path.join(temp_dir, "orden.pdf")
            if not os.path.exists(temp_pdf):
                err_msg = res.stderr.decode('utf-8', errors='ignore') or 'Error en la conversión con LibreOffice.'
                return JsonResponse({'error': f'No se pudo generar el PDF: {err_msg}'}, status=500)

            with open(temp_pdf, 'rb') as f:
                pdf_data = f.read()

            nombre_archivo = f"Orden_Compra_{slugify(proveedor_nombre)}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
            return response
    except Exception as e:
        return JsonResponse({'error': f'Error al procesar la orden: {str(e)}'}, status=500)

@login_required
def crear_producto_ajax(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            unidad = (data.get('unidad_medida') or 'UNIDAD')
            unidades_validas = {c[0] for c in Producto.UnidadMedida.choices}
            if unidad not in unidades_validas:
                return JsonResponse({'error': 'Unidad de medida inválida.'}, status=400)
            producto = InventarioService.crear_producto(
                nombre=data.get('nombre'),
                descripcion=data.get('descripcion'),
                precio=data.get('precio', 0),
                stock_actual=0,
                stock_minimo=data.get('stock_minimo', 5),
                unidad_medida=unidad,
                usuario=request.user
            )
            return JsonResponse({
                'id': producto.pk,
                'nombre': producto.nombre,
                'unidad_medida': producto.unidad_medida,
                'unidad_display': producto.get_unidad_medida_display(),
                'unidad_abreviatura': producto.unidad_abreviatura,
            })
        except InventarioError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': 'Error inesperado.'}, status=500)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

