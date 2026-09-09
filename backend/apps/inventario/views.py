"""
Peluquería Lorena — Vistas del módulo de Inventario.

Implementa las vistas web basadas en plantillas Django y los endpoints
de la API REST para cumplir con:
- RF 7.1: Gestión de productos (Alta, edición y baja).
- RF 7.2: Descuento manual de stock por consumo en servicios.
- RF 7.3: Alertas automáticas de stock mínimo.
- Agregar / Reponer Stock con trazabilidad y auditoría.
- Historial de movimientos con buscador inteligente.
"""
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import AgregarStockForm, ConsumoServicioForm, ProductoEditForm, ProductoForm
from .models import MovimientoStock, Producto
from .serializers import (
    DescuentoStockSerializer,
    MovimientoStockSerializer,
    ProductoSerializer,
)
from .services import (
    CantidadInvalidaError,
    InventarioError,
    InventarioService,
    ProductoNoEncontradoError,
    StockInsuficienteError,
)


# ──────────────────────────────────────────────────────────────
# Vistas Web (Django Templates + Bootstrap 5)
# ──────────────────────────────────────────────────────────────


@login_required
def lista_productos(request):
    """
    Lista todos los productos del inventario con buscador inteligente por nombre
    y filtros por estado crítico de stock.
    """
    busqueda = request.GET.get("q", "").strip()
    bajo_stock_only = request.GET.get("bajo_stock") == "1"

    productos = InventarioService.listar_productos(
        solo_activos=True,
        bajo_stock_only=bajo_stock_only,
        busqueda=busqueda if busqueda else None,
    )

    productos_bajo_stock = InventarioService.obtener_productos_bajo_stock()
    total_bajo_stock = productos_bajo_stock.count()
    total_activos = Producto.objects.filter(activo=True).count()
    
    ultimo_movimiento = MovimientoStock.objects.order_by("-fecha").first()

    context = {
        "productos": productos,
        "productos_bajo_stock": productos_bajo_stock,
        "total_bajo_stock": total_bajo_stock,
        "total_activos": total_activos,
        "filtro_bajo_stock": bajo_stock_only,
        "busqueda": busqueda,
        "ultimo_movimiento": ultimo_movimiento,
    }
    return render(request, "inventario/lista_productos.html", context)


@login_required
def crear_producto(request):
    """
    RF 7.1: Alta de un nuevo producto en el inventario.
    El usuario ingresa nombre, descripción, precio, stock inicial y stock mínimo.
    El sistema registra automáticamente el movimiento de alta en el historial.
    """
    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            try:
                producto = InventarioService.crear_producto(
                    nombre=form.cleaned_data["nombre"],
                    precio=form.cleaned_data["precio"],
                    stock_actual=form.cleaned_data["stock_actual"],
                    stock_minimo=form.cleaned_data["stock_minimo"],
                    descripcion=form.cleaned_data.get("descripcion"),
                    unidad_medida=form.cleaned_data.get("unidad_medida", "UNIDAD"),
                    usuario=request.user,
                )
                messages.success(
                    request,
                    f"Producto '{producto.nombre}' registrado exitosamente con stock inicial de {producto.stock_actual} {producto.unidad_abreviatura}.",
                )

                # RF 7.3: Alerta si se dio de alta con stock <= stock_minimo
                if producto.verificar_stock_minimo():
                    messages.warning(
                        request,
                        f"⚠️ Alerta: El producto '{producto.nombre}' se ha creado en nivel de stock mínimo o inferior ({producto.stock_actual}/{producto.stock_minimo}).",
                    )

                return redirect("inventario:lista_productos")
            except InventarioError as e:
                messages.error(request, str(e))
    else:
        form = ProductoForm()

    return render(
        request,
        "inventario/form_producto.html",
        {"form": form, "accion": "Registrar Nuevo"},
    )


@login_required
def editar_producto(request, pk: int):
    """
    RF 7.1: Edición de un producto existente.
    Permite modificar únicamente nombre, descripción, precio y stock mínimo.
    """
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == "POST":
        form = ProductoEditForm(request.POST, instance=producto)
        if form.is_valid():
            try:
                producto_original = Producto.objects.get(pk=pk)
                producto_actualizado = InventarioService.actualizar_producto(
                    producto=producto_original,
                    usuario=request.user,
                    nombre=form.cleaned_data["nombre"],
                    precio=form.cleaned_data["precio"],
                    stock_minimo=form.cleaned_data["stock_minimo"],
                    descripcion=form.cleaned_data.get("descripcion"),
                    unidad_medida=form.cleaned_data.get("unidad_medida", producto_original.unidad_medida),
                )
                messages.success(
                    request,
                    f"Producto '{producto_actualizado.nombre}' actualizado exitosamente.",
                )

                # RF 7.3: Alerta si el nuevo stock queda en nivel crítico
                if producto_actualizado.verificar_stock_minimo():
                    messages.warning(
                        request,
                        f"⚠️ Atención: El producto '{producto_actualizado.nombre}' se encuentra en stock mínimo ({producto_actualizado.stock_actual}/{producto_actualizado.stock_minimo}).",
                    )

                return redirect("inventario:lista_productos")
            except InventarioError as e:
                messages.error(request, str(e))
    else:
        form = ProductoEditForm(instance=producto)

    return render(
        request,
        "inventario/form_producto.html",
        {"form": form, "producto": producto, "accion": "Editar"},
    )


