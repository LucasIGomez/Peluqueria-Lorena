"""
Peluquería Lorena — Vistas del módulo de Caja y Ventas.

Tablero de caja diaria, registro de cobros con vista previa del descuento,
cierre diario (solo Administradora), reporte por medio de pago
y API REST de cobros y cierres.
"""
from __future__ import annotations

import io
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .facturacion import FacturaError, FacturaService
from .forms import CierreCajaForm, CobroForm, ReporteMediosForm
from .models import CierreCaja, Cobro
from .serializers import CierreCajaSerializer, CobroSerializer
from .services import CajaCerradaError, CajaError, CajaService, CobroInvalidoError


def es_admin_check(user) -> bool:
    return user.is_authenticated and user.es_administradora


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR
# ──────────────────────────────────────────────────────────────


@login_required
def caja_diaria_view(request):
    """Tablero de caja del día: cobros, resumen por medio y estado del cierre."""
    fecha_str = request.GET.get("fecha")
    if fecha_str:
        try:
            dia = date.fromisoformat(fecha_str)
        except ValueError:
            dia = timezone.localdate()
    else:
        dia = timezone.localdate()

    resumen = CajaService.resumen_caja_dia(fecha=dia)
    # Si se acaba de confirmar una venta (?factura=<pk>), la plantilla abre
    # el comprobante PDF en una pestaña nueva automáticamente.
    factura_pk = request.GET.get("factura") or ""
    factura_pk = factura_pk if factura_pk.isdigit() else ""
    context = {
        "fecha": dia,
        "fecha_str": dia.isoformat(),
        "resumen": resumen,
        "cobros": resumen["cobros"],
        # Ventas agrupadas: los ítems vendidos en conjunto comparten una fila.
        "ventas": FacturaService.agrupar_ventas(resumen["cobros"]),
        "factura_pk": factura_pk,
    }
    return render(request, "pagos/caja_diaria.html", context)


