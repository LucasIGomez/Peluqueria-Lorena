"""
Peluquería Lorena — Tests unitarios de la capa de servicios de Inventario.

Valida todas las reglas de negocio de InventarioService para:
- RF 7.1: Gestión de productos con movimientos automáticos de alta/baja.
- RF 7.2: Descuento manual de stock con auditoría.
- Agregar / Reponer Stock.
- RF 7.3: Alertas automáticas de stock mínimo.
- Historial de movimientos con buscador inteligente.
"""
from decimal import Decimal
import pytest

from apps.inventario.models import MovimientoStock, Producto
from apps.inventario.services import (
    CantidadInvalidaError,
    InventarioService,
    ProductoNoEncontradoError,
    StockInsuficienteError,
)
from apps.usuarios.models import Usuario


@pytest.mark.django_db
class TestInventarioServiceCRUD:
    """RF 7.1: Pruebas de creación, actualización y baja de productos."""

    def test_crear_producto_exitoso_y_movimiento_automatico(self) -> None:
        """Verifica la creación correcta de un producto y su movimiento automático de 'Producto añadido'."""
        producto = InventarioService.crear_producto(
            nombre="Tratamiento Botox Capilar",
            precio=Decimal("6500.00"),
            stock_actual=15,
            stock_minimo=5,
            descripcion="Nutrición profunda para cabello dañado",
        )
        assert producto.id is not None
        assert producto.nombre == "Tratamiento Botox Capilar"
        assert producto.precio == Decimal("6500.00")
        assert producto.stock_actual == 15
        assert producto.stock_minimo == 5
        assert producto.activo is True

        # Verifica el movimiento de auditoría registrado
        movimiento = MovimientoStock.objects.filter(producto=producto).first()
        assert movimiento is not None
        assert movimiento.tipo_movimiento == MovimientoStock.TipoMovimiento.ALTA_PRODUCTO
        assert movimiento.cantidad == 15
        assert movimiento.stock_previo == 0
        assert movimiento.stock_posterior == 15

    def test_crear_producto_valores_negativos_lanza_error(self) -> None:
        """Verifica que no se permitan stocks o precios negativos."""
        with pytest.raises(CantidadInvalidaError):
            InventarioService.crear_producto(
                nombre="Producto Inválido",
                precio=Decimal("-10.00"),
                stock_actual=5,
                stock_minimo=1,
            )

        with pytest.raises(CantidadInvalidaError):
            InventarioService.crear_producto(
                nombre="Producto Inválido",
                precio=Decimal("100.00"),
                stock_actual=-1,
                stock_minimo=1,
            )

    def test_actualizar_producto_exitoso(self) -> None:
        """Verifica la actualización de atributos de un producto (nombre, precio, stock mínimo)."""
        producto = InventarioService.crear_producto(
            nombre="Aceite de Argán",
            precio=Decimal("3500.00"),
            stock_actual=10,
            stock_minimo=2,
        )
        actualizado = InventarioService.actualizar_producto(
            producto=producto,
            nombre="Aceite de Argán Puro 60ml",
            precio=Decimal("4200.00"),
            stock_minimo=4,
        )
        assert actualizado.nombre == "Aceite de Argán Puro 60ml"
        assert actualizado.precio == Decimal("4200.00")
        assert actualizado.stock_minimo == 4

    def test_baja_logica_producto_registra_movimiento(self) -> None:
        """Verifica que eliminar_producto realice baja lógica y registre 'Producto eliminado' en historial."""
        producto = InventarioService.crear_producto(
            nombre="Ampolla Reparadora",
            precio=Decimal("1200.00"),
            stock_actual=20,
        )
        InventarioService.eliminar_producto(producto, permanente=False)
        producto.refresh_from_db()
        assert producto.activo is False

        mov_baja = MovimientoStock.objects.filter(
            producto=producto,
            tipo_movimiento=MovimientoStock.TipoMovimiento.BAJA_PRODUCTO,
        ).first()
        assert mov_baja is not None
        assert "eliminado" in mov_baja.motivo

    def test_baja_permanente_producto(self) -> None:
        """Verifica que eliminar_producto con permanente=True borre el registro de la BD."""
        producto = InventarioService.crear_producto(
            nombre="Producto Temporal",
            precio=Decimal("500.00"),
            stock_actual=1,
        )
        prod_id = producto.id
        InventarioService.eliminar_producto(producto, permanente=True)
        assert Producto.objects.filter(pk=prod_id).exists() is False

    def test_listar_productos_con_filtros_y_busqueda(self) -> None:
        """Verifica el filtrado por texto inteligente y por estado activo."""
        InventarioService.crear_producto(nombre="Tintura 7.1 Rubio Ceniza", precio="2000.00")
        InventarioService.crear_producto(nombre="Tintura 8.0 Rubio Claro", precio="2000.00")
        desactivado = InventarioService.crear_producto(
            nombre="Tintura 1.0 Negro", precio="2000.00", activo=False
        )

        activos = InventarioService.listar_productos(solo_activos=True)
        assert activos.count() == 2
        assert desactivado not in activos

        busqueda = InventarioService.listar_productos(busqueda="Ceniza")
        assert busqueda.count() == 1
        assert busqueda.first().nombre == "Tintura 7.1 Rubio Ceniza"


