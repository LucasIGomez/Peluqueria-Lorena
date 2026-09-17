"""
Peluquería Lorena — Capa de servicios del módulo de Caja y Ventas.

Centraliza la lógica de negocio de cobros, descuentos por medio de pago,
cierres diarios y reportes de ingresos.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union

from django.db import transaction
from django.db.models import Count, QuerySet, Sum
from django.utils import timezone

from .models import CierreCaja, Cobro


def _a_dos_decimales(valor: Decimal) -> Decimal:
    """Redondea un Decimal a dos decimales (mitad hacia arriba)."""
    return valor.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


class CajaError(Exception):
    """Excepción base del módulo de caja."""


class CajaCerradaError(CajaError):
    """Se lanza al operar sobre una fecha con cierre ya realizado."""


class CobroInvalidoError(CajaError):
    """Se lanza cuando los datos del cobro no son válidos."""


class CajaService:
    """
    Servicio de dominio para cobros, descuentos, cierres y reportes.
    """

    #: Descuento sugerido por defecto (10%) para efectivo, Mercado Pago y Ualá.
    #: El usuario puede modificarlo en cada cobro entre 0 y 100%.
    PORCENTAJE_DESCUENTO_AUTOMATICO = Decimal("10.00")

    #: Medios que aplican el descuento automático.
    MEDIOS_CON_DESCUENTO = frozenset(
        {Cobro.MedioPago.EFECTIVO, Cobro.MedioPago.MERCADO_PAGO, Cobro.MedioPago.UALA}
    )

    # ── Descuento por medio de pago ──

    @classmethod
    def calcular_totales(
        cls,
        subtotal: Union[Decimal, str, float],
        medio_pago: str,
        porcentaje_descuento: Optional[Union[Decimal, str, float]] = None,
    ) -> Dict[str, Decimal]:
        """
        Calcula el descuento según el medio de pago.

        - Efectivo, Mercado Pago y Ualá: aplica el porcentaje indicado
          (por defecto el sugerido del 10%). Debe estar entre 0 y 100.
        - Tarjetas de débito y crédito: no admiten descuento (0% forzado).

        Args:
            subtotal: Monto base antes del descuento (>= 0).
            medio_pago: Código del medio de pago (ver Cobro.MedioPago).
            porcentaje_descuento: Porcentaje manual (solo medios con descuento).

        Returns:
            Diccionario con porcentaje_descuento, monto_descuento y total.
        """
        base = _a_dos_decimales(Decimal(str(subtotal)))
        if base < Decimal("0.00"):
            raise CobroInvalidoError("El subtotal no puede ser negativo.")

        medios_validos = {c[0] for c in Cobro.MedioPago.choices}
        if medio_pago not in medios_validos:
            raise CobroInvalidoError(f"Medio de pago inválido: {medio_pago}.")

        if medio_pago in cls.MEDIOS_CON_DESCUENTO:
            if porcentaje_descuento is None:
                porcentaje = cls.PORCENTAJE_DESCUENTO_AUTOMATICO
            else:
                porcentaje = _a_dos_decimales(Decimal(str(porcentaje_descuento)))
                if porcentaje < Decimal("0.00") or porcentaje > Decimal("100.00"):
                    raise CobroInvalidoError("El descuento debe estar entre 0 y 100%.")
        else:
            porcentaje = Decimal("0.00")

        monto = _a_dos_decimales(base * porcentaje / Decimal("100"))
        total = _a_dos_decimales(base - monto)
        return {
            "porcentaje_descuento": porcentaje,
            "monto_descuento": monto,
            "total": total,
        }

    @classmethod
    def calcularTotales(cls, *args: Any, **kwargs: Any) -> Dict[str, Decimal]:
        return cls.calcular_totales(*args, **kwargs)

    # ── Registro de cobro ──

    @classmethod
    @transaction.atomic
    def registrar_cobro(
        cls,
        cliente_nombre: str,
        profesional: Any,
        tipo: str = Cobro.Tipo.SERVICIO,
        medio_pago: str = Cobro.MedioPago.EFECTIVO,
        cantidad: int = 1,
        precio_unitario: Optional[Union[Decimal, str, float]] = None,
        servicio: Any = None,
        servicio_realizado: Any = None,
        producto: Any = None,
        cliente: Any = None,
        fecha: Optional[date] = None,
        observaciones: str = "",
        porcentaje_descuento: Optional[Union[Decimal, str, float]] = None,
    ) -> Cobro:
        """
        Registra el cobro de un servicio o la venta de un producto.

        - Servicio: requiere precio_unitario o servicio/servicio_realizado
          para tomar el precio de referencia.
        - Producto: requiere producto y descuenta stock automáticamente
          mediante el módulo de inventario.

        Aplica el descuento indicado si el medio es efectivo, Mercado Pago o Ualá
        (10% por defecto); las tarjetas no admiten descuento.
        """
        from apps.inventario.services import InventarioService

        tipos_validos = {c[0] for c in Cobro.Tipo.choices}
        if tipo not in tipos_validos:
            raise CobroInvalidoError(f"Tipo de cobro inválido: {tipo}.")

        if not cliente_nombre or not cliente_nombre.strip():
            raise CobroInvalidoError("El nombre de la clienta es obligatorio.")
        if profesional is None:
            raise CobroInvalidoError("El profesional que cobra es obligatorio.")
        if cantidad <= 0:
            raise CobroInvalidoError("La cantidad debe ser mayor a cero.")

        dia = fecha or timezone.localdate()

        # No operar sobre una caja ya cerrada.
        if CierreCaja.objects.filter(fecha=dia).exists():
            raise CajaCerradaError(
                f"La caja del {dia.strftime('%d/%m/%Y')} ya fue cerrada. "
                "No se pueden registrar ni anular cobros de ese día."
            )

        precio_ref: Optional[Decimal] = None
        producto_obj = None
        servicio_obj = servicio
        servicio_realizado_obj = servicio_realizado

        if tipo == Cobro.Tipo.PRODUCTO:
            if producto is None:
                raise CobroInvalidoError("La venta de producto requiere un producto.")
            from apps.inventario.models import Producto as ProductoModel

            producto_obj = producto
            if isinstance(producto, int):
                try:
                    producto_obj = ProductoModel.objects.get(pk=producto)
                except ProductoModel.DoesNotExist as exc:
                    raise CobroInvalidoError("El producto no existe.") from exc
            if not producto_obj.activo:
                raise CobroInvalidoError("El producto está dado de baja.")
            precio_ref = producto_obj.precio
        else:
            if servicio_realizado_obj is not None and precio_unitario is None:
                precio_ref = servicio_realizado_obj.precio_acordado
            elif servicio_obj is not None and precio_unitario is None:
                precio_ref = servicio_obj.precio_base

        if precio_unitario is not None:
            precio_final = _a_dos_decimales(Decimal(str(precio_unitario)))
        elif precio_ref is not None:
            precio_final = _a_dos_decimales(Decimal(precio_ref))
        else:
            raise CobroInvalidoError(
                "Debe indicar el precio unitario o el servicio cobrado."
            )
        if precio_final <= Decimal("0.00"):
            raise CobroInvalidoError("El precio unitario debe ser mayor a cero.")

        subtotal = _a_dos_decimales(precio_final * cantidad)
        totales = cls.calcular_totales(subtotal, medio_pago, porcentaje_descuento)

        cobro = Cobro.objects.create(
            cliente=cliente,
            cliente_nombre=cliente_nombre.strip(),
            profesional=profesional,
            tipo=tipo,
            servicio=servicio_obj,
            servicio_realizado=servicio_realizado_obj,
            producto=producto_obj,
            cantidad=cantidad,
            precio_unitario=precio_final,
            subtotal=subtotal,
            porcentaje_descuento=totales["porcentaje_descuento"],
            monto_descuento=totales["monto_descuento"],
            total=totales["total"],
            medio_pago=medio_pago,
            fecha=dia,
            observaciones=observaciones.strip() if observaciones else "",
        )

        # La venta de producto descuenta stock con trazabilidad.
        if tipo == Cobro.Tipo.PRODUCTO and producto_obj is not None:
            motivo = (
                f"Venta en caja a {cobro.cliente_nombre} "
                f"({dia.strftime('%d/%m/%Y')}) — Cobro #{cobro.pk}"
            )
            try:
                InventarioService.descontar_stock(
                    producto_o_id=producto_obj.pk,
                    cantidad=cantidad,
                    motivo=motivo,
                    usuario=profesional,
                )
            except Exception as exc:
                raise CobroInvalidoError(f"No se pudo descontar stock: {exc}") from exc

        return cobro

    @classmethod
    def registrarCobro(cls, *args: Any, **kwargs: Any) -> Cobro:
        return cls.registrar_cobro(*args, **kwargs)

    @classmethod
    @transaction.atomic
    def registrar_cobros_carrito(
        cls,
        items: list[dict],
        cliente_nombre: str,
        profesional: Any,
        medio_pago: str = Cobro.MedioPago.EFECTIVO,
        cliente: Any = None,
        fecha: Optional[date] = None,
        observaciones: str = "",
        porcentaje_descuento: Optional[Union[Decimal, str, float]] = None,
    ) -> list[Cobro]:
        """
        Registra una venta con múltiples ítems (carrito) como varios Cobro
        vinculados por cabecera común, en una única transacción atómica.

        Cada ítem requiere: tipo, cantidad (1 fija para servicios, > 0 para
        productos), precio_unitario (> 0) y servicio o producto según el tipo.
        El descuento porcentual de la cabecera se aplica a cada línea para que
        el total general cuadre con el cierre y los reportes existentes.
        """
        if not items:
            raise CobroInvalidoError("Agregá al menos un servicio o producto al carrito.")
        dia = fecha or timezone.localdate()
        if CierreCaja.objects.filter(fecha=dia).exists():
            raise CajaCerradaError(
                f"La caja del {dia.strftime('%d/%m/%Y')} ya fue cerrada. "
                "No se pueden registrar ni anular cobros de ese día."
            )
        cobros: list[Cobro] = []
        for indice, item in enumerate(items, start=1):
            tipo = item.get("tipo")
            cantidad = item.get("cantidad")
            precio = item.get("precio_unitario")
            try:
                cantidad = int(cantidad)
            except (TypeError, ValueError) as exc:
                raise CobroInvalidoError(f"Ítem {indice}: cantidad inválida.") from exc
            if cantidad <= 0:
                raise CobroInvalidoError(f"Ítem {indice}: la cantidad debe ser mayor a cero.")
            if tipo == Cobro.Tipo.SERVICIO and cantidad != 1:
                raise CobroInvalidoError(
                    f"Ítem {indice}: los servicios se cobran por unidad (cantidad 1)."
                )
            try:
                precio_dec = _a_dos_decimales(Decimal(str(precio)))
            except Exception as exc:
                raise CobroInvalidoError(f"Ítem {indice}: precio inválido.") from exc
            if precio_dec <= Decimal("0.00"):
                raise CobroInvalidoError(f"Ítem {indice}: el precio debe ser mayor a cero.")
            cobro = cls.registrar_cobro(
                cliente_nombre=cliente_nombre,
                profesional=profesional,
                tipo=tipo,
                medio_pago=medio_pago,
                cantidad=cantidad,
                precio_unitario=precio_dec,
                servicio=item.get("servicio"),
                servicio_realizado=None,
                producto=item.get("producto"),
                cliente=cliente,
                fecha=dia,
                observaciones=observaciones,
                porcentaje_descuento=porcentaje_descuento,
            )
            cobros.append(cobro)
        return cobros

    @classmethod
    def registrarCobrosCarrito(cls, *args: Any, **kwargs: Any) -> list[Cobro]:
        return cls.registrar_cobros_carrito(*args, **kwargs)

    # ── Anulación ──

    @classmethod
    @transaction.atomic
    def anular_cobro(cls, cobro: Cobro, usuario: Any = None) -> Cobro:
        """
        Anula un cobro (baja lógica). Si era venta de producto, repone stock.
        No permite anular cobros de un día con caja ya cerrada.
        """
        from apps.inventario.services import InventarioService

        if cobro.anulado:
            raise CobroInvalidoError("El cobro ya se encuentra anulado.")
        if cobro.cierre_id is not None or CierreCaja.objects.filter(fecha=cobro.fecha).exists():
            raise CajaCerradaError(
                "No se puede anular un cobro incluido en un cierre de caja."
            )

        if cobro.tipo == Cobro.Tipo.PRODUCTO and cobro.producto_id:
            InventarioService.reponer_stock(
                producto_o_id=cobro.producto_id,
                cantidad=cobro.cantidad,
                motivo=f"Anulación del cobro #{cobro.pk} a {cobro.cliente_nombre}",
                usuario=usuario,
            )

        cobro.anulado = True
        cobro.save(update_fields=["anulado"])
        return cobro

    @classmethod
    def anularCobro(cls, *args: Any, **kwargs: Any) -> Cobro:
        return cls.anular_cobro(*args, **kwargs)

    @classmethod
    @transaction.atomic
    def anular_venta(cls, cobros: list, usuario: Any = None) -> list:
        """
        Anula todos los ítems de una venta en conjunto (baja lógica de cada
        cobro con reposición de stock). Todo o nada: si un ítem falla
        (caja cerrada o ya anulado), no se anula ninguno.
        """
        if not cobros:
            raise CobroInvalidoError("La venta no tiene cobros vigentes para anular.")
        anulados = []
        for cobro in cobros:
            anulados.append(cls.anular_cobro(cobro, usuario=usuario))
        return anulados

    @classmethod
    def anularVenta(cls, *args: Any, **kwargs: Any) -> list:
        return cls.anular_venta(*args, **kwargs)

    # ── Consultas ──

    @staticmethod
    def listar_cobros_por_fecha(
        fecha: Optional[date] = None,
        incluir_anulados: bool = False,
    ) -> QuerySet[Cobro]:
        """Lista los cobros de un día ordenados por hora de registro."""
        dia = fecha or timezone.localdate()
        queryset = Cobro.objects.filter(fecha=dia).select_related(
            "profesional", "cliente", "servicio", "producto", "cierre"
        )
        if not incluir_anulados:
            queryset = queryset.filter(anulado=False)
        return queryset.order_by("fecha_creacion")

    @staticmethod
    def listarCobrosPorFecha(*args: Any, **kwargs: Any) -> QuerySet[Cobro]:
        return CajaService.listar_cobros_por_fecha(*args, **kwargs)

    @staticmethod
    def caja_esta_cerrada(fecha: Optional[date] = None) -> bool:
        """Indica si la caja de la fecha ya fue cerrada."""
        dia = fecha or timezone.localdate()
        return CierreCaja.objects.filter(fecha=dia).exists()

    @staticmethod
    def cajaEstaCerrada(*args: Any, **kwargs: Any) -> bool:
        return CajaService.caja_esta_cerrada(*args, **kwargs)

    @classmethod
    def resumen_caja_dia(cls, fecha: Optional[date] = None) -> Dict[str, Any]:
        """
        Consolida los cobros vigentes del día por medio de pago,
        con cantidades, descuentos y total general (base del cierre y reporte).
        """
        from django.db.models import Sum as _Sum

        dia = fecha or timezone.localdate()
        cobros = Cobro.objects.filter(fecha=dia, anulado=False)

        totales: Dict[str, Decimal] = {}
        cantidades: Dict[str, int] = {}
        descuentos: Dict[str, Decimal] = {}
        for codigo, _etiqueta in Cobro.MedioPago.choices:
            totales[codigo] = Decimal("0.00")
            cantidades[codigo] = 0
            descuentos[codigo] = Decimal("0.00")

        agregados = (
            cobros.values("medio_pago")
            .annotate(
                cantidad_cobros=Count("id"),
                suma_total=Sum("total"),
                suma_descuento=Sum("monto_descuento"),
            )
            .order_by("medio_pago")
        )
        for fila in agregados:
            totales[fila["medio_pago"]] = _a_dos_decimales(fila["suma_total"] or Decimal("0.00"))
            cantidades[fila["medio_pago"]] = fila["cantidad_cobros"]
            descuentos[fila["medio_pago"]] = _a_dos_decimales(
                fila["suma_descuento"] or Decimal("0.00")
            )

        total_descuentos = cobros.aggregate(s=Sum("monto_descuento"))["s"] or Decimal("0.00")
        total_general = cobros.aggregate(s=_Sum("total"))["s"] or Decimal("0.00")

        detalle = [
            {
                "codigo": codigo,
                "etiqueta": etiqueta,
                "cantidad": cantidades[codigo],
                "total": totales[codigo],
                "descuento": descuentos[codigo],
                "con_descuento": codigo in cls.MEDIOS_CON_DESCUENTO,
            }
            for codigo, etiqueta in Cobro.MedioPago.choices
        ]

        cierre = CierreCaja.objects.filter(fecha=dia).first()

        return {
            "fecha": dia,
            "cobros": cobros.select_related("profesional", "cliente", "servicio", "producto"),
            "cantidad_cobros": cobros.count(),
            "detalle_por_medio": detalle,
            "totales": totales,
            "total_descuentos": _a_dos_decimales(total_descuentos),
            "total_general": _a_dos_decimales(total_general),
            "caja_cerrada": cierre is not None,
            "cierre": cierre,
        }

    @classmethod
    def resumenCajaDia(cls, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return cls.resumen_caja_dia(*args, **kwargs)

    # ── Cierre de caja ──

    @classmethod
    @transaction.atomic
    def realizar_cierre_caja(
        cls,
        fecha: Optional[date] = None,
        responsable: Any = None,
        observaciones: str = "",
    ) -> CierreCaja:
        """
        Realiza el cierre de caja diario: consolida los cobros vigentes
        por medio de pago, guarda el CierreCaja y vincula cada cobro.
        """
        dia = fecha or timezone.localdate()
        if responsable is None:
            raise CobroInvalidoError("El responsable del cierre es obligatorio.")
        if CierreCaja.objects.filter(fecha=dia).exists():
            raise CajaCerradaError(
                f"La caja del {dia.strftime('%d/%m/%Y')} ya fue cerrada."
            )

        resumen = cls.resumen_caja_dia(fecha=dia)
        totales = resumen["totales"]

        cierre = CierreCaja.objects.create(
            fecha=dia,
            responsable=responsable,
            cantidad_cobros=resumen["cantidad_cobros"],
            total_efectivo=totales[Cobro.MedioPago.EFECTIVO],
            total_mercado_pago=totales[Cobro.MedioPago.MERCADO_PAGO],
            total_uala=totales[Cobro.MedioPago.UALA],
            total_tarjeta_debito=totales[Cobro.MedioPago.TARJETA_DEBITO],
            total_tarjeta_credito=totales[Cobro.MedioPago.TARJETA_CREDITO],
            total_descuentos=resumen["total_descuentos"],
            total_general=resumen["total_general"],
            observaciones=observaciones.strip() if observaciones else "",
        )
        Cobro.objects.filter(fecha=dia, anulado=False, cierre__isnull=True).update(
            cierre=cierre
        )
        return cierre

    @classmethod
    def realizarCierreCaja(cls, *args: Any, **kwargs: Any) -> CierreCaja:
        return cls.realizar_cierre_caja(*args, **kwargs)

    # ── Reapertura de caja ──

    @classmethod
    @transaction.atomic
    def reabrir_caja(cls, fecha: Optional[date] = None, usuario: Any = None) -> None:
        """
        Reabre la caja de una fecha eliminando el CierreCaja existente y desvinculando
        los cobros asociados para permitir registrar nuevas operaciones.
        """
        dia = fecha or timezone.localdate()
        cierre = CierreCaja.objects.filter(fecha=dia).first()
        if not cierre:
            raise CajaError(f"No hay ningún cierre de caja registrado para el {dia.strftime('%d/%m/%Y')}.")

        Cobro.objects.filter(cierre=cierre).update(cierre=None)
        cierre.delete()

    @classmethod
    def reabrirCaja(cls, *args: Any, **kwargs: Any) -> None:
        return cls.reabrir_caja(*args, **kwargs)

    # ── Reporte por medio de pago ──

    @staticmethod
    def reporte_por_medio_pago(
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Genera el reporte de ingresos discriminado por medio de pago
        en un rango de fechas (inclusive). Solo cobros vigentes.
        """
        hoy = timezone.localdate()
        desde = fecha_desde or hoy
        hasta = fecha_hasta or hoy
        if desde > hasta:
            raise CobroInvalidoError(
                "La fecha inicial no puede ser posterior a la fecha final."
            )

        cobros = Cobro.objects.filter(fecha__gte=desde, fecha__lte=hasta, anulado=False)

        detalle: List[Dict[str, Any]] = []
        total_general = Decimal("0.00")
        cantidad_total = 0
        for codigo, etiqueta in Cobro.MedioPago.choices:
            fila = cobros.filter(medio_pago=codigo).aggregate(
                cantidad=Count("id"), suma=Sum("total")
            )
            cantidad = fila["cantidad"] or 0
            suma = _a_dos_decimales(fila["suma"] or Decimal("0.00"))
            total_general += suma
            cantidad_total += cantidad
            detalle.append(
                {
                    "codigo": codigo,
                    "etiqueta": etiqueta,
                    "cantidad": cantidad,
                    "total": suma,
                    "porcentaje": Decimal("0.00"),  # se completa abajo
                }
            )

        total_general = _a_dos_decimales(total_general)
        for fila in detalle:
            if total_general > 0:
                fila["porcentaje"] = _a_dos_decimales(
                    fila["total"] * Decimal("100") / total_general
                )

        total_descuentos = _a_dos_decimales(
            cobros.aggregate(s=Sum("monto_descuento"))["s"] or Decimal("0.00")
        )

        return {
            "fecha_desde": desde,
            "fecha_hasta": hasta,
            "detalle": detalle,
            "cantidad_total": cantidad_total,
            "total_general": total_general,
            "total_descuentos": total_descuentos,
        }

    @staticmethod
    def reportePorMedioPago(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return CajaService.reporte_por_medio_pago(*args, **kwargs)
