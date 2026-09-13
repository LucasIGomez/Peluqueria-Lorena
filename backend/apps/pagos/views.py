"""
Peluquería Lorena — Vistas del módulo de Caja y Ventas.

Tablero de caja diaria, registro de cobros con vista previa del descuento,
cierre diario (solo Administradora), reporte por medio de pago
y API REST de cobros y cierres.
"""
from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

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
    context = {
        "fecha": dia,
        "fecha_str": dia.isoformat(),
        "resumen": resumen,
        "cobros": resumen["cobros"],
    }
    return render(request, "pagos/caja_diaria.html", context)


@login_required
def registrar_cobro_view(request):
    """Registra el cobro de un servicio o la venta de un producto."""
    if CajaService.caja_esta_cerrada(timezone.localdate()) and request.method == "GET":
        messages.warning(request, "La caja de hoy ya fue cerrada.")

    if request.method == "POST":
        form = CobroForm(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                cobro = CajaService.registrar_cobro(
                    cliente_nombre=datos["cliente_nombre"],
                    profesional=datos["profesional"],
                    tipo=datos["tipo"],
                    medio_pago=datos["medio_pago"],
                    cantidad=datos["cantidad"],
                    precio_unitario=datos.get("precio_unitario"),
                    servicio=datos.get("servicio"),
                    servicio_realizado=datos.get("servicio_realizado"),
                    producto=datos.get("producto"),
                    cliente=datos.get("cliente"),
                    fecha=datos.get("fecha") or timezone.localdate(),
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
                return redirect(f"/pagos/?fecha={cobro.fecha.isoformat()}")
            except (CobroInvalidoError, CajaCerradaError) as exc:
                messages.error(request, str(exc))
    else:
        initial = {
            "fecha": timezone.localdate(),
            "cantidad": 1,
            "medio_pago": Cobro.MedioPago.EFECTIVO,
            "tipo": Cobro.Tipo.SERVICIO,
        }
        # Precompletar desde una atención o clienta si vienen por querystring.
        servicio_realizado_id = request.GET.get("atencion")
        if servicio_realizado_id:
            from apps.servicios.models import ServicioRealizado

            atencion = ServicioRealizado.objects.filter(pk=servicio_realizado_id).first()
            if atencion:
                initial.update(
                    {
                        "servicio_realizado": atencion,
                        "servicio": atencion.servicio,
                        "cliente": atencion.cliente,
                        "cliente_nombre": atencion.cliente_nombre,
                        "precio_unitario": atencion.precio_acordado,
                    }
                )
        cliente_id = request.GET.get("cliente")
        if cliente_id and not initial.get("cliente_nombre"):
            from apps.clientes.models import Cliente

            cli = Cliente.objects.filter(pk=cliente_id).first()
            if cli:
                initial["cliente"] = cli
                initial["cliente_nombre"] = cli.nombre
        producto_id = request.GET.get("producto")
        if producto_id:
            from apps.inventario.models import Producto

            prod = Producto.objects.filter(pk=producto_id).first()
            if prod:
                initial.update(
                    {
                        "tipo": Cobro.Tipo.PRODUCTO,
                        "producto": prod,
                        "precio_unitario": prod.precio,
                    }
                )
        form = CobroForm(initial=initial)

    from apps.inventario.models import Producto
    from apps.servicios.models import Servicio, ServicioRealizado

    servicios = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
    productos = Producto.objects.filter(activo=True).order_by("nombre")
    atenciones = ServicioRealizado.objects.filter(
        fecha=timezone.localdate(), estado=ServicioRealizado.Estado.COMPLETADO
    ).order_by("-hora")[:50]

    servicios_precios = {str(s.pk): str(s.precio_base) for s in servicios}
    productos_precios = {str(p.pk): str(p.precio) for p in productos}
    atenciones_data = {
        str(a.pk): {
            "precio": str(a.precio_acordado),
            "cliente": a.cliente_nombre,
            "servicio": a.servicio_id,
        }
        for a in atenciones
    }

    return render(
        request,
        "pagos/form_cobro.html",
        {
            "form": form,
            "servicios_precios": servicios_precios,
            "productos_precios": productos_precios,
            "atenciones_data": atenciones_data,
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