@pytest.mark.django_db
class TestInventarioServiceDescuentoYReposicion:
    """RF 7.2 & RF 7.3: Pruebas del consumo de stock, reposición y alertas automáticas."""

    def test_registrar_consumo_servicio_exitoso(self, db) -> None:
        """RF 7.2: Verifica el descuento manual de stock con registro de 'Descuento de Stock'."""
        producto = InventarioService.crear_producto(
            nombre="Decolorante Premium 500g",
            precio=Decimal("4500.00"),
            stock_actual=10,
            stock_minimo=3,
        )

        movimiento, alerta = InventarioService.registrar_consumo_servicio(
            producto_o_id=producto,
            cantidad=3,
            detalle_servicio="Decoloración completa mechas clienta Mariana",
        )

        producto.refresh_from_db()
        assert producto.stock_actual == 7
        assert alerta is False  # 7 > stock_minimo 3 -> no hay alerta

        assert movimiento.producto == producto
        assert movimiento.cantidad == 3
        assert movimiento.stock_previo == 10
        assert movimiento.stock_posterior == 7
        assert movimiento.tipo_movimiento == MovimientoStock.TipoMovimiento.DESCUENTO
        assert "Mariana" in movimiento.motivo

    def test_descuento_stock_dispara_alerta_stock_minimo(self, db) -> None:
        """RF 7.3: Verifica que cuando el stock cae a <= stock_minimo se dispare la alerta."""
        producto = InventarioService.crear_producto(
            nombre="Fijador Fuerte 400ml",
            precio=Decimal("2800.00"),
            stock_actual=5,
            stock_minimo=3,
        )

        # Descontamos 2 unidades -> stock queda en 3 (igual al mínimo)
        movimiento, alerta = InventarioService.descontar_stock(
            producto_o_id=producto,
            cantidad=2,
            motivo="Peinado de fiesta para evento",
        )

        producto.refresh_from_db()
        assert producto.stock_actual == 3
        assert alerta is True  # Dispara alerta de stock mínimo

        bajo_stock = InventarioService.obtener_productos_bajo_stock()
        assert producto in bajo_stock

    def test_descuento_stock_insuficiente_lanza_excepcion(self, db) -> None:
        """RF 7.2: Verifica que si no hay stock suficiente se lance StockInsuficienteError."""
        producto = InventarioService.crear_producto(
            nombre="Ampolla Ácido Hialurónico",
            precio=Decimal("1800.00"),
            stock_actual=2,
            stock_minimo=1,
        )

        with pytest.raises(StockInsuficienteError) as exc_info:
            InventarioService.descontar_stock(
                producto_o_id=producto,
                cantidad=5,
                motivo="Tratamiento múltiple",
            )

        assert "Stock insuficiente" in str(exc_info.value)
        producto.refresh_from_db()
        assert producto.stock_actual == 2

    def test_reponer_stock_exitoso_y_auditoria(self, db) -> None:
        """Verifica el ingreso de mercadería y generación de MovimientoStock tipo REPOSICION."""
        producto = InventarioService.crear_producto(
            nombre="Guantes Nitrilo Caja 100u",
            precio=Decimal("5200.00"),
            stock_actual=2,
            stock_minimo=4,
        )
        assert producto.verificar_stock_minimo() is True

        movimiento = InventarioService.reponer_stock(
            producto_o_id=producto,
            cantidad=10,
            motivo="Compra a Distribuidora Belleza Sur",
        )

        producto.refresh_from_db()
        assert producto.stock_actual == 12
        assert producto.verificar_stock_minimo() is False
        assert movimiento.tipo_movimiento == MovimientoStock.TipoMovimiento.REPOSICION
        assert movimiento.stock_previo == 2
        assert movimiento.stock_posterior == 12

    def test_obtener_historial_movimientos_buscador_inteligente(self, db) -> None:
        """Verifica la consulta de historial con buscador inteligente por nombre y filtros."""
        prod1 = InventarioService.crear_producto(nombre="Shampoo Ácido", precio="100.00", stock_actual=20)
        prod2 = InventarioService.crear_producto(nombre="Acondicionador Neutro", precio="200.00", stock_actual=20)

        InventarioService.descontar_stock(prod1, 5, motivo="Servicio lavado")
        InventarioService.reponer_stock(prod2, 10, motivo="Reposición stock mensual")

        # Búsqueda inteligente por nombre de producto
        movs_busqueda = InventarioService.obtener_historial_movimientos(busqueda="Shampoo")
        # prod1 tiene 2 movimientos: ALTA_PRODUCTO y DESCUENTO
        assert movs_busqueda.count() == 2
        assert all("Shampoo" in m.producto.nombre for m in movs_busqueda)

        # Filtro por tipo de movimiento
        movs_reposicion = InventarioService.obtener_historial_movimientos(
            tipo_movimiento=MovimientoStock.TipoMovimiento.REPOSICION
        )
        assert movs_reposicion.count() == 1
        assert movs_reposicion.first().producto == prod2
