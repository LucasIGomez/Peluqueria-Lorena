"""
Peluquería Lorena — Tests de integración de vistas y API de Inventario.

Valida:
- RF 7.1: Vistas CRUD de productos (con edición sin alteración directa de stock).
- Agregar / Reponer Stock.
- RF 7.2: Vista y endpoint de descuento manual de stock en servicios.
- RF 7.3: Visualización de alertas de stock mínimo y mensajes contextuales.
- Historial con buscador inteligente.
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.inventario.models import MovimientoStock, Producto
from apps.inventario.services import InventarioService
from tests.factories.usuario_factory import EmpleadaFactory


@pytest.mark.django_db
class TestInventarioWebViews:
    """Pruebas de integración de las vistas basadas en plantillas HTML."""

    @pytest.fixture(autouse=True)
    def _login(self, db, client):
        """Las vistas web de inventario exigen sesión iniciada."""
        client.force_login(EmpleadaFactory(email="inventario.web@test.com"))

    def test_acceso_sin_login_redirige_a_login(self) -> None:
        """Un visitante sin sesión no puede entrar al inventario."""
        from django.test import Client

        anon = Client()
        response = anon.get(reverse("inventario:lista_productos"))
        assert response.status_code == 302
        assert "/usuarios/login/" in response.url

    def test_lista_productos_retorna_200_y_muestra_datos(self, client) -> None:
        """Verifica la carga del listado de productos."""
        Producto.objects.create(
            nombre="Shampoo Anticaspa 300ml",
            precio=Decimal("3200.00"),
            stock_actual=12,
            stock_minimo=3,
        )
        url = reverse("inventario:lista_productos")
        response = client.get(url)

        assert response.status_code == 200
        assert "Shampoo Anticaspa 300ml" in response.content.decode("utf-8")
        assert "Listado de Productos" in response.content.decode("utf-8")

    def test_lista_productos_muestra_alerta_bajo_stock(self, client) -> None:
        """RF 7.3: Verifica que la lista muestre el banner y badge de alerta cuando hay bajo stock."""
        Producto.objects.create(
            nombre="Tinte 6.0 Castaño Claro",
            precio=Decimal("2500.00"),
            stock_actual=1,
            stock_minimo=3,
        )
        url = reverse("inventario:lista_productos")
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "¡Atención! Hay 1 producto(s) en nivel de stock mínimo" in content
        assert "Bajo Stock" in content

    def test_crear_producto_formulario_web(self, client) -> None:
        """RF 7.1: Alta de producto mediante formulario web y registro de 'Producto añadido'."""
        url = reverse("inventario:crear_producto")
        response_get = client.get(url)
        assert response_get.status_code == 200

        data = {
            "nombre": "Mascara Capilar Nutritiva",
            "descripcion": "Tratamiento intensivo con argán",
            "precio": "4500.00",
            "stock_actual": 8,
            "stock_minimo": 2,
        }
        response_post = client.post(url, data, follow=True)
        assert response_post.status_code == 200

        producto = Producto.objects.filter(nombre="Mascara Capilar Nutritiva").first()
        assert producto is not None
        assert producto.stock_actual == 8
        assert producto.stock_minimo == 2

        movimiento = MovimientoStock.objects.filter(producto=producto).first()
        assert movimiento is not None
        assert movimiento.tipo_movimiento == MovimientoStock.TipoMovimiento.ALTA_PRODUCTO
        assert movimiento.cantidad == 8

    def test_editar_producto_formulario_web(self, client) -> None:
        """RF 7.1: Edición de producto existente (solo modifica nombre, descripción, precio y stock mínimo)."""
        producto = Producto.objects.create(
            nombre="Cera Modeladora",
            precio=Decimal("2000.00"),
            stock_actual=10,
            stock_minimo=3,
        )
        url = reverse("inventario:editar_producto", kwargs={"pk": producto.pk})
        response_get = client.get(url)
        assert response_get.status_code == 200

        data = {
            "nombre": "Cera Modeladora Efecto Mate 100g",
            "descripcion": "Nueva fórmula fijación fuerte",
            "precio": "2600.00",
            "stock_minimo": 5,
        }
        response_post = client.post(url, data, follow=True)
        assert response_post.status_code == 200

        producto.refresh_from_db()
        assert producto.nombre == "Cera Modeladora Efecto Mate 100g"
        assert producto.stock_actual == 10  # Stock actual intacto
        assert producto.precio == Decimal("2600.00")
        assert producto.stock_minimo == 5

    def test_reponer_stock_formulario_web(self, client) -> None:
        """Verifica la vista para Agregar / Reponer Stock."""
        producto = Producto.objects.create(
            nombre="Oxigenta 30 vol 1L",
            precio=Decimal("1800.00"),
            stock_actual=4,
            stock_minimo=2,
        )
        url = reverse("inventario:reponer_stock_producto", kwargs={"pk": producto.pk})
        response_get = client.get(url)
        assert response_get.status_code == 200

        data = {
            "producto": producto.pk,
            "cantidad": 6,
            "motivo": "Compra a Distribuidora Central",
        }
        response_post = client.post(url, data, follow=True)
        assert response_post.status_code == 200

        producto.refresh_from_db()
        assert producto.stock_actual == 10

        movimiento = MovimientoStock.objects.filter(
            producto=producto, tipo_movimiento=MovimientoStock.TipoMovimiento.REPOSICION
        ).first()
        assert movimiento is not None
        assert movimiento.cantidad == 6

    def test_eliminar_producto_baja_logica_registra_movimiento(self, client) -> None:
        """RF 7.1: Baja lógica de producto registra 'Producto eliminado'."""
        producto = Producto.objects.create(
            nombre="Producto Descontinuado",
            precio=Decimal("1000.00"),
            stock_actual=0,
            stock_minimo=0,
        )
        url = reverse("inventario:eliminar_producto", kwargs={"pk": producto.pk})
        response_get = client.get(url)
        assert response_get.status_code == 200

        response_post = client.post(url, {}, follow=True)
        assert response_post.status_code == 200

        producto.refresh_from_db()
        assert producto.activo is False

        mov_baja = MovimientoStock.objects.filter(
            producto=producto, tipo_movimiento=MovimientoStock.TipoMovimiento.BAJA_PRODUCTO
        ).first()
        assert mov_baja is not None

    def test_descontar_stock_servicio_exitoso_web(self, client) -> None:
        """RF 7.2: Descuento manual de stock por servicio a través de la vista web."""
        producto = Producto.objects.create(
            nombre="Decolorante Azul 500g",
            precio=Decimal("5000.00"),
            stock_actual=10,
            stock_minimo=2,
        )
        url = reverse("inventario:descontar_stock_producto", kwargs={"pk": producto.pk})
        response_get = client.get(url)
        assert response_get.status_code == 200

        data = {
            "producto": producto.pk,
            "cantidad": 3,
            "detalle_servicio": "Decoloración completa para servicio de Balayage clienta Romina",
        }
        response_post = client.post(url, data, follow=True)
        assert response_post.status_code == 200

        producto.refresh_from_db()
        assert producto.stock_actual == 7

        movimiento = MovimientoStock.objects.filter(
            producto=producto, tipo_movimiento=MovimientoStock.TipoMovimiento.DESCUENTO
        ).first()
        assert movimiento is not None
        assert movimiento.cantidad == 3
        assert movimiento.stock_previo == 10
        assert movimiento.stock_posterior == 7

    def test_descontar_stock_servicio_dispara_alerta_minimo_mensaje(self, client) -> None:
        """RF 7.3: Descuento que alcanza stock mínimo muestra mensaje de alerta en la respuesta."""
        producto = Producto.objects.create(
            nombre="Ampolla Reparadora Intensiva",
            precio=Decimal("1500.00"),
            stock_actual=4,
            stock_minimo=3,
        )
        url = reverse("inventario:descontar_stock_producto", kwargs={"pk": producto.pk})
        data = {
            "producto": producto.pk,
            "cantidad": 2,  # Deja stock en 2 (menor que el mínimo 3)
            "detalle_servicio": "Nutrición capilar post-color",
        }
        response = client.post(url, data, follow=True)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "ALERTA DE STOCK M" in content or "alcanzó el nivel crítico" in content

    def test_descontar_stock_insuficiente_muestra_error(self, client) -> None:
        """RF 7.2: Intento de descuento con stock insuficiente muestra error de validación."""
        producto = Producto.objects.create(
            nombre="Protector Solar Capilar",
            precio=Decimal("3000.00"),
            stock_actual=1,
            stock_minimo=1,
        )
        url = reverse("inventario:descontar_stock_general")
        data = {
            "producto": producto.pk,
            "cantidad": 5,
            "detalle_servicio": "Consumo excesivo",
        }
        response = client.post(url, data)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "No hay suficiente stock disponible" in content
        producto.refresh_from_db()
        assert producto.stock_actual == 1

    def test_historial_movimientos_vista_200_con_busqueda(self, client) -> None:
        """Verifica la carga del historial de movimientos con buscador inteligente."""
        producto = Producto.objects.create(
            nombre="Producto Test Movimientos",
            precio=Decimal("1000.00"),
            stock_actual=5,
            stock_minimo=1,
        )
        InventarioService.descontar_stock(producto, 2, motivo="Corte y peinado especial")

        url = reverse("inventario:historial_movimientos") + "?q=Movimientos"
        response = client.get(url)
        assert response.status_code == 200
        assert "Corte y peinado especial" in response.content.decode("utf-8")


@pytest.mark.django_db
class TestInventarioApi:
    """Pruebas de los endpoints REST de la API de Inventario."""

    def test_api_listar_productos(self, authenticated_client_empleada) -> None:
        """Verifica el endpoint GET /inventario/api/."""
        Producto.objects.create(
            nombre="Tónico Capilar Anticaída",
            precio=Decimal("4800.00"),
            stock_actual=7,
            stock_minimo=2,
        )
        response = authenticated_client_empleada.get("/inventario/api/")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_api_descontar_servicio_exitoso(self, authenticated_client_empleada) -> None:
        """RF 7.2: Descuento de stock vía API POST /inventario/api/{id}/descontar-servicio/."""
        producto = Producto.objects.create(
            nombre="Serum Brillo Espejo",
            precio=Decimal("3600.00"),
            stock_actual=10,
            stock_minimo=2,
        )
        data = {
            "cantidad": 3,
            "motivo": "Tratamiento de brillo final en peinado",
        }
        response = authenticated_client_empleada.post(
            f"/inventario/api/{producto.pk}/descontar-servicio/",
            data=data,
            format="json",
        )
        assert response.status_code == 200
        assert response.data["mensaje"] == "Consumo de stock registrado exitosamente."
        assert response.data["alerta_stock_minimo"] is False

        producto.refresh_from_db()
        assert producto.stock_actual == 7

    def test_api_reponer_stock_exitoso(self, authenticated_client_empleada) -> None:
        """Verifica endpoint API POST /inventario/api/{id}/reponer/."""
        producto = Producto.objects.create(
            nombre="Crema Enjuague 1L",
            precio=Decimal("2200.00"),
            stock_actual=5,
            stock_minimo=2,
        )
        data = {
            "cantidad": 10,
            "motivo": "Ingreso mercadería API",
        }
        response = authenticated_client_empleada.post(
            f"/inventario/api/{producto.pk}/reponer/",
            data=data,
            format="json",
        )
        assert response.status_code == 200
        assert response.data["mensaje"] == "Stock agregado exitosamente."

        producto.refresh_from_db()
        assert producto.stock_actual == 15

    def test_api_bajo_stock_endpoint(self, authenticated_client_empleada) -> None:
        """RF 7.3: Endpoint GET /inventario/api/bajo-stock/."""
        Producto.objects.create(
            nombre="Producto Crítico",
            precio=Decimal("1500.00"),
            stock_actual=1,
            stock_minimo=3,
        )
        response = authenticated_client_empleada.get("/inventario/api/bajo-stock/")
        assert response.status_code == 200
        assert response.data["total_alertas"] >= 1
        assert any(p["nombre"] == "Producto Crítico" for p in response.data["productos"])
