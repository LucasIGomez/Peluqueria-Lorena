"""
Pruebas unitarias del módulo de Caja y Ventas.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.inventario.models import Producto
from apps.pagos.models import CierreCaja, Cobro
from apps.pagos.services import CajaCerradaError, CajaService, CobroInvalidoError
from apps.servicios.services import ServicioService
from apps.servicios.models import Servicio
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.mark.django_db
class TestRegistroCobroYMediosPago:
    """Cobro de servicio y venta de producto con sus medios de pago."""

    def test_cobro_servicio_en_efectivo_aplica_descuento_10(self) -> None:
        empleada = EmpleadaFactory()
        servicio = ServicioService.crear_servicio(
            nombre="Corte Test",
            categoria=Servicio.Categoria.CORTES,
            precio_base=Decimal("25000.00"),
        )
        cobro = CajaService.registrar_cobro(
            cliente_nombre="Ana Pérez",
            profesional=empleada,
            tipo=Cobro.Tipo.SERVICIO,
            medio_pago=Cobro.MedioPago.EFECTIVO,
            cantidad=1,
            servicio=servicio,
        )
        assert cobro.subtotal == Decimal("25000.00")
        assert cobro.porcentaje_descuento == Decimal("10.00")
        assert cobro.monto_descuento == Decimal("2500.00")
        assert cobro.total == Decimal("22500.00")

    def test_cobro_tarjeta_no_aplica_descuento(self) -> None:
        empleada = EmpleadaFactory()
        cobro = CajaService.registrar_cobro(
            cliente_nombre="Bea Díaz",
            profesional=empleada,
            tipo=Cobro.Tipo.SERVICIO,
            medio_pago=Cobro.MedioPago.TARJETA_CREDITO,
            cantidad=1,
            precio_unitario=Decimal("50000.00"),
        )
        assert cobro.porcentaje_descuento == Decimal("0.00")
        assert cobro.monto_descuento == Decimal("0.00")
        assert cobro.total == Decimal("50000.00")

    def test_venta_producto_descuenta_stock(self) -> None:
        empleada = EmpleadaFactory()
        producto = Producto.objects.create(
            nombre="Shampoo Reventa",
            precio=Decimal("15000.00"),
            stock_actual=10,
            stock_minimo=2,
            activo=True,
        )
        cobro = CajaService.registrar_cobro(
            cliente_nombre="Celi Ruiz",
            profesional=empleada,
            tipo=Cobro.Tipo.PRODUCTO,
            medio_pago=Cobro.MedioPago.MERCADO_PAGO,
            cantidad=2,
            producto=producto,
        )
        assert cobro.subtotal == Decimal("30000.00")
        assert cobro.porcentaje_descuento == Decimal("10.00")
        assert cobro.monto_descuento == Decimal("3000.00")
        assert cobro.total == Decimal("27000.00")
        producto.refresh_from_db()
        assert producto.stock_actual == 8

    def test_medio_pago_invalido_rechazado(self) -> None:
        empleada = EmpleadaFactory()
        with pytest.raises(CobroInvalidoError):
            CajaService.registrar_cobro(
                cliente_nombre="Dora",
                profesional=empleada,
                medio_pago="BITCOIN",
                precio_unitario=Decimal("1000.00"),
            )


@pytest.mark.django_db
class TestDescuentoPorMedioPago:
    """Descuento automático del 10% para efectivo, Mercado Pago y Ualá."""

    @pytest.mark.parametrize(
        "medio,espera_descuento",
        [
            (Cobro.MedioPago.EFECTIVO, True),
            (Cobro.MedioPago.MERCADO_PAGO, True),
            (Cobro.MedioPago.UALA, True),
            (Cobro.MedioPago.TARJETA_DEBITO, False),
            (Cobro.MedioPago.TARJETA_CREDITO, False),
        ],
    )
    def test_descuento_segun_medio(self, medio: str, espera_descuento: bool) -> None:
        resultado = CajaService.calcular_totales(Decimal("10000.00"), medio)
        if espera_descuento:
            assert resultado["porcentaje_descuento"] == Decimal("10.00")
            assert resultado["monto_descuento"] == Decimal("1000.00")
            assert resultado["total"] == Decimal("9000.00")
        else:
            assert resultado["porcentaje_descuento"] == Decimal("0.00")
            assert resultado["total"] == Decimal("10000.00")


@pytest.mark.django_db
class TestCierreCajaYReporte:
    """Cierre diario y reporte por medio de pago."""

    def test_cierre_consolida_totales_y_bloquea_dia(self) -> None:
        empleada = EmpleadaFactory()
        admin = AdministradoraFactory()
        dia = timezone.localdate()

        CajaService.registrar_cobro(
            cliente_nombre="Eva",
            profesional=empleada,
            medio_pago=Cobro.MedioPago.EFECTIVO,
            precio_unitario=Decimal("10000.00"),
            fecha=dia,
        )
        CajaService.registrar_cobro(
            cliente_nombre="Fabi",
            profesional=empleada,
            medio_pago=Cobro.MedioPago.TARJETA_DEBITO,
            precio_unitario=Decimal("20000.00"),
            fecha=dia,
        )

        cierre = CajaService.realizar_cierre_caja(
            fecha=dia, responsable=admin, observaciones="Cierre de prueba"
        )
        assert cierre.cantidad_cobros == 2
        assert cierre.total_efectivo == Decimal("9000.00")
        assert cierre.total_tarjeta_debito == Decimal("20000.00")
        assert cierre.total_general == Decimal("29000.00")
        assert cierre.total_descuentos == Decimal("1000.00")

        # El día queda bloqueado: ni nuevos cobros ni segundo cierre.
        with pytest.raises(CajaCerradaError):
            CajaService.registrar_cobro(
                cliente_nombre="Gala",
                profesional=empleada,
                precio_unitario=Decimal("5000.00"),
                fecha=dia,
            )
        with pytest.raises(CajaCerradaError):
            CajaService.realizar_cierre_caja(fecha=dia, responsable=admin)

    def test_reporte_discriminado_por_medio(self) -> None:
        empleada = EmpleadaFactory()
        dia = timezone.localdate()
        CajaService.registrar_cobro(
            cliente_nombre="Hilda",
            profesional=empleada,
            medio_pago=Cobro.MedioPago.EFECTIVO,
            precio_unitario=Decimal("10000.00"),
            fecha=dia,
        )
        CajaService.registrar_cobro(
            cliente_nombre="Irene",
            profesional=empleada,
            medio_pago=Cobro.MedioPago.UALA,
            precio_unitario=Decimal("20000.00"),
            fecha=dia,
        )

        reporte = CajaService.reporte_por_medio_pago(fecha_desde=dia, fecha_hasta=dia)
        por_codigo = {fila["codigo"]: fila for fila in reporte["detalle"]}
        assert por_codigo[Cobro.MedioPago.EFECTIVO]["total"] == Decimal("9000.00")
        assert por_codigo[Cobro.MedioPago.UALA]["total"] == Decimal("18000.00")
        assert por_codigo[Cobro.MedioPago.UALA]["cantidad"] == 1
        assert reporte["total_general"] == Decimal("27000.00")
        assert reporte["cantidad_total"] == 2

    def test_anular_venta_repone_stock(self) -> None:
        empleada = EmpleadaFactory()
        producto = Producto.objects.create(
            nombre="Acondicionador Reventa",
            precio=Decimal("12000.00"),
            stock_actual=5,
            stock_minimo=1,
            activo=True,
        )
        cobro = CajaService.registrar_cobro(
            cliente_nombre="Juli",
            profesional=empleada,
            tipo=Cobro.Tipo.PRODUCTO,
            medio_pago=Cobro.MedioPago.EFECTIVO,
            cantidad=2,
            producto=producto,
        )
        producto.refresh_from_db()
        assert producto.stock_actual == 3

        CajaService.anular_cobro(cobro, usuario=empleada)
        producto.refresh_from_db()
        assert producto.stock_actual == 5
        cobro.refresh_from_db()
        assert cobro.anulado is True
