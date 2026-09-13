"""
Peluquería Lorena — Vistas del módulo de Servicios.

Implementa:
- Catálogo oficial de servicios, tarifas y duraciones.
- Control de servicios diarios por fecha y horario (personalización por clienta).
- Emisión y visualización de Consentimiento Informado (decoloración y alisado).
- Cierre diario de servicios y descuento masivo de insumos en stock.
- Endpoints de API REST para integración digital.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.inventario.models import Producto
from .forms import ConsentimientoInformadoForm, ServicioForm, ServicioRealizadoForm
from .models import ConsentimientoInformado, ConsumoInsumoCierre, Servicio, ServicioRealizado
from .serializers import ServicioSerializer
from .services import ServicioService


def es_admin_check(user) -> bool:
    return user.is_authenticated and user.es_administradora


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR — Catálogo de Servicios
# ──────────────────────────────────────────────────────────────


@login_required
def catalogo_servicios_view(request):
    """
    Muestra el catálogo oficial de servicios organizado por categorías.
    Permite cargar el tarifario inicial si el catálogo se encuentra vacío.
    """
    categoria_filtro = request.GET.get("categoria", "").strip()

    # Si se solicita sincronización inicial de precios oficiales
    if request.GET.get("cargar_inicial") == "1" and request.user.is_authenticated and request.user.es_administradora:
        cantidad = ServicioService.cargar_catalogo_inicial()
        messages.success(request, f"Se sincronizaron {cantidad} servicios de la lista oficial de Lorena.")
        return redirect("servicios:catalogo")

    # Si el catálogo está completamente vacío, precargar automáticamente
    if not Servicio.objects.exists():
        ServicioService.cargar_catalogo_inicial()

    servicios = ServicioService.listar_servicios(
        categoria=categoria_filtro if categoria_filtro else None
    )

    categorias = [
        (c.value, c.label) for c in Servicio.Categoria
    ]

    context = {
        "servicios": servicios,
        "categorias": categorias,
        "categoria_seleccionada": categoria_filtro,
        "total_servicios": servicios.count(),
    }
    return render(request, "servicios/catalogo.html", context)


@login_required
@user_passes_test(es_admin_check, login_url="servicios:catalogo")
def crear_servicio_view(request):
    """Alta de un nuevo servicio en el catálogo (solo Administradora)."""
    if request.method == "POST":
        form = ServicioForm(request.POST)
        if form.is_valid():
            servicio = form.save()
            messages.success(request, f"Servicio '{servicio.nombre}' añadido al catálogo.")
            return redirect("servicios:catalogo")
    else:
        form = ServicioForm()

    return render(request, "servicios/form_servicio.html", {"form": form, "accion": "Crear Servicio"})


@login_required
@user_passes_test(es_admin_check, login_url="servicios:catalogo")
def editar_servicio_view(request, pk: int):
    """Edición de un servicio del catálogo (solo Administradora)."""
    servicio = get_object_or_404(Servicio, pk=pk)

    if request.method == "POST":
        form = ServicioForm(request.POST, instance=servicio)
        if form.is_valid():
            form.save()
            messages.success(request, f"Servicio '{servicio.nombre}' actualizado correctamente.")
            return redirect("servicios:catalogo")
    else:
        form = ServicioForm(instance=servicio)

    return render(request, "servicios/form_servicio.html", {"form": form, "servicio": servicio, "accion": "Editar Servicio"})


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR — Control Diario de Servicios
# ──────────────────────────────────────────────────────────────


@login_required
def control_diario_servicios_view(request):
    """
    Control de los servicios que se realizan por día y horario.
    Muestra la bitácora con los precios cobrados, duraciones y estados.
    """
    fecha_str = request.GET.get("fecha")
    if fecha_str:
        try:
            dia = date.fromisoformat(fecha_str)
        except ValueError:
            dia = timezone.localdate()
    else:
        dia = timezone.localdate()

    servicios_hoy = ServicioService.listar_servicios_por_fecha(fecha=dia)
    
    total_recaudado = sum((s.precio_acordado for s in servicios_hoy if s.estado == ServicioRealizado.Estado.COMPLETADO), Decimal("0.00"))
    total_completados = servicios_hoy.filter(estado=ServicioRealizado.Estado.COMPLETADO).count()

    context = {
        "fecha": dia,
        "fecha_str": dia.isoformat(),
        "servicios": servicios_hoy,
        "total_servicios": servicios_hoy.count(),
        "total_completados": total_completados,
        "total_recaudado": total_recaudado,
    }
    return render(request, "servicios/control_diario.html", context)


@login_required
def registrar_servicio_realizado_view(request):
    """
    Registra un servicio para un cliente por día y horario,
    permitiendo personalizar el precio cobrado y la duración en minutos.

    Si viene de un turno agendado (?turno=<id>), precarga sus datos y,
    al guardar, vincula la atención de vuelta al turno (RF4.6), marcándolo
    como completado.
    """
    from apps.turnos.models import Turno
    from apps.turnos.services import TurnoError, TurnoService

    turno_id = request.POST.get("turno_id") or request.GET.get("turno")
    turno = Turno.objects.filter(pk=turno_id).first() if turno_id else None

    if request.method == "POST":
        form = ServicioRealizadoForm(request.POST)
        if form.is_valid():
            servicio_realizado = form.save()
            if turno is not None:
                try:
                    TurnoService.completar_turno(turno, servicio_realizado)
                except TurnoError as exc:
                    messages.warning(request, f"Servicio guardado, pero no se pudo vincular al turno: {exc}")
            messages.success(
                request,
                f"Servicio '{servicio_realizado.servicio.nombre}' asentado para {servicio_realizado.cliente_nombre}.",
            )
            return redirect("servicios:control_diario")
    else:
        # Valores iniciales
        servicio_id = request.GET.get("servicio")
        cliente_id = request.GET.get("cliente")
        initial_data: dict[str, Any] = {
            "fecha": timezone.localdate(),
            "hora": timezone.localtime().strftime("%H:%M"),
        }
        if turno is not None:
            initial_data.update(
                {
                    "cliente": turno.cliente,
                    "cliente_nombre": turno.cliente_nombre,
                    "cliente_telefono": turno.cliente_telefono,
                    "servicio": turno.servicio,
                    "profesional": turno.profesional,
                    "fecha": turno.fecha,
                    "hora": turno.hora,
                    "precio_acordado": turno.servicio.precio_base,
                    "duracion_minutos": turno.duracion_minutos,
                }
            )
        if cliente_id and turno is None:
            from apps.clientes.models import Cliente
            cli = Cliente.objects.filter(pk=cliente_id).first()
            if cli:
                initial_data["cliente"] = cli
                initial_data["cliente_nombre"] = cli.nombre
                initial_data["cliente_telefono"] = cli.telefono

        if servicio_id and turno is None:
            srv = ServicioService.obtener_servicio_por_id(int(servicio_id))
            if srv:
                initial_data["servicio"] = srv
                initial_data["precio_acordado"] = srv.precio_base
                initial_data["duracion_minutos"] = srv.duracion_estimada_minutos

        form = ServicioRealizadoForm(initial=initial_data)

    servicios_disponibles = Servicio.objects.filter(activo=True)
    servicios_data = {
        str(s.pk): {
            "precio": str(s.precio_base),
            "duracion": s.duracion_estimada_minutos,
        }
        for s in servicios_disponibles
    }
    return render(
        request,
        "servicios/form_servicio_realizado.html",
        {
            "form": form,
            "servicios_disponibles": servicios_disponibles,
            "servicios_data": servicios_data,
            "turno": turno,
        },
    )


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR — Ficha de Consentimiento Informado
# ──────────────────────────────────────────────────────────────


@login_required
def crear_consentimiento_view(request):
    """
    Genera una ficha de consentimiento informado para decoloración o alisado.
    """
    if request.method == "POST":
        form = ConsentimientoInformadoForm(request.POST)
        if form.is_valid():
            consentimiento = form.save(commit=False)
            if request.user.is_authenticated and not consentimiento.profesional:
                consentimiento.profesional = request.user
            consentimiento.save()
            messages.success(
                request,
                f"Consentimiento informado registrado exitosamente para {consentimiento.cliente_nombre}.",
            )
            return redirect("servicios:ver_consentimiento", pk=consentimiento.pk)
    else:
        initial_data = {}
        cliente_id = request.GET.get("cliente")
        if cliente_id:
            from apps.clientes.models import Cliente
            cliente_obj = Cliente.objects.filter(pk=cliente_id).first()
            if cliente_obj:
                initial_data["cliente"] = cliente_obj
                initial_data["cliente_nombre"] = cliente_obj.nombre
                initial_data["cliente_telefono"] = cliente_obj.telefono
        form = ConsentimientoInformadoForm(initial=initial_data)

    return render(request, "servicios/ficha_consentimiento.html", {"form": form})


@login_required
def ver_consentimiento_view(request, pk: int):
    """
    Visualiza la ficha de consentimiento legal/técnica en formato imprimible.
    """
    consentimiento = get_object_or_404(ConsentimientoInformado, pk=pk)
    return render(request, "servicios/ver_consentimiento.html", {"consentimiento": consentimiento})


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR — Cierre Diario y Descuento Masivo de Insumos
# ──────────────────────────────────────────────────────────────


@login_required
def cierre_diario_view(request):
    """
    Cierre al finalizar el día:
    1. Computa la cantidad de personas atendidas por cada servicio.
    2. Permite seleccionar los insumos utilizados y las cantidades.
    3. Descuenta automáticamente del stock del inventario.
    """
    fecha_str = request.GET.get("fecha")
    if fecha_str:
        try:
            dia = date.fromisoformat(fecha_str)
        except ValueError:
            dia = timezone.localdate()
    else:
        dia = timezone.localdate()

    if request.method == "POST":
        servicio_id = int(request.POST.get("servicio_id", 0))
        productos_ids = request.POST.getlist("producto_id[]")
        cantidades = request.POST.getlist("cantidad[]")

        insumos_para_descontar: list[dict[str, Any]] = []
        for p_id, cant in zip(productos_ids, cantidades):
            try:
                c_val = int(cant)
                if c_val > 0:
                    insumos_para_descontar.append({"producto_id": int(p_id), "cantidad": c_val})
            except ValueError:
                continue

        if insumos_para_descontar:
            try:
                ServicioService.descontar_insumos_cierre_dia(
                    servicio_id=servicio_id,
                    fecha=dia,
                    insumos=insumos_para_descontar,
                    usuario=request.user if request.user.is_authenticated else None,
                )
                messages.success(request, "Insumos descontados correctamente del stock del inventario.")
            except Exception as e:
                messages.error(request, f"Error al descontar insumos: {str(e)}")
        else:
            messages.warning(request, "No se especificaron cantidades válidas para descontar.")

        return redirect(f"{request.path}?fecha={dia.isoformat()}")

    resumen = ServicioService.obtener_resumen_servicios_dia(fecha=dia)
    productos_inventario = Producto.objects.filter(activo=True).order_by("nombre")
    consumos_realizados = ConsumoInsumoCierre.objects.filter(fecha=dia).select_related("servicio", "producto")

    context = {
        "fecha": dia,
        "fecha_str": dia.isoformat(),
        "resumen": resumen,
        "productos": productos_inventario,
        "consumos_realizados": consumos_realizados,
    }
    return render(request, "servicios/cierre_diario.html", context)


# ── Aliases camelCase para vistas Web ──
catalogoServiciosView = catalogo_servicios_view
controlDiarioServiciosView = control_diario_servicios_view
registrarServicioRealizadoView = registrar_servicio_realizado_view
crearConsentimientoView = crear_consentimiento_view
verConsentimientoView = ver_consentimiento_view
cierreDiarioView = cierre_diario_view


# ──────────────────────────────────────────────────────────────
# API REST (DRF)
# ──────────────────────────────────────────────────────────────


class ServicioViewSet(viewsets.ModelViewSet):
    """API REST CRUD para catálogo de servicios."""

    queryset = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
    serializer_class = ServicioSerializer
    permission_classes = [IsAuthenticated]
