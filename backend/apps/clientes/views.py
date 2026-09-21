"""
Peluquería Lorena — Vistas del módulo de Clientes.

Implementa:
- Vistas Web para la agenda de clientas, alertas de cumpleaños y WhatsApp.
- Ficha técnica integral de la clienta (tratamientos multisesión, consentimientos).
- API REST para consulta y gestión programática de clientas.
"""
from __future__ import annotations

from typing import Any
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from .forms import ClienteForm, EvolucionSesionForm, TratamientoProgresoForm, _validar_formato_telefono
from .models import Cliente, EvolucionSesion, TratamientoProgreso
from .services import ClienteService


# ──────────────────────────────────────────────────────────────
# Vistas Web SSR
# ──────────────────────────────────────────────────────────────


@login_required
def lista_clientes_view(request):
    """
    Lista las clientas con buscador inteligente por nombre, teléfono o email,
    y muestra alertas destacadas de cumpleañeras de la semana.
    """
    busqueda = request.GET.get("q", "").strip()
    clientes = ClienteService.listar_clientes(busqueda=busqueda if busqueda else None)
    cumpleaneras = ClienteService.obtener_cumpleaneras_proximos_dias(dias=7)

    context = {
        "clientes": clientes,
        "busqueda": busqueda,
        "total_clientes": clientes.count(),
        "cumpleaneras": cumpleaneras,
    }
    return render(request, "clientes/lista_clientes.html", context)


@login_required
def detalle_cliente_view(request, pk: int):
    """
    Ficha integral de la clienta: datos personales, alertas de cumpleaños,
    enlace a WhatsApp, tratamientos multisesión en progreso y consentimientos firmados.
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    tratamientos = cliente.tratamientos_progreso.all().prefetch_related("sesiones_evolucion")
    
    # Import dinámico para evitar ciclos si servicios aún no cargó
    from apps.servicios.models import ConsentimientoInformado, ServicioRealizado
    consentimientos = ConsentimientoInformado.objects.filter(
        cliente=cliente
    ).order_by("-fecha_emision")
    servicios_realizados = ServicioRealizado.objects.filter(
        cliente=cliente
    ).order_by("-fecha", "-hora")

    context = {
        "cliente": cliente,
        "tratamientos": tratamientos,
        "consentimientos": consentimientos,
        "servicios_realizados": servicios_realizados,
    }
    return render(request, "clientes/detalle_cliente.html", context)


@login_required
def crear_cliente_view(request):
    """Alta de una nueva clienta en el sistema."""
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Clienta '{cliente.nombre}' registrada exitosamente.")
            return redirect("clientes:detalle_cliente", pk=cliente.pk)
    else:
        form = ClienteForm()

    return render(request, "clientes/form_cliente.html", {"form": form, "accion": "Registrar Nueva Clienta"})


@login_required
def editar_cliente_view(request, pk: int):
    """Edición de los datos personales, alergias y preferencias de la clienta."""
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Datos de '{cliente.nombre}' actualizados correctamente.")
            return redirect("clientes:detalle_cliente", pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)

    return render(
        request,
        "clientes/form_cliente.html",
        {"form": form, "cliente": cliente, "accion": "Editar Ficha de Clienta"},
    )


@login_required
def eliminar_cliente_view(request, pk: int):
    """RF 4.2: Baja lógica de la clienta, preservando su historial de tratamientos."""
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        nombre = cliente.nombre
        ClienteService.eliminar_cliente(cliente)
        messages.success(request, f"Clienta '{nombre}' dada de baja exitosamente.")
        return redirect("clientes:lista_clientes")

    return render(request, "clientes/eliminar_cliente.html", {"cliente": cliente})


@login_required
def iniciar_tratamiento_view(request, cliente_pk: int):
    """Abre una ficha de seguimiento multisesión para la clienta."""
    cliente = get_object_or_404(Cliente, pk=cliente_pk)

    if request.method == "POST":
        form = TratamientoProgresoForm(request.POST)
        if form.is_valid():
            tratamiento = form.save(commit=False)
            tratamiento.cliente = cliente
            tratamiento.save()
            messages.success(
                request,
                f"Tratamiento '{tratamiento.titulo_tratamiento}' iniciado para {cliente.nombre}.",
            )
            return redirect("clientes:detalle_cliente", pk=cliente.pk)
    else:
        form = TratamientoProgresoForm()

    return render(
        request,
        "clientes/form_tratamiento.html",
        {"form": form, "cliente": cliente},
    )


@login_required
def registrar_evolucion_view(request, tratamiento_pk: int):
    """Registra la evolución y fórmulas químicas de una nueva sesión de tratamiento."""
    tratamiento = get_object_or_404(TratamientoProgreso, pk=tratamiento_pk)

    if request.method == "POST":
        form = EvolucionSesionForm(request.POST)
        if form.is_valid():
            sesion = form.save(commit=False)
            sesion.tratamiento = tratamiento
            if request.user.is_authenticated:
                sesion.profesional = request.user
            sesion.save()

            # Actualizar estado de avance del tratamiento
            if sesion.numero_sesion >= tratamiento.sesion_actual:
                tratamiento.sesion_actual = sesion.numero_sesion
                if tratamiento.sesion_actual >= tratamiento.total_sesiones_estimadas:
                    tratamiento.estado = TratamientoProgreso.Estado.FINALIZADO
                tratamiento.save(update_fields=["sesion_actual", "estado"])

            messages.success(
                request,
                f"Sesión #{sesion.numero_sesion} registrada exitosamente para '{tratamiento.titulo_tratamiento}'.",
            )
            return redirect("clientes:detalle_cliente", pk=tratamiento.cliente.pk)
    else:
        form = EvolucionSesionForm(initial={"numero_sesion": tratamiento.siguiente_numero_sesion})

    return render(
        request,
        "clientes/form_evolucion.html",
        {"form": form, "tratamiento": tratamiento},
    )


# ── Aliases camelCase para vistas Web ──
listaClientesView = lista_clientes_view
detalleClienteView = detalle_cliente_view
crearClienteView = crear_cliente_view
editarClienteView = editar_cliente_view
eliminarClienteView = eliminar_cliente_view
iniciarTratamientoView = iniciar_tratamiento_view
registrarEvolucionView = registrar_evolucion_view


# ──────────────────────────────────────────────────────────────
# API REST (DRF)
# ──────────────────────────────────────────────────────────────


class ClienteSerializer(serializers.ModelSerializer):
    es_cumpleanos_hoy = serializers.BooleanField(read_only=True)
    dias_para_cumpleanos = serializers.IntegerField(read_only=True)
    link_whatsapp = serializers.CharField(read_only=True)

    class Meta:
        model = Cliente
        fields = "__all__"

    def validate_telefono(self, value: str) -> str:
        try:
            return _validar_formato_telefono(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message)


class ClienteViewSet(viewsets.ModelViewSet):
    """API REST CRUD de clientas."""

    queryset = Cliente.objects.filter(activo=True).order_by("nombre")
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance: Cliente) -> None:
        """RF 4.2: un DELETE por API hace baja lógica, no borra el historial."""
        ClienteService.eliminar_cliente(instance)
