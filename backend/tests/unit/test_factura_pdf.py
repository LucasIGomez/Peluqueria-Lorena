"""
Pruebas unitarias del comprobante de venta (factura en PDF).
"""
from decimal import Decimal

import pytest

from apps.inventario.models import Producto
from apps.pagos.facturacion import FacturaService
from apps.pagos.models import Cobro
from apps.pagos.services import CajaService
from apps.servicios.models import Servicio
from apps.servicios.services import ServicioService
from tests.factories.usuario_factory import EmpleadaFactory


@pytest.mark.django_db
class TestFacturaVenta:
    """Agrupación de cobros y contexto del comprobante (sin I/O)."""

    def _venta_carrito(self):
        empleada = EmpleadaFactory()
        servicio = ServicioService.crear_servicio(
            nombre="Corte Factura",
            categoria=Servicio.Categoria.CORTES,
            precio_base=Decimal("20000.00"),
        )
        producto = Producto.objects.create(
            nombre="Crema Factura",
            precio=Decimal("10000.00"),
            stock_actual=10,
            stock_minimo=2,
            activo=True,
        )
        cobros = CajaService.registrar_cobros_carrito(
            items=[
                {
                    "tipo": Cobro.Tipo.SERVICIO,
                    "cantidad": 1,
                    "precio_unitario": Decimal("20000.00"),
                    "servicio": servicio,
                },
                {
                    "tipo": Cobro.Tipo.PRODUCTO,
                    "cantidad": 2,
                    "precio_unitario": Decimal("10000.00"),
                    "producto": producto,
                },
            ],
            cliente_nombre="Dora Factura",
            profesional=empleada,
            medio_pago=Cobro.MedioPago.EFECTIVO,
        )
        return cobros

    def test_agrupa_items_de_la_venta_con_carrito(self) -> None:
        cobros = self._venta_carrito()
        agrupados = FacturaService.cobros_de_venta(cobros[0])
        assert [c.pk for c in agrupados] == [c.pk for c in cobros]

    def test_venta_individual_agrupa_solo_un_cobro(self) -> None:
        empleada = EmpleadaFactory()
        cobro = CajaService.registrar_cobro(
            cliente_nombre="Eva Simple",
            profesional=empleada,
            tipo=Cobro.Tipo.SERVICIO,
            medio_pago=Cobro.MedioPago.TARJETA_DEBITO,
            cantidad=1,
            precio_unitario=Decimal("15000.00"),
        )
        agrupados = FacturaService.cobros_de_venta(cobro)
        assert [c.pk for c in agrupados] == [cobro.pk]

    def test_cobro_anulado_no_genera_comprobante(self) -> None:
        cobros = self._venta_carrito()
        CajaService.anular_cobro(cobros[0], usuario=cobros[0].profesional)
        cobros[0].refresh_from_db()
        assert FacturaService.cobros_de_venta(cobros[0]) == []

    def test_contexto_factura_completo(self) -> None:
        cobros = self._venta_carrito()
        contexto = FacturaService.contexto_factura(cobros)
        assert contexto["numero_comprobante"].endswith(f"-{cobros[0].pk:04d}")
        assert contexto["cliente_nombre"] == "Dora Factura"
        assert contexto["medio_pago"] == cobros[0].get_medio_pago_display()
        assert len(contexto["items"]) == 2
        assert contexto["items"][0]["descripcion"] == "Corte Factura"
        assert contexto["items"][1]["cantidad"] == "2"
        assert contexto["subtotal_general"] == "40,000.00"
        assert contexto["monto_descuento"] == "4,000.00"
        assert contexto["total_general"] == "36,000.00"
        assert contexto["estado"] == "VIGENTE"


