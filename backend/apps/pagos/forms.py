"""
Peluquería Lorena — Formularios del módulo de Caja y Ventas.
"""
from __future__ import annotations

import json
from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.inventario.models import Producto
from apps.servicios.models import Servicio
from apps.usuarios.models import Usuario
from .models import Cobro
from .services import CajaService


class CobroForm(forms.Form):
    """Formulario de registro de cobro con medio de pago."""

    TIPO_CHOICES = Cobro.Tipo.choices
    MEDIO_CHOICES = Cobro.MedioPago.choices

    tipo = forms.ChoiceField(
        label="Tipo de cobro",
        choices=TIPO_CHOICES,
        initial=Cobro.Tipo.SERVICIO,
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_tipo"}),
    )
    items_json = forms.CharField(
        label="Ítems del carrito",
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_items_json"}),
    )
    cliente = forms.ModelChoiceField(
        label="Clienta registrada (opcional)",
        queryset=Cliente.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_cliente"}),
    )
    cliente_nombre = forms.CharField(
        label="Nombre de la clienta",
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre y apellido", "id": "id_cliente_nombre"}
        ),
    )
    profesional = forms.ModelChoiceField(
        label="Profesional que cobra",
        queryset=Usuario.objects.filter(is_active=True).order_by("nombre"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    servicio = forms.ModelChoiceField(
        label="Servicio del catálogo",
        queryset=Servicio.objects.filter(activo=True).order_by("categoria", "nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_servicio"}),
    )
    producto = forms.ModelChoiceField(
        label="Producto a vender",
        queryset=Producto.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_producto"}),
    )
    cantidad = forms.IntegerField(
        label="Cantidad",
        min_value=1,
        initial=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "id": "id_cantidad"}),
    )
    precio_unitario = forms.DecimalField(
        label="Precio unitario ($)",
        min_value=0,
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "min": 0, "id": "id_precio_unitario"}
        ),
    )
    medio_pago = forms.ChoiceField(
        label="Medio de pago",
        choices=MEDIO_CHOICES,
        initial=Cobro.MedioPago.EFECTIVO,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_medio_pago"}),
    )
    porcentaje_descuento = forms.DecimalField(
        label="Descuento (%)",
        min_value=0,
        max_value=100,
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.5",
                "min": 0,
                "max": 100,
                "placeholder": "Ej: 10",
                "id": "id_descuento",
            }
        ),
    )
    fecha = forms.DateField(
        label="Fecha de cobro",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    def _parse_items(self, crudo: str | None) -> list[dict]:
        """Parsea el carrito JSON enviado por el frontend."""
        if not crudo or not str(crudo).strip():
            return []
        try:
            items = json.loads(crudo)
        except (json.JSONDecodeError, TypeError):
            raise forms.ValidationError("El carrito contiene datos inválidos.")
        if not isinstance(items, list):
            raise forms.ValidationError("El carrito contiene datos inválidos.")
        return items

    def _validar_items_carrito(self, items: list[dict]) -> list[dict]:
        """Valida cada fila del carrito: tipo, existencia, cantidad y precio > 0."""
        tipos_validos = {c[0] for c in Cobro.Tipo.choices}
        normalizados: list[dict] = []
        for indice, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise forms.ValidationError(f"Ítem {indice}: formato inválido.")
            tipo = str(item.get("tipo") or "").upper()
            if tipo not in tipos_validos:
                raise forms.ValidationError(f"Ítem {indice}: tipo inválido.")
            try:
                cantidad = int(item.get("cantidad") or 0)
            except (TypeError, ValueError):
                raise forms.ValidationError(f"Ítem {indice}: cantidad inválida.")
            if cantidad <= 0:
                raise forms.ValidationError(f"Ítem {indice}: la cantidad debe ser mayor a cero.")
            try:
                precio = Decimal(str(item.get("precio_unitario") or "0"))
            except Exception:
                raise forms.ValidationError(f"Ítem {indice}: precio inválido.")
            if precio <= Decimal("0.00"):
                raise forms.ValidationError(f"Ítem {indice}: el precio debe ser mayor a cero.")
            if tipo == Cobro.Tipo.SERVICIO:
                servicio_id = item.get("servicio_id")
                if not servicio_id:
                    raise forms.ValidationError(f"Ítem {indice}: seleccioná el servicio.")
                if cantidad != 1:
                    raise forms.ValidationError(
                        f"Ítem {indice}: los servicios se cobran por unidad (cantidad 1)."
                    )
                try:
                    servicio = Servicio.objects.get(pk=int(servicio_id), activo=True)
                except (Servicio.DoesNotExist, ValueError, TypeError):
                    raise forms.ValidationError(f"Ítem {indice}: el servicio no existe o está inactivo.")
                normalizados.append(
                    {"tipo": tipo, "cantidad": 1, "precio_unitario": precio, "servicio": servicio}
                )
            else:
                producto_id = item.get("producto_id")
                if not producto_id:
                    raise forms.ValidationError(f"Ítem {indice}: seleccioná el producto.")
                try:
                    prod = Producto.objects.get(pk=int(producto_id), activo=True)
                except (Producto.DoesNotExist, ValueError, TypeError):
                    raise forms.ValidationError(f"Ítem {indice}: el producto no existe o está inactivo.")
                if prod.stock_actual < cantidad:
                    raise forms.ValidationError(
                        f"Ítem {indice}: stock insuficiente para '{prod.nombre}'. "
                        f"Disponible: {prod.stock_actual}."
                    )
                normalizados.append(
                    {"tipo": tipo, "cantidad": cantidad, "precio_unitario": precio, "producto": prod}
                )
        if not normalizados:
            raise forms.ValidationError("Agregá al menos un servicio o producto al carrito.")
        return normalizados

    def clean(self):
        datos = super().clean()
        items_crudos = self.data.get("items_json") or datos.get("items_json")
        items = self._parse_items(items_crudos if isinstance(items_crudos, str) else None)
        if items:
            datos["items"] = self._validar_items_carrito(items)
        else:
            # Compatibilidad con POST unitario (tests/API): validación de ítem único.
            datos["items"] = []
            if (
                datos.get("cantidad") is None
                and datos.get("precio_unitario") is None
                and not datos.get("servicio")
                and not datos.get("producto")
            ):
                raise forms.ValidationError("Agregá al menos un servicio o producto al carrito.")
            tipo = datos.get("tipo") or Cobro.Tipo.SERVICIO
            datos["tipo"] = tipo
            if tipo == Cobro.Tipo.PRODUCTO and not datos.get("producto"):
                self.add_error("producto", "Seleccioná el producto a vender.")
            if tipo == Cobro.Tipo.SERVICIO and not datos.get("precio_unitario"):
                if not datos.get("servicio"):
                    self.add_error(
                        "precio_unitario",
                        "Indicá el precio o seleccioná el servicio cobrado.",
                    )
            cantidad = datos.get("cantidad")
            if cantidad is not None and cantidad <= 0:
                self.add_error("cantidad", "La cantidad debe ser mayor a cero.")
            if tipo == Cobro.Tipo.SERVICIO and cantidad is not None and cantidad != 1:
                self.add_error("cantidad", "Los servicios se cobran por unidad (cantidad 1).")
            precio = datos.get("precio_unitario")
            # Precio explícito siempre > 0. Si es None y hay servicio, el
            # servicio resuelve por precio_base en la capa de servicios.
            if precio is not None and precio <= Decimal("0.00"):
                self.add_error("precio_unitario", "El precio debe ser mayor a cero.")
        medio = datos.get("medio_pago")
        descuento = datos.get("porcentaje_descuento")
        if medio in CajaService.MEDIOS_CON_DESCUENTO:
            if descuento is None:
                datos["porcentaje_descuento"] = Decimal("0.00")
        else:
            if descuento is not None and descuento != Decimal("0.00"):
                self.add_error(
                    "porcentaje_descuento",
                    "Este medio de pago no admite descuento.",
                )
            datos["porcentaje_descuento"] = Decimal("0.00")
        return datos


class CierreCajaForm(forms.Form):
    """Confirmación del cierre de caja diario."""

    fecha = forms.DateField(
        label="Fecha del cierre",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    observaciones = forms.CharField(
        label="Observaciones del cierre",
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 2, "placeholder": "Diferencias, faltantes, notas..."}
        ),
    )


class ReporteMediosForm(forms.Form):
    """Filtros del reporte por medio de pago."""

    fecha_desde = forms.DateField(
        label="Desde",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )
    fecha_hasta = forms.DateField(
        label="Hasta",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
    )

    def clean(self):
        datos = super().clean()
        desde = datos.get("fecha_desde")
        hasta = datos.get("fecha_hasta")
        if desde and hasta and desde > hasta:
            raise forms.ValidationError("La fecha inicial no puede ser posterior a la final.")
        return datos