def _obtener_mapa_unidades_productos() -> dict[str, dict[str, Any]]:
    """Helper para serializar las unidades y métricas de productos para el frontend."""
    return {
        str(p.id): {
            "nombre": p.nombre,
            "unidad": p.unidad_medida,
            "plural": p.unidad_plural,
            "abreviatura": p.unidad_abreviatura,
            "display": p.get_unidad_medida_display(),
            "stock": p.stock_actual,
        }
        for p in Producto.objects.filter(activo=True).order_by("nombre")
    }


@login_required
def reponer_stock_view(request, pk: int | None = None):
    """
    Vista para agregar / reponer stock a un producto con registro de auditoría.
    """
    producto_inicial = None
    if pk:
        producto_inicial = get_object_or_404(Producto, pk=pk, activo=True)

    if request.method == "POST":
        form = AgregarStockForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data["producto"]
            cantidad = form.cleaned_data["cantidad"]
            motivo = form.cleaned_data.get("motivo")

            try:
                movimiento = InventarioService.reponer_stock(
                    producto_o_id=producto,
                    cantidad=cantidad,
                    motivo=motivo,
                    usuario=request.user,
                )
                messages.success(
                    request,
                    f"Stock agregado exitosamente: +{cantidad} {producto.unidad_abreviatura} de '{producto.nombre}'. Stock total: {movimiento.stock_posterior} {producto.unidad_abreviatura}.",
                )
                return redirect("inventario:lista_productos")
            except InventarioError as e:
                messages.error(request, str(e))
    else:
        initial_data = {}
        if producto_inicial:
            initial_data["producto"] = producto_inicial
        form = AgregarStockForm(initial=initial_data)

    return render(
        request,
        "inventario/reponer_stock.html",
        {
            "form": form,
            "producto_inicial": producto_inicial,
            "productos_unidades": _obtener_mapa_unidades_productos(),
        },
    )


@login_required
def descontar_stock_servicio(request, pk: int | None = None):
    """
    RF 7.2: Vista para registrar manualmente el consumo de stock al finalizar un servicio.
    RF 7.3: Dispara alerta automática si el producto alcanza el stock mínimo.
    """
    producto_inicial = None
    if pk:
        producto_inicial = get_object_or_404(Producto, pk=pk, activo=True)

    if request.method == "POST":
        form = ConsumoServicioForm(request.POST)
        if form.is_valid():
            producto = form.cleaned_data["producto"]
            cantidad = form.cleaned_data["cantidad"]
            detalle = form.cleaned_data["detalle_servicio"]

            try:
                movimiento, alerta_stock = InventarioService.registrar_consumo_servicio(
                    producto_o_id=producto,
                    cantidad=cantidad,
                    detalle_servicio=detalle,
                    usuario=request.user,
                )

                messages.success(
                    request,
                    f"Consumo registrado correctamente: -{cantidad} {producto.unidad_abreviatura} de '{producto.nombre}'. Stock restante: {movimiento.stock_posterior} {producto.unidad_abreviatura}.",
                )

                # RF 7.3: Generación de alerta automática inmediata
                if alerta_stock:
                    messages.warning(
                        request,
                        f"🚨 ¡ALERTA DE STOCK MÍNIMO! El producto '{producto.nombre}' alcanzó el nivel crítico ({movimiento.stock_posterior} restantes, stock mínimo: {producto.stock_minimo}). Por favor reponga el insumo a la brevedad.",
                    )

                return redirect("inventario:lista_productos")

            except StockInsuficienteError as e:
                messages.error(request, str(e))
            except InventarioError as e:
                messages.error(request, str(e))
    else:
        initial_data = {}
        if producto_inicial:
            initial_data["producto"] = producto_inicial
        form = ConsumoServicioForm(initial=initial_data)

    return render(
        request,
        "inventario/descontar_stock.html",
        {
            "form": form,
            "producto_inicial": producto_inicial,
            "productos_unidades": _obtener_mapa_unidades_productos(),
        },
    )