@pytest.mark.django_db
class TestAgruparVentasHistorial:
    """Filas del historial: ítems vendidos en conjunto comparten fila."""

    def _cobro_simple(self, cliente_nombre, profesional=None, medio_pago=None):
        empleada = profesional or EmpleadaFactory()
        return CajaService.registrar_cobro(
            cliente_nombre=cliente_nombre,
            profesional=empleada,
            tipo=Cobro.Tipo.SERVICIO,
            medio_pago=medio_pago or Cobro.MedioPago.EFECTIVO,
            cantidad=1,
            precio_unitario=Decimal("10000.00"),
        )

    def test_items_del_carrito_forman_una_sola_venta(self) -> None:
        empleada = EmpleadaFactory()
        servicio = ServicioService.crear_servicio(
            nombre="Corte Grupo",
            categoria=Servicio.Categoria.CORTES,
            precio_base=Decimal("20000.00"),
        )
        cobros = CajaService.registrar_cobros_carrito(
            items=[
                {
                    "tipo": Cobro.Tipo.SERVICIO,
                    "cantidad": 1,
                    "precio_unitario": Decimal("20000.00"),
                    "servicio": servicio,
                },
                {
                    "tipo": Cobro.Tipo.SERVICIO,
                    "cantidad": 1,
                    "precio_unitario": Decimal("20000.00"),
                    "servicio": servicio,
                },
            ],
            cliente_nombre="Gala Grupo",
            profesional=empleada,
            medio_pago=Cobro.MedioPago.EFECTIVO,
        )
        ventas = FacturaService.agrupar_ventas(cobros)
        assert len(ventas) == 1
        assert ventas[0]["es_grupo"] is True
        assert [c.pk for c in ventas[0]["cobros"]] == [c.pk for c in cobros]
        assert ventas[0]["total"] == Decimal("36000.00")

    def test_ventas_distintas_van_en_filas_separadas(self) -> None:
        empleada = EmpleadaFactory()
        primero = self._cobro_simple("Hada Sola", profesional=empleada)
        segundo = self._cobro_simple("Iris Sola", profesional=empleada)
        ventas = FacturaService.agrupar_ventas([primero, segundo])
        assert len(ventas) == 2
        assert all(v["es_grupo"] is False for v in ventas)
        # Más recientes primero.
        assert ventas[0]["principal"].pk == segundo.pk

    def test_misma_clienta_separada_en_tiempo_no_se_agrupa(self) -> None:
        from datetime import timedelta

        from django.utils import timezone

        empleada = EmpleadaFactory()
        primero = self._cobro_simple("Jana Tiempo", profesional=empleada)
        segundo = self._cobro_simple("Jana Tiempo", profesional=empleada)
        Cobro.objects.filter(pk=segundo.pk).update(
            fecha_creacion=timezone.now() + timedelta(minutes=5)
        )
        primero.refresh_from_db()
        segundo.refresh_from_db()
        ventas = FacturaService.agrupar_ventas([primero, segundo])
        assert len(ventas) == 2


@pytest.mark.django_db
class TestAnularVentaEnConjunto:
    """Un solo botón anula todos los ítems de la venta y repone stock."""

    def test_anular_venta_da_de_baja_todos_los_items(self) -> None:
        empleada = EmpleadaFactory()
        servicio = ServicioService.crear_servicio(
            nombre="Corte Anular",
            categoria=Servicio.Categoria.CORTES,
            precio_base=Decimal("20000.00"),
        )
        producto = Producto.objects.create(
            nombre="Crema Anular",
            precio=Decimal("10000.00"),
            stock_actual=10,
            stock_minimo=2,
            activo=True,
        )
        cobros = CajaService.registrar_cobros_carrito(
            items=[
                {
                    "tipo": Cobro.Tipo.SERVICIO,
                    "cantidad": 1,
                    "precio_unitario": Decimal("20000.00"),
                    "servicio": servicio,
                },
                {
                    "tipo": Cobro.Tipo.PRODUCTO,
                    "cantidad": 2,
                    "precio_unitario": Decimal("10000.00"),
                    "producto": producto,
                },
            ],
            cliente_nombre="Karla Anular",
            profesional=empleada,
            medio_pago=Cobro.MedioPago.EFECTIVO,
        )
        anulados = CajaService.anular_venta(cobros, usuario=empleada)
        assert len(anulados) == 2
        assert all(c.anulado for c in anulados)
        producto.refresh_from_db()
        assert producto.stock_actual == 10

    def test_anular_venta_vacia_rechazada(self) -> None:
        from apps.pagos.services import CobroInvalidoError

        with pytest.raises(CobroInvalidoError):
            CajaService.anular_venta([], usuario=None)
