"""
Peluquería Lorena — Control de acceso por rol en Proveedores e Inventario (RNF 1.2).

Reglas:
- Proveedores y órdenes de compra: solo la Administradora.
- Alta, edición y baja de productos (web y API): solo la Administradora.
- Reponer, descontar, consultar y ver el historial de stock: Empleada y Administradora.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.inventario.models import Producto
from apps.proveedores.models import Proveedor
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.fixture
def producto(db) -> Producto:
    return Producto.objects.create(nombre="Shampoo Permisos", precio=Decimal("3000.00"), stock_actual=10, stock_minimo=2)


@pytest.fixture
def proveedor(db) -> Proveedor:
    return Proveedor.objects.create(nombre="Distribuidora Permisos", contacto="3704000000")


@pytest.mark.django_db
class TestProveedoresSoloAdministradora:
    def _urls(self, proveedor):
        return [
            reverse("proveedores:lista_proveedores"),
            reverse("proveedores:crear_proveedor"),
            reverse("proveedores:editar_proveedor", kwargs={"pk": proveedor.pk}),
            reverse("proveedores:eliminar_proveedor", kwargs={"pk": proveedor.pk}),
            reverse("proveedores:generar_orden"),
        ]

    def test_empleada_no_entra_a_ninguna_pantalla_de_proveedores(self, client, proveedor) -> None:
        client.force_login(EmpleadaFactory(email="emp.prov@test.com"))
        for url in self._urls(proveedor):
            respuesta = client.get(url)
            assert respuesta.status_code == 302, url
            assert not respuesta.url.startswith("/proveedores/"), url

    def test_empleada_no_puede_eliminar_un_proveedor(self, client, proveedor) -> None:
        client.force_login(EmpleadaFactory(email="emp.prov2@test.com"))
        client.post(reverse("proveedores:eliminar_proveedor", kwargs={"pk": proveedor.pk}))
        assert Proveedor.objects.filter(pk=proveedor.pk).exists()

    def test_empleada_no_puede_crear_producto_desde_proveedores(self, client) -> None:
        client.force_login(EmpleadaFactory(email="emp.prov3@test.com"))
        respuesta = client.post(
            reverse("proveedores:crear_producto_ajax"),
            data='{"nombre": "Intruso", "precio": 1}',
            content_type="application/json",
        )
        assert respuesta.status_code == 302
        assert not Producto.objects.filter(nombre="Intruso").exists()

    def test_visitante_sin_sesion_no_entra(self, client, proveedor) -> None:
        respuesta = client.get(reverse("proveedores:lista_proveedores"))
        assert respuesta.status_code == 302

    def test_administradora_si_entra(self, client, proveedor) -> None:
        client.force_login(AdministradoraFactory(email="admin.prov@test.com"))
        for url in self._urls(proveedor):
            assert client.get(url).status_code == 200, url


@pytest.mark.django_db
class TestInventarioWebPorRol:
    def test_empleada_no_puede_crear_editar_ni_eliminar_productos(self, client, producto) -> None:
        client.force_login(EmpleadaFactory(email="emp.inv@test.com"))
        for nombre, kwargs in [
            ("inventario:crear_producto", {}),
            ("inventario:editar_producto", {"pk": producto.pk}),
            ("inventario:eliminar_producto", {"pk": producto.pk}),
        ]:
            respuesta = client.get(reverse(nombre, kwargs=kwargs))
            assert respuesta.status_code == 302, nombre
        client.post(reverse("inventario:eliminar_producto", kwargs={"pk": producto.pk}))
        producto.refresh_from_db()
        assert producto.activo is True

    def test_empleada_si_puede_consultar_reponer_y_descontar(self, client, producto) -> None:
        client.force_login(EmpleadaFactory(email="emp.inv2@test.com"))
        for nombre, kwargs in [
            ("inventario:lista_productos", {}),
            ("inventario:historial_movimientos", {}),
            ("inventario:reponer_stock_producto", {"pk": producto.pk}),
            ("inventario:descontar_stock_producto", {"pk": producto.pk}),
        ]:
            assert client.get(reverse(nombre, kwargs=kwargs)).status_code == 200, nombre

    def test_administradora_si_puede_crear_editar_y_eliminar(self, client, producto) -> None:
        client.force_login(AdministradoraFactory(email="admin.inv@test.com"))
        for nombre, kwargs in [
            ("inventario:crear_producto", {}),
            ("inventario:editar_producto", {"pk": producto.pk}),
            ("inventario:eliminar_producto", {"pk": producto.pk}),
        ]:
            assert client.get(reverse(nombre, kwargs=kwargs)).status_code == 200, nombre


@pytest.mark.django_db
class TestInventarioApiPorRol:
    def test_empleada_no_puede_crear_ni_borrar_productos_por_api(self, authenticated_client_empleada, producto) -> None:
        nuevo = {"nombre": "Api Intruso", "precio": "100.00", "stock_actual": 1, "stock_minimo": 1}
        assert authenticated_client_empleada.post("/inventario/api/", nuevo, format="json").status_code == 403
        assert authenticated_client_empleada.delete(f"/inventario/api/{producto.pk}/").status_code == 403
        assert authenticated_client_empleada.patch(
            f"/inventario/api/{producto.pk}/", {"nombre": "Cambiado"}, format="json"
        ).status_code == 403
        producto.refresh_from_db()
        assert producto.activo is True and producto.nombre == "Shampoo Permisos"

    def test_empleada_si_puede_listar_por_api(self, authenticated_client_empleada, producto) -> None:
        assert authenticated_client_empleada.get("/inventario/api/").status_code == 200

    def test_administradora_si_puede_borrar_por_api(self, authenticated_client_administradora, producto) -> None:
        assert authenticated_client_administradora.delete(f"/inventario/api/{producto.pk}/").status_code == 204