@login_required
def eliminar_producto(request, pk: int):
    """
    RF 7.1: Baja de un producto del catálogo (baja lógica por defecto o física).
    Registra el movimiento en el historial.
    """
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == "POST":
        modo_permanente = request.POST.get("permanente") == "1"
        nombre = producto.nombre
        InventarioService.eliminar_producto(producto, permanente=modo_permanente, usuario=request.user)
        messages.success(request, f"Producto '{nombre}' dado de baja exitosamente.")
        return redirect("inventario:lista_productos")

    return render(
        request,
        "inventario/eliminar_producto.html",
        {"producto": producto},
    )


@login_required
def historial_movimientos(request):
    """
    Vista de auditoría y trazabilidad de todos los movimientos de stock
    con buscador inteligente por nombre de producto.
    """
    busqueda = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "").strip()

    movimientos = InventarioService.obtener_historial_movimientos(
        tipo_movimiento=tipo if tipo else None,
        busqueda=busqueda if busqueda else None,
    )

    context = {
        "movimientos": movimientos,
        "busqueda": busqueda,
        "tipo_seleccionado": tipo,
        "tipos_movimiento": MovimientoStock.TipoMovimiento.choices,
    }
    return render(request, "inventario/historial_movimientos.html", context)


@login_required
def sugerencias_productos(request):
    """
    Retorna sugerencias en tiempo real (JSON) para las barras de búsqueda inteligente.
    """
    q = request.GET.get("q", "").strip()
    productos = Producto.objects.filter(activo=True)
    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(descripcion__icontains=q)
        )
    data = [
        {
            "id": p.id,
            "nombre": p.nombre,
            "precio": str(p.precio),
            "stock_actual": p.stock_actual,
            "stock_minimo": p.stock_minimo,
            "unidad_medida": p.unidad_medida,
            "unidad_abreviatura": p.unidad_abreviatura,
            "bajo_stock": p.verificar_stock_minimo(),
        }
        for p in productos[:8]
    ]
    return JsonResponse(data, safe=False)


# ──────────────────────────────────────────────────────────────
# API REST (DRF ViewSet)
# ──────────────────────────────────────────────────────────────


class ProductoViewSet(viewsets.ModelViewSet):
    """
    API REST para operaciones sobre productos del inventario.
    """

    queryset = Producto.objects.filter(activo=True).order_by("nombre")
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance: Producto) -> None:
        """Baja lógica por defecto con registro de auditoría."""
        InventarioService.dar_de_baja_producto(instance, usuario=self.request.user)

    @action(detail=False, methods=["get"], url_path="bajo-stock")
    def bajo_stock(self, request):
        """
        RF 7.3: Endpoint API que retorna la lista de productos en alerta de stock mínimo.
        """
        productos = InventarioService.obtener_productos_bajo_stock()
        serializer = self.get_serializer(productos, many=True)
        return Response(
            {
                "total_alertas": productos.count(),
                "productos": serializer.data,
            }
        )

    @action(detail=True, methods=["post"], url_path="descontar-servicio")
    def descontar_servicio(self, request, pk=None):
        """
        RF 7.2: Endpoint API para registrar consumo de stock de un servicio.
        """
        producto = self.get_object()
        serializer = DescuentoStockSerializer(
            data={"producto_id": producto.id, **request.data}
        )
        serializer.is_valid(raise_exception=True)

        try:
            movimiento, alerta = InventarioService.registrar_consumo_servicio(
                producto_o_id=producto,
                cantidad=serializer.validated_data["cantidad"],
                detalle_servicio=serializer.validated_data["motivo"],
                usuario=request.user,
            )
            return Response(
                {
                    "mensaje": "Consumo de stock registrado exitosamente.",
                    "movimiento": MovimientoStockSerializer(movimiento).data,
                    "alerta_stock_minimo": alerta,
                },
                status=status.HTTP_200_OK,
            )
        except StockInsuficienteError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except InventarioError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="reponer")
    def reponer(self, request, pk=None):
        """
        Endpoint API para reponer o agregar stock a un producto.
        """
        producto = self.get_object()
        cantidad = int(request.data.get("cantidad", 1))
        motivo = request.data.get("motivo", "Reposición vía API")

        try:
            movimiento = InventarioService.reponer_stock(
                producto_o_id=producto,
                cantidad=cantidad,
                motivo=motivo,
                usuario=request.user,
            )
            return Response(
                {
                    "mensaje": "Stock agregado exitosamente.",
                    "movimiento": MovimientoStockSerializer(movimiento).data,
                },
                status=status.HTTP_200_OK,
            )
        except InventarioError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="movimientos")
    def movimientos(self, request, pk=None):
        """
        Retorna el historial de movimientos de un producto específico.
        """
        producto = self.get_object()
        movimientos = InventarioService.obtener_historial_movimientos(producto_id=producto.pk)
        serializer = MovimientoStockSerializer(movimientos, many=True)
        return Response(serializer.data)
