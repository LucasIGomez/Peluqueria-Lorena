"""
Peluquería Lorena — Tests unitarios de los modelos de Inventario.

Valida el comportamiento de los métodos de dominio de:
- Producto (RF 7.1, 7.2, 7.3)
- MovimientoStock (RF 7.2)
"""
from decimal import Decimal
import pytest

from apps.inventario.models import MovimientoStock, Producto


@pytest.mark.django_db
class TestProductoDomainMethods:
    """Pruebas unitarias de los métodos de dominio del modelo Producto."""

    def test_creacion_producto_atributos_basicos(self) -> None:
        """Verifica la correcta inicialización de atributos de Producto."""
        producto = Producto.objects.create(
            nombre="Keratina Brasileña 1L",
            descripcion="Tratamiento alisador intensivo",
            precio=Decimal("8500.00"),
            stock_actual=10,
            stock_minimo=3,
        )
        assert producto.nombre == "Keratina Brasileña 1L"
        assert producto.precio == Decimal("8500.00")
        assert producto.stock_actual == 10
        assert producto.stock_minimo == 3
        assert producto.activo is True
        assert producto.stockActual == 10
        assert producto.stockMinimo == 3

    def test_descontar_stock_exitoso(self) -> None:
        """RF 7.2: Verifica que descontar_stock reduzca la existencia cuando hay stock."""
        producto = Producto.objects.create(
            nombre="Shampoo Neutro 5L",
            precio=Decimal("4200.00"),
            stock_actual=8,
            stock_minimo=2,
        )
        resultado = producto.descontar_stock(3)
        producto.refresh_from_db()

        assert resultado is True
        assert producto.stock_actual == 5

    def test_descontar_stock_insuficiente(self) -> None:
        """RF 7.2: Verifica que descontar_stock falle y no modifique el stock si es insuficiente."""
        producto = Producto.objects.create(
            nombre="Decolorante en Polvo 500g",
            precio=Decimal("3100.00"),
            stock_actual=2,
            stock_minimo=1,
        )
        resultado = producto.descontar_stock(5)
        producto.refresh_from_db()

        assert resultado is False
        assert producto.stock_actual == 2

    def test_descontar_stock_cantidad_invalida_lanza_error(self) -> None:
        """Verifica que cantidades <= 0 lancen ValueError."""
        producto = Producto.objects.create(
            nombre="Gel Modelador",
            precio=Decimal("1500.00"),
            stock_actual=5,
            stock_minimo=2,
        )
        with pytest.raises(ValueError):
            producto.descontar_stock(0)

        with pytest.raises(ValueError):
            producto.descontar_stock(-2)

    def test_reponer_stock_aumenta_existencia(self) -> None:
        """Verifica que reponer_stock incremente el stock actual."""
        producto = Producto.objects.create(
            nombre="Serum Reparador Puntas",
            precio=Decimal("2800.00"),
            stock_actual=3,
            stock_minimo=2,
        )
        producto.reponer_stock(10)
        producto.refresh_from_db()

        assert producto.stock_actual == 13

    def test_reponer_stock_cantidad_invalida_lanza_error(self) -> None:
        """Verifica que reponer con cantidad <= 0 lance ValueError."""
        producto = Producto.objects.create(
            nombre="Crema de Enjuague",
            precio=Decimal("1900.00"),
            stock_actual=4,
        )
        with pytest.raises(ValueError):
            producto.reponer_stock(0)

    def test_verificar_stock_minimo_y_propiedad_esta_bajo_stock(self) -> None:
        """RF 7.3: Verifica el cálculo automático de alerta de stock mínimo."""
        producto = Producto.objects.create(
            nombre="Oxigenta 20 vol",
            precio=Decimal("1200.00"),
            stock_actual=5,
            stock_minimo=3,
        )
        # Con stock 5 > min 3: No está bajo stock
        assert producto.verificar_stock_minimo() is False
        assert producto.esta_bajo_stock is False

        # Descontamos 2 -> stock = 3 (igual al mínimo): Debe estar bajo stock
        producto.descontar_stock(2)
        assert producto.verificar_stock_minimo() is True
        assert producto.esta_bajo_stock is True

        # Descontamos 2 más -> stock = 1 (< mínimo): Debe estar bajo stock
        producto.descontar_stock(2)
        assert producto.verificar_stock_minimo() is True
        assert producto.esta_bajo_stock is True

    def test_baja_logica_y_reactivacion(self) -> None:
        """RF 7.1: Verifica que dar_de_baja desactive y reactivar active el producto."""
        producto = Producto.objects.create(
            nombre="Tinte Fantasía Fucsia",
            precio=Decimal("2500.00"),
            stock_actual=4,
        )
        assert producto.activo is True

        producto.dar_de_baja()
        producto.refresh_from_db()
        assert producto.activo is False

        producto.reactivar()
        producto.refresh_from_db()
        assert producto.activo is True

    def test_str_representation(self) -> None:
        """Verifica el formato del método __str__."""
        producto = Producto.objects.create(
            nombre="Cera Capilar Mate",
            precio=Decimal("3000.00"),
            stock_actual=7,
        )
        assert "Cera Capilar Mate" in str(producto)
        assert "7" in str(producto)


@pytest.mark.django_db
class TestMovimientoStockDomain:
    """Pruebas unitarias del modelo de auditoría MovimientoStock."""

    def test_creacion_movimiento_stock_campos(self) -> None:
        """RF 7.2: Verifica la persistencia de datos y trazabilidad en MovimientoStock."""
        producto = Producto.objects.create(
            nombre="Protector Térmico 250ml",
            precio=Decimal("3400.00"),
            stock_actual=10,
            stock_minimo=2,
        )
        movimiento = MovimientoStock.objects.create(
            producto=producto,
            tipo_movimiento=MovimientoStock.TipoMovimiento.CONSUMO_SERVICIO,
            cantidad=2,
            stock_previo=10,
            stock_posterior=8,
            motivo="Alisado definitivo clienta Laura",
        )
        assert movimiento.producto == producto
        assert movimiento.cantidad == 2
        assert movimiento.stock_previo == 10
        assert movimiento.stock_posterior == 8
        assert movimiento.tipo_movimiento == MovimientoStock.TipoMovimiento.CONSUMO_SERVICIO
        assert "Alisado" in movimiento.motivo
        assert "Protector Térmico" in str(movimiento)
