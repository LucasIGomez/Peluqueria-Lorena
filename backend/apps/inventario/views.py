"""
Peluquería Lorena — Vistas del módulo de Inventario.

Implementa las vistas web basadas en plantillas Django y los endpoints
de la API REST para cumplir con:
- RF 7.1: Gestión de productos (Alta, edición y baja).
- RF 7.2: Descuento manual de stock por consumo en servicios.
- RF 7.3: Alertas automáticas de stock mínimo.
"""
from typing import Any

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import ConsumoServicioForm, ProductoForm
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


def lista_productos(request):
    """
    Lista todos los productos del inventario.

    Muestra indicadores clave, banner automático de alertas de stock mínimo (RF 7.3)
    y permite filtrar por término de búsqueda o productos en nivel crítico.
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
    
    ultimo_movimiento = MovimientoStock.objects.filter(tipo_movimiento=MovimientoStock.TipoMovimiento.CONSUMO_SERVICIO).order_by('-fecha').first()

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


def crear_producto(request):
    """
    RF 7.1: Alta de un nuevo producto en el inventario.
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
                )
                messages.success(
                    request,
                    f"Producto '{producto.nombre}' registrado exitosamente con stock inicial de {producto.stock_actual} u.",
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


def editar_producto(request, pk: int):
    """
    RF 7.1: Edición de un producto existente.
    """
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == "POST":
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            try:
                producto_actualizado = InventarioService.actualizar_producto(
                    producto=producto,
                    nombre=form.cleaned_data["nombre"],
                    precio=form.cleaned_data["precio"],
                    stock_actual=form.cleaned_data["stock_actual"],
                    stock_minimo=form.cleaned_data["stock_minimo"],
                    descripcion=form.cleaned_data.get("descripcion"),
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
        form = ProductoForm(instance=producto)

    return render(
        request,
        "inventario/form_producto.html",
        {"form": form, "producto": producto, "accion": "Editar"},
    )


def eliminar_producto(request, pk: int):
    """
    RF 7.1: Baja de un producto del catálogo (baja lógica por defecto o física).
    """
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == "POST":
        modo_permanente = request.POST.get("permanente") == "1"
        nombre = producto.nombre
        InventarioService.eliminar_producto(producto, permanente=modo_permanente)
        messages.success(request, f"Producto '{nombre}' dado de baja exitosamente.")
        return redirect("inventario:lista_productos")

    return render(
        request,
        "inventario/eliminar_producto.html",
        {"producto": producto},
    )


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
                    f"Consumo registrado correctamente: {cantidad} u. de '{producto.nombre}'. Stock restante: {movimiento.stock_posterior} u.",
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
        {"form": form, "producto_inicial": producto_inicial},
    )


def historial_movimientos(request):
    """
    Vista de auditoría y trazabilidad de todos los movimientos de stock.
    """
    producto_id = request.GET.get("producto")
    tipo = request.GET.get("tipo")

    producto_seleccionado = None
    if producto_id:
        try:
            producto_seleccionado = Producto.objects.get(pk=int(producto_id))
        except (ValueError, Producto.DoesNotExist):
            producto_seleccionado = None

    movimientos = InventarioService.obtener_historial_movimientos(
        producto_id=producto_seleccionado.pk if producto_seleccionado else None,
        tipo_movimiento=tipo if tipo else None,
    )

    context = {
        "movimientos": movimientos,
        "productos": Producto.objects.filter(activo=True).order_by("nombre"),
        "producto_seleccionado": producto_seleccionado,
        "tipo_seleccionado": tipo,
        "tipos_movimiento": MovimientoStock.TipoMovimiento.choices,
    }
    return render(request, "inventario/historial_movimientos.html", context)


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
        """Baja lógica por defecto."""
        InventarioService.dar_de_baja_producto(instance)

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

    @action(detail=True, methods=["get"], url_path="movimientos")
    def movimientos(self, request, pk=None):
        """
        Retorna el historial de movimientos de un producto específico.
        """
        producto = self.get_object()
        movimientos = InventarioService.obtener_historial_movimientos(producto_id=producto.pk)
        serializer = MovimientoStockSerializer(movimientos, many=True)
        return Response(serializer.data)
