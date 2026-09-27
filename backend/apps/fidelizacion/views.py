"""
Peluquería Lorena — Vistas del módulo de Beneficios y Fidelización (RF10).

Implementa:
- Configuración del motor de reglas por la administradora (RF 10.1).
- Panel de auditoría de beneficios otorgados con filtros y canje en caja.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CanjeBeneficioForm, FiltroBeneficiosForm, ReglaBeneficioForm
from .models import BeneficioOtorgado, MensajeBeneficio, ReglaBeneficio
from .services import FidelizacionService, MensajeriaService


def es_admin_check(user) -> bool:
    return user.is_authenticated and getattr(user, "es_administradora", False)


# ──────────────────────────────────────────────────────────────
# RF 10.1 — Configuración del motor de reglas (solo administradora)
# ──────────────────────────────────────────────────────────────

@login_required
@user_passes_test(es_admin_check, login_url="fidelizacion:panel_beneficios")
def lista_reglas_view(request):
    """Lista las reglas del motor con conteo de beneficios otorgados."""
    FidelizacionService.marcar_vencidos()
    reglas = ReglaBeneficio.objects.all().order_by("tipo", "nombre")
    total_otorgados = BeneficioOtorgado.objects.count()
    disponibles = BeneficioOtorgado.objects.filter(estado=BeneficioOtorgado.Estado.DISPONIBLE).count()
    context = {
        "reglas": reglas,
        "total_otorgados": total_otorgados,
        "disponibles": disponibles,
        "hoy": timezone.localdate(),
    }
    return render(request, "fidelizacion/lista_reglas.html", context)


@login_required
@user_passes_test(es_admin_check, login_url="fidelizacion:panel_beneficios")
def crear_regla_view(request):
    """Alta de una nueva regla de beneficio."""
    if request.method == "POST":
        form = ReglaBeneficioForm(request.POST)
        if form.is_valid():
            regla = form.save()
            messages.success(request, f"Regla '{regla.nombre}' creada exitosamente.")
            return redirect("fidelizacion:lista_reglas")
    else:
        form = ReglaBeneficioForm()
    return render(request, "fidelizacion/form_regla.html", {"form": form, "accion": "Nueva regla de beneficio"})


@login_required
@user_passes_test(es_admin_check, login_url="fidelizacion:panel_beneficios")
def editar_regla_view(request, pk: int):
    """Edición de umbrales, recompensa y plantilla de una regla existente."""
    regla = get_object_or_404(ReglaBeneficio, pk=pk)
    if request.method == "POST":
        form = ReglaBeneficioForm(request.POST, instance=regla)
        if form.is_valid():
            regla = form.save()
            messages.success(request, f"Regla '{regla.nombre}' actualizada correctamente.")
            return redirect("fidelizacion:lista_reglas")
    else:
        form = ReglaBeneficioForm(instance=regla)
    return render(
        request, "fidelizacion/form_regla.html", {"form": form, "regla": regla, "accion": "Editar regla de beneficio"}
    )


@login_required
@user_passes_test(es_admin_check, login_url="fidelizacion:panel_beneficios")
def alternar_regla_view(request, pk: int):
    """Activa o pausa una regla sin eliminarla (conserva auditoría)."""
    regla = get_object_or_404(ReglaBeneficio, pk=pk)
    if request.method == "POST":
        regla.activo = not regla.activo
        regla.save(update_fields=["activo"])
        estado_txt = "activada" if regla.activo else "pausada"
        messages.success(request, f"Regla '{regla.nombre}' {estado_txt} correctamente.")
    return redirect("fidelizacion:lista_reglas")


@login_required
@user_passes_test(es_admin_check, login_url="fidelizacion:panel_beneficios")
def eliminar_regla_view(request, pk: int):
    """Elimina una regla del motor. Los cupones ya otorgados se conservan como historial (FK SET_NULL)."""
    regla = get_object_or_404(ReglaBeneficio, pk=pk)
    if request.method == "POST":
        nombre = regla.nombre
        cupones = BeneficioOtorgado.objects.filter(regla=regla).count()
        regla.delete()
        messages.success(
            request,
            f"Regla '{nombre}' eliminada. Se conservaron {cupones} cupón/cupones ya otorgados como historial.",
        )
    return redirect("fidelizacion:lista_reglas")


# ──────────────────────────────────────────────────────────────
# Panel de auditoría + canje (empleadas y administradora)
# ──────────────────────────────────────────────────────────────

@login_required
def panel_beneficios_view(request):
    """Listado auditable de beneficios otorgados con filtros por tipo, estado y búsqueda."""
    FidelizacionService.marcar_vencidos()
    form = FiltroBeneficiosForm(request.GET or None)
    beneficios = BeneficioOtorgado.objects.select_related("cliente", "regla").order_by("-fecha_otorgamiento")

    busqueda = request.GET.get("busqueda", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    estado = request.GET.get("estado", "").strip()

    if busqueda:
        beneficios = beneficios.filter(
            Q(cliente__nombre__icontains=busqueda)
            | Q(codigo__icontains=busqueda)
            | Q(cliente__telefono__icontains=busqueda)
        )
    if tipo:
        beneficios = beneficios.filter(tipo=tipo)
    if estado:
        beneficios = beneficios.filter(estado=estado)

    context = {
        "form": form,
        "beneficios": beneficios[:200],
        "total": beneficios.count(),
        "disponibles": beneficios.filter(estado=BeneficioOtorgado.Estado.DISPONIBLE).count(),
        "busqueda": busqueda,
        "hay_reglas_activas": ReglaBeneficio.objects.filter(activo=True).exists(),
        "total_reglas": ReglaBeneficio.objects.count(),
    }
    return render(request, "fidelizacion/panel_beneficios.html", context)


@login_required
def detalle_beneficio_view(request, pk: int):
    """Ficha del cupón: vigencia, mensaje enviado e historial de avisos."""
    beneficio = get_object_or_404(
        BeneficioOtorgado.objects.select_related("cliente", "regla", "canjeado_por"), pk=pk
    )
    mensajes = beneficio.mensajes.all().order_by("-fecha_creacion")
    form = CanjeBeneficioForm()

    if request.method == "POST" and "canjear" in request.POST:
        form = CanjeBeneficioForm(request.POST)
        if form.is_valid():
            try:
                beneficio.canjear(
                    profesional=request.user,
                    observaciones=form.cleaned_data.get("observaciones", ""),
                )
                messages.success(request, f"Cupón {beneficio.codigo} canjeado exitosamente.")
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("fidelizacion:detalle_beneficio", pk=beneficio.pk)

    if request.method == "POST" and "reenviar" in request.POST:
        canal = request.POST.get("canal", MensajeBeneficio.Canal.WHATSAPP)
        if canal not in dict(MensajeBeneficio.Canal.choices):
            canal = MensajeBeneficio.Canal.WHATSAPP
        MensajeriaService.avisar_beneficio(beneficio, canal=canal)
        messages.success(request, f"Aviso reenviado por {dict(MensajeBeneficio.Canal.choices)[canal]} (mock).")
        return redirect("fidelizacion:detalle_beneficio", pk=beneficio.pk)

    context = {
        "beneficio": beneficio,
        "mensajes": mensajes,
        "form": form,
        "canales": MensajeBeneficio.Canal.choices,
    }
    return render(request, "fidelizacion/detalle_beneficio.html", context)


# ── Aliases camelCase ──
listaReglasView = lista_reglas_view
crearReglaView = crear_regla_view
editarReglaView = editar_regla_view
alternarReglaView = alternar_regla_view
eliminarReglaView = eliminar_regla_view
panelBeneficiosView = panel_beneficios_view
detalleBeneficioView = detalle_beneficio_view