@login_required
def registrar_cobro_view(request):
    """Registra una venta con carrito de múltiples servicios y/o productos."""
    if CajaService.caja_esta_cerrada(timezone.localdate()) and request.method == "GET":
        messages.warning(request, "La caja de hoy ya fue cerrada.")

    if request.method == "POST":
        form = CobroForm(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                items = datos.get("items") or []
                fecha_cobro = datos.get("fecha") or timezone.localdate()
                if items:
                    from decimal import Decimal as _Decimal

                    cobros = CajaService.registrar_cobros_carrito(
                        items=items,
                        cliente_nombre=datos["cliente_nombre"],
                        profesional=datos["profesional"],
                        medio_pago=datos["medio_pago"],
                        cliente=datos.get("cliente"),
                        fecha=fecha_cobro,
                        observaciones=datos.get("observaciones", ""),
                        porcentaje_descuento=datos.get("porcentaje_descuento"),
                    )
                    total_general = sum((c.total for c in cobros), _Decimal("0.00"))
                    desc_total = sum((c.monto_descuento for c in cobros), _Decimal("0.00"))
                    primero = cobros[0]
                    if desc_total > 0:
                        messages.success(
                            request,
                            f"Venta registrada: {len(cobros)} ítems por ${total_general:,.2f} "
                            f"({primero.get_medio_pago_display()}, descuento "
                            f"{primero.porcentaje_descuento}%: -${desc_total:,.2f}).",
                        )
                    else:
                        messages.success(
                            request,
                            f"Venta registrada: {len(cobros)} ítems por ${total_general:,.2f} "
                            f"({primero.get_medio_pago_display()}).",
                        )
                    return redirect(f"/pagos/?fecha={fecha_cobro.isoformat()}&factura={cobros[0].pk}")
                # Compatibilidad con POST unitario (tests/API sin carrito).
                cobro = CajaService.registrar_cobro(
                    cliente_nombre=datos["cliente_nombre"],
                    profesional=datos["profesional"],
                    tipo=datos.get("tipo") or Cobro.Tipo.SERVICIO,
                    medio_pago=datos["medio_pago"],
                    cantidad=datos.get("cantidad") or 1,
                    precio_unitario=datos.get("precio_unitario"),
                    servicio=datos.get("servicio"),
                    servicio_realizado=None,
                    producto=datos.get("producto"),
                    cliente=datos.get("cliente"),
                    fecha=fecha_cobro,
                    observaciones=datos.get("observaciones", ""),
                    porcentaje_descuento=datos.get("porcentaje_descuento"),
                )
                if cobro.monto_descuento > 0:
                    messages.success(
                        request,
                        f"Cobro #{cobro.pk} registrado: ${cobro.total:,.2f} "
                        f"({cobro.get_medio_pago_display()}, descuento "
                        f"{cobro.porcentaje_descuento}%: -${cobro.monto_descuento:,.2f}).",
                    )
                else:
                    messages.success(
                        request,
                        f"Cobro #{cobro.pk} registrado: ${cobro.total:,.2f} "
                        f"({cobro.get_medio_pago_display()}).",
                    )
                return redirect(f"/pagos/?fecha={cobro.fecha.isoformat()}&factura={cobro.pk}")
            except (CobroInvalidoError, CajaCerradaError) as exc:
                messages.error(request, str(exc))
    else:
        initial = {
            "fecha": timezone.localdate(),
            "medio_pago": Cobro.MedioPago.EFECTIVO,
        }
        # Precompletar clienta o producto inicial si vienen por querystring.
        cliente_id = request.GET.get("cliente")
        if cliente_id:
            from apps.clientes.models import Cliente

            cli = Cliente.objects.filter(pk=cliente_id).first()
            if cli:
                initial["cliente"] = cli
                initial["cliente_nombre"] = cli.nombre
        form = CobroForm(initial=initial)

    from apps.inventario.models import Producto
    from apps.servicios.models import Servicio

    servicios = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
    productos = Producto.objects.filter(activo=True).order_by("nombre")

    servicios_data = {
        str(s.pk): {"precio": str(s.precio_base), "nombre": s.nombre}
        for s in servicios
    }
    productos_data = {
        str(p.pk): {
            "precio": str(p.precio),
            "nombre": p.nombre,
            "stock": p.stock_actual,
        }
        for p in productos
    }
    # Compatibilidad con el JS anterior (solo precios).
    servicios_precios = {k: v["precio"] for k, v in servicios_data.items()}
    productos_precios = {k: v["precio"] for k, v in productos_data.items()}

    # Ítem inicial si viene ?producto=<id> (precarga el carrito).
    item_inicial = None
    producto_id = request.GET.get("producto")
    if producto_id and str(producto_id) in productos_data:
        item_inicial = {
            "tipo": Cobro.Tipo.PRODUCTO,
            "producto_id": str(producto_id),
            "cantidad": 1,
            "precio_unitario": productos_data[str(producto_id)]["precio"],
        }

    return render(
        request,
        "pagos/form_cobro.html",
        {
            "form": form,
            "servicios_precios": servicios_precios,
            "productos_precios": productos_precios,
            "servicios_data": servicios_data,
            "productos_data": productos_data,
            "item_inicial": item_inicial,
        },
    )


@login_required
def anular_cobro_view(request, pk: int):
    """Anula un cobro vigente (repone stock si era venta de producto)."""
    cobro = get_object_or_404(Cobro, pk=pk)
    if request.method == "POST":
        try:
            CajaService.anular_cobro(cobro, usuario=request.user)
            messages.success(request, f"Cobro #{cobro.pk} anulado correctamente.")
        except (CobroInvalidoError, CajaCerradaError) as exc:
            messages.error(request, str(exc))
        return redirect(f"/pagos/?fecha={cobro.fecha.isoformat()}")
    return render(request, "pagos/confirmar_anulacion.html", {"cobro": cobro})


@login_required
def anular_venta_view(request, pk: int):
    """Anula todos los ítems de una venta en conjunto (repone stock)."""
    from decimal import Decimal as _Decimal

    cobro = get_object_or_404(Cobro, pk=pk)
    cobros = FacturaService.cobros_de_venta(cobro)
    if not cobros:
        messages.error(request, f"El cobro #{cobro.pk} ya se encuentra anulado.")
        return redirect(f"/pagos/?fecha={cobro.fecha.isoformat()}")
    if request.method == "POST":
        try:
            anulados = CajaService.anular_venta(cobros, usuario=request.user)
            total = sum((c.total for c in anulados), _Decimal("0.00"))
            messages.success(
                request,
                f"Venta anulada: {len(anulados)} ítems por ${total:,.2f}.",
            )
        except (CobroInvalidoError, CajaCerradaError) as exc:
            messages.error(request, str(exc))
        return redirect(f"/pagos/?fecha={cobro.fecha.isoformat()}")
    total = sum((c.total for c in cobros), _Decimal("0.00"))
    return render(
        request,
        "pagos/confirmar_anulacion_venta.html",
        {"cobros": cobros, "total": total},
    )


@login_required
def factura_pdf_view(request, pk: int):
    """Retorna el comprobante de venta en PDF para visualizar en el navegador."""
    cobro = get_object_or_404(Cobro, pk=pk)
    cobros = FacturaService.cobros_de_venta(cobro)
    if not cobros:
        messages.error(request, f"El cobro #{cobro.pk} está anulado y no admite comprobante.")
        return redirect(f"/pagos/?fecha={cobro.fecha.isoformat()}")
    try:
        pdf_data = FacturaService.generar_pdf(cobros)
    except FacturaError as exc:
        messages.error(request, str(exc))
        return redirect(f"/pagos/?fecha={cobro.fecha.isoformat()}")
    numero = FacturaService.numero_comprobante(cobros)
    respuesta = FileResponse(io.BytesIO(pdf_data), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'inline; filename="Factura_{numero}.pdf"'
    return respuesta


@login_required
@user_passes_test(es_admin_check, login_url="/pagos/")
def cierre_caja_view(request):
    """Muestra el consolidado del día y confirma el cierre (solo Administradora)."""
    fecha_str = request.GET.get("fecha") or request.POST.get("fecha")
    if fecha_str:
        try:
            dia = date.fromisoformat(fecha_str)
        except ValueError:
            dia = timezone.localdate()
    else:
        dia = timezone.localdate()

    resumen = CajaService.resumen_caja_dia(fecha=dia)

    if request.method == "POST":
        form = CierreCajaForm(request.POST)
        if form.is_valid():
            try:
                cierre = CajaService.realizar_cierre_caja(
                    fecha=form.cleaned_data["fecha"],
                    responsable=request.user,
                    observaciones=form.cleaned_data.get("observaciones", ""),
                )
                messages.success(
                    request,
                    f"Caja del {cierre.fecha.strftime('%d/%m/%Y')} cerrada: "
                    f"${cierre.total_general:,.2f} en {cierre.cantidad_cobros} cobros.",
                )
                return redirect(f"/pagos/?fecha={cierre.fecha.isoformat()}")
            except (CobroInvalidoError, CajaCerradaError) as exc:
                messages.error(request, str(exc))
    else:
        form = CierreCajaForm(initial={"fecha": dia})

    return render(
        request,
        "pagos/cierre.html",
        {"form": form, "resumen": resumen, "fecha": dia, "fecha_str": dia.isoformat()},
    )


@login_required
@user_passes_test(es_admin_check, login_url="/pagos/")
def reabrir_caja_view(request):
    """Reabre la caja de una fecha ya cerrada, para corregir cobros (solo Administradora)."""
    fecha_str = request.GET.get("fecha") or request.POST.get("fecha")
    if fecha_str:
        try:
            dia = date.fromisoformat(fecha_str)
        except ValueError:
            dia = timezone.localdate()
    else:
        dia = timezone.localdate()

    cierre = CierreCaja.objects.filter(fecha=dia).first()

    if request.method == "POST":
        try:
            CajaService.reabrir_caja(fecha=dia, usuario=request.user)
            messages.success(request, f"Caja del {dia.strftime('%d/%m/%Y')} reabierta correctamente.")
        except CajaError as exc:
            messages.error(request, str(exc))
        return redirect(f"/pagos/?fecha={dia.isoformat()}")

    return render(
        request,
        "pagos/reabrir.html",
        {"fecha": dia, "fecha_str": dia.isoformat(), "cierre": cierre},
    )


@login_required
@user_passes_test(es_admin_check, login_url="/pagos/")
def reporte_medios_view(request):
    """Reporte de ingresos discriminado por medio de pago (solo Administradora)."""
    if request.GET.get("fecha_desde"):
        form = ReporteMediosForm(request.GET)
    else:
        hoy = timezone.localdate()
        form = ReporteMediosForm(
            initial={"fecha_desde": hoy.replace(day=1), "fecha_hasta": hoy}
        )

    reporte = None
    if form.is_valid() and request.GET.get("fecha_desde"):
        try:
            reporte = CajaService.reporte_por_medio_pago(
                fecha_desde=form.cleaned_data["fecha_desde"],
                fecha_hasta=form.cleaned_data["fecha_hasta"],
            )
        except CobroInvalidoError as exc:
            messages.error(request, str(exc))

    return render(request, "pagos/reporte.html", {"form": form, "reporte": reporte})


# ── Aliases camelCase ──
cajaDiariaView = caja_diaria_view
registrarCobroView = registrar_cobro_view
anularCobroView = anular_cobro_view
cierreCajaView = cierre_caja_view
reabrirCajaView = reabrir_caja_view
reporteMediosView = reporte_medios_view


# ──────────────────────────────────────────────────────────────
# API REST (DRF)
# ──────────────────────────────────────────────────────────────


class CobroViewSet(viewsets.ModelViewSet):
    """API REST de cobros (el alta aplica descuento y stock vía servicio)."""

    queryset = Cobro.objects.filter(anulado=False).order_by("-fecha", "-fecha_creacion")
    serializer_class = CobroSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        datos = serializer.validated_data
        cobro = CajaService.registrar_cobro(
            cliente_nombre=datos.get("cliente_nombre", ""),
            profesional=self.request.user,
            tipo=datos.get("tipo", Cobro.Tipo.SERVICIO),
            medio_pago=datos.get("medio_pago", Cobro.MedioPago.EFECTIVO),
            cantidad=datos.get("cantidad", 1),
            precio_unitario=datos.get("precio_unitario"),
            fecha=datos.get("fecha") or timezone.localdate(),
            observaciones=datos.get("observaciones", ""),
        )
        serializer.instance = cobro


class CierreCajaViewSet(viewsets.ReadOnlyModelViewSet):
    """API REST de solo lectura para cierres de caja."""

    queryset = CierreCaja.objects.all().order_by("-fecha")
    serializer_class = CierreCajaSerializer
    permission_classes = [IsAuthenticated]
