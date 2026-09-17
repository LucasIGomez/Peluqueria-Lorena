"""
Peluquería Lorena — Servicio de comprobantes de venta (facturas en PDF).

Replica la arquitectura de generación de PDF de las órdenes de compra
(`apps/proveedores`): plantilla Word con variables Jinja renderizada con
`docxtpl` y conversión a PDF con LibreOffice en modo headless.

Una venta con carrito se persiste como varios `Cobro` (uno por ítem) con la
misma cabecera; este servicio los reagrupa en un único comprobante a partir
de cualquiera de sus cobros.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils import timezone

from .models import Cobro


class FacturaError(Exception):
    """Error al generar el comprobante de venta en PDF."""


# Ventana temporal para reagrupar los cobros de una misma venta con carrito
# (se registran en una única transacción, con segundos de diferencia).
VENTANA_AGRUPACION_SEGUNDOS = 60


def _formatear_monto(valor: Any) -> str:
    """Formatea un importe con 2 decimales y separador de miles."""
    return f"{Decimal(valor):,.2f}"


def _formatear_porcentaje(valor: Any) -> str:
    """Formatea un porcentaje sin decimales innecesarios (10.00 → 10)."""
    return "%g" % Decimal(valor)


class FacturaService:
    """Genera el comprobante de venta en PDF de una venta de caja."""

    # ── Agrupación de la venta ──

    @classmethod
    def cobros_de_venta(cls, cobro: Cobro) -> list[Cobro]:
        """
        Retorna los cobros vigentes que componen la misma venta que `cobro`.

        Los ítems de un carrito comparten cabecera (fecha, clienta,
        profesional, medio de pago, descuento y observaciones) y se crean en
        la misma transacción, por lo que se reagrupan filtrando por cabecera
        idéntica dentro de una ventana de 60 segundos alrededor del registro.
        """
        if cobro.anulado:
            return []
        desde = cobro.fecha_creacion - timedelta(seconds=VENTANA_AGRUPACION_SEGUNDOS)
        hasta = cobro.fecha_creacion + timedelta(seconds=VENTANA_AGRUPACION_SEGUNDOS)
        return list(
            Cobro.objects.filter(
                anulado=False,
                fecha=cobro.fecha,
                cliente_nombre=cobro.cliente_nombre,
                profesional=cobro.profesional,
                medio_pago=cobro.medio_pago,
                porcentaje_descuento=cobro.porcentaje_descuento,
                observaciones=cobro.observaciones,
                cliente_id=cobro.cliente_id,
                fecha_creacion__range=(desde, hasta),
            )
            .select_related("servicio", "producto", "profesional", "cliente")
            .order_by("pk")
        )

    @classmethod
    def cobrosDeVenta(cls, cobro: Cobro) -> list[Cobro]:
        return cls.cobros_de_venta(cobro)

    # ── Agrupación para el historial ──

    @classmethod
    def _clave_venta(cls, cobro: Cobro) -> tuple:
        """Cabecera que identifica a los ítems de una misma venta."""
        return (
            str(cobro.fecha),
            cobro.cliente_nombre,
            cobro.profesional_id,
            cobro.medio_pago,
            str(cobro.porcentaje_descuento),
            cobro.observaciones,
            cobro.cliente_id,
        )

    @classmethod
    def agrupar_ventas(cls, cobros) -> list[dict[str, Any]]:
        """
        Agrupa una lista de cobros en ventas para mostrarlas juntas en el
        historial: los ítems con igual cabecera y registros consecutivos
        (ventana de 60 segundos) forman una única fila. Retorna las ventas
        de más recientes a más antiguas, cada una con sus cobros y totales.
        """
        ordenados = sorted(cobros, key=lambda c: (c.fecha_creacion, c.pk))
        ventas: list[dict[str, Any]] = []
        for cobro in ordenados:
            if (
                ventas
                and cls._clave_venta(cobro) == cls._clave_venta(ventas[-1]["cobros"][-1])
                and (cobro.fecha_creacion - ventas[-1]["cobros"][-1].fecha_creacion).total_seconds()
                <= VENTANA_AGRUPACION_SEGUNDOS
            ):
                ventas[-1]["cobros"].append(cobro)
            else:
                ventas.append({"cobros": [cobro]})
        for venta in ventas:
            items = venta["cobros"]
            venta["principal"] = items[0]
            venta["es_grupo"] = len(items) > 1
            venta["subtotal"] = sum((c.subtotal for c in items), Decimal("0.00"))
            venta["monto_descuento"] = sum((c.monto_descuento for c in items), Decimal("0.00"))
            venta["total"] = sum((c.total for c in items), Decimal("0.00"))
        return ventas[::-1]

    @classmethod
    def agruparVentas(cls, cobros) -> list[dict[str, Any]]:
        return cls.agrupar_ventas(cobros)

    # ── Contexto del comprobante ──

    @classmethod
    def numero_comprobante(cls, cobros: list[Cobro]) -> str:
        """Número de comprobante: AAAAMMDD + ID del primer cobro."""
        primero = cobros[0]
        return f"{primero.fecha.strftime('%Y%m%d')}-{primero.pk:04d}"

    @classmethod
    def contexto_factura(cls, cobros: list[Cobro]) -> dict[str, Any]:
        """Arma el diccionario de variables para la plantilla del comprobante."""
        if not cobros:
            raise FacturaError("La venta no tiene cobros vigentes para facturar.")
        primero = cobros[0]
        datos_salon = getattr(settings, "DATOS_PELUQUERIA", {})
        profesional = primero.profesional
        profesional_nombre = (
            getattr(profesional, "nombre", None)
            or getattr(profesional, "username", None)
            or str(profesional)
        )
        porcentaje = primero.porcentaje_descuento or Decimal("0.00")
        items = []
        for cobro in cobros:
            if cobro.tipo == Cobro.Tipo.SERVICIO:
                descripcion = cobro.servicio.nombre if cobro.servicio else "Servicio"
            else:
                descripcion = cobro.producto.nombre if cobro.producto else "Producto"
            items.append(
                {
                    "tipo": cobro.get_tipo_display(),
                    "descripcion": descripcion,
                    "cantidad": str(cobro.cantidad),
                    "precio_unitario": _formatear_monto(cobro.precio_unitario),
                    "subtotal": _formatear_monto(cobro.subtotal),
                }
            )
        subtotal_general = sum((c.subtotal for c in cobros), Decimal("0.00"))
        monto_descuento = sum((c.monto_descuento for c in cobros), Decimal("0.00"))
        total_general = sum((c.total for c in cobros), Decimal("0.00"))
        return {
            "duena_nombre": datos_salon.get("NOMBRE_DUENA", "Lorena Yanil Ortigoza"),
            "duena_cuit": datos_salon.get("CUIT_DUENA", "27-29327958-1"),
            "peluqueria_telefono": datos_salon.get("TELEFONO", "+54 9 297 534-9278"),
            "duena_email": datos_salon.get("EMAIL", "lrnortigoza@gmail.com"),
            "direccion": datos_salon.get("DIRECCION", "Comodoro Rivadavia, Chubut, Argentina"),
            "numero_comprobante": cls.numero_comprobante(cobros),
            "fecha_emision": primero.fecha.strftime("%d/%m/%Y"),
            "hora_emision": timezone.localtime(primero.fecha_creacion).strftime("%H:%M"),
            "cliente_nombre": primero.cliente_nombre,
            "profesional_nombre": profesional_nombre,
            "medio_pago": primero.get_medio_pago_display(),
            "descuento_texto": (
                f"{_formatear_porcentaje(porcentaje)} %" if porcentaje > 0 else "Sin descuento"
            ),
            "descuento_porcentaje": _formatear_porcentaje(porcentaje),
            "observaciones": primero.observaciones or "—",
            "estado": "VIGENTE",
            "items": items,
            "subtotal_general": _formatear_monto(subtotal_general),
            "monto_descuento": _formatear_monto(monto_descuento),
            "total_general": _formatear_monto(total_general),
        }

    # ── Generación del PDF ──

    @classmethod
    def generar_pdf(cls, cobros: list[Cobro]) -> bytes:
        """
        Renderiza la plantilla del comprobante con `docxtpl` y la convierte
        a PDF con LibreOffice headless. Retorna los bytes del PDF.
        """
        contexto = cls.contexto_factura(cobros)
        plantilla = os.path.join(
            settings.BASE_DIR, "apps", "pagos", "templates_docx", "plantilla_factura.docx"
        )
        if not os.path.exists(plantilla):
            raise FacturaError(
                "No se encontró la plantilla del comprobante en el servidor "
                "(apps/pagos/templates_docx/plantilla_factura.docx)."
            )
        try:
            from docxtpl import DocxTemplate
        except ImportError as exc:
            raise FacturaError(
                "La librería 'docxtpl' no está instalada en el entorno virtual. "
                "Ejecuta 'pip install -r requirements.txt' en el servidor."
            ) from exc

        try:
            doc = DocxTemplate(plantilla)
            doc.render(contexto)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_docx = os.path.join(temp_dir, "factura.docx")
                doc.save(temp_docx)

                cmd_libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
                if not cmd_libreoffice:
                    raise FacturaError(
                        "LibreOffice no está instalado en el servidor para convertir a PDF. "
                        "Ejecuta en la terminal de la YOGA: sudo apt install -y libreoffice-writer-nogui"
                    )

                res = subprocess.run(
                    [cmd_libreoffice, "--headless", "--convert-to", "pdf", temp_docx, "--outdir", temp_dir],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )

                temp_pdf = os.path.join(temp_dir, "factura.pdf")
                if not os.path.exists(temp_pdf):
                    detalle = res.stderr.decode("utf-8", errors="ignore") or "Error en la conversión con LibreOffice."
                    raise FacturaError(f"No se pudo generar el PDF: {detalle}")

                with open(temp_pdf, "rb") as f:
                    return f.read()
        except FacturaError:
            raise
        except Exception as exc:
            raise FacturaError(f"Error al procesar el comprobante: {exc}") from exc

    @classmethod
    def generarPdf(cls, cobros: list[Cobro]) -> bytes:
        return cls.generar_pdf(cobros)
