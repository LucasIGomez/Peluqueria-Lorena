"""
Pruebas de integración web para los módulos de Servicios y Clientes.
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, TratamientoProgreso
from apps.inventario.models import Producto
from apps.servicios.models import ConsentimientoInformado, Servicio, ServicioRealizado
from apps.servicios.services import ServicioService
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.mark.django_db
class TestServiciosWebViews:
    """Pruebas de integración de las pantallas web de servicios y cierre de insumos."""

    def test_catalogo_web_renderiza_servicios_oficiales(self, client) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)

        url = reverse("servicios:catalogo")
        response = client.get(url)
        assert response.status_code == 200
        # Debe haber cargado automáticamente la lista oficial si estaba vacía
        assert "Corte Damas" in response.content.decode("utf-8")
        assert "Balayage (desde)" in response.content.decode("utf-8")
        assert "120000" in response.content.decode("utf-8")

    def test_vistas_servicios_exigen_login(self, client) -> None:
        """Un visitante sin sesión no puede acceder a las pantallas de servicios."""
        for nombre_url in (
            "servicios:catalogo",
            "servicios:control_diario",
            "servicios:registrar_servicio_realizado",
            "servicios:crear_consentimiento",
            "servicios:cierre_diario",
        ):
            response = client.get(reverse(nombre_url))
            assert response.status_code == 302
            assert "/usuarios/login/" in response.url

    def test_control_diario_web(self, client) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)

        url = reverse("servicios:control_diario")
        response = client.get(url)
        assert response.status_code == 200
        assert "Control Diario de Servicios" in response.content.decode("utf-8")

    def test_registrar_servicio_web_personalizando_tarifa(self, client) -> None:
        profesional = EmpleadaFactory()
        client.force_login(profesional)

        servicio = ServicioService.crear_servicio(
            nombre="Alisado Especial",
            categoria=Servicio.Categoria.TRATAMIENTOS,
            precio_base=Decimal("80000.00"),
            duracion_estimada_minutos=180,
        )

        url = reverse("servicios:registrar_servicio_realizado")
        payload = {
            "servicio": servicio.id,
            "profesional": profesional.id,
            "cliente_nombre": "Marina López",
            "cliente_telefono": "1166778899",
            "fecha": timezone.localdate().isoformat(),
            "hora": "14:30",
            "precio_acordado": "95000.00",  # Precio personalizado por largo de cabello
            "duracion_minutos": "210",       # Tiempo personalizado
            "estado": ServicioRealizado.Estado.COMPLETADO,
            "notas": "Cabello rizado abundante",
        }

        response = client.post(url, data=payload, follow=True)
        assert response.status_code == 200

        servicio_guardado = ServicioRealizado.objects.get(cliente_nombre="Marina López")
        assert servicio_guardado.precio_acordado == Decimal("95000.00")
        assert servicio_guardado.duracion_minutos == 210

    def test_crear_consentimiento_informado_web(self, client) -> None:
        admin = AdministradoraFactory()
        client.force_login(admin)

        url = reverse("servicios:crear_consentimiento")
        payload = {
            "cliente_nombre": "Carolina Balayage",
            "cliente_dni": "33444555",
            "tipo_procedimiento": ConsentimientoInformado.TipoProcedimiento.DECOLORACION_MECHAS,
            "profesional": admin.id,
            "acepta_terminos": True,
            "firma_digital": "Carolina Balayage Conforme",
            "observaciones": "Fibra en excelente estado.",
        }

        response = client.post(url, data=payload)
        assert response.status_code == 302
        consentimiento = ConsentimientoInformado.objects.get(cliente_nombre="Carolina Balayage")
        assert f"/servicios/consentimiento/{consentimiento.pk}/" in response.url

        # Visualizar la ficha imprimible
        resp_ficha = client.get(response.url)
        assert resp_ficha.status_code == 200
        assert "PELUQUERÍA LORENA" in resp_ficha.content.decode("utf-8")
        assert "Consentimiento Informado" in resp_ficha.content.decode("utf-8")

    def test_cierre_diario_web_descuenta_stock(self, client) -> None:
        admin = AdministradoraFactory()
        client.force_login(admin)
        dia = timezone.localdate()

        # Insumo
        producto = Producto.objects.create(
            nombre="Oxigenta 30 vol 1L",
            stock_actual=15,
            stock_minimo=2,
            precio=Decimal("12000.00"),
            activo=True,
        )

        servicio = ServicioService.crear_servicio(
            nombre="Mechas Iluminación",
            categoria=Servicio.Categoria.MECHAS,
            precio_base=Decimal("90000.00"),
        )

        # 2 servicios completados
        for i in range(2):
            ServicioService.registrar_servicio_realizado(
                servicio=servicio,
                profesional=admin,
                cliente_nombre=f"Clienta Mechas {i+1}",
                fecha=dia,
                estado=ServicioRealizado.Estado.COMPLETADO,
            )

        url = reverse("servicios:cierre_diario")
        payload = {
            "servicio_id": servicio.id,
            "producto_id[]": [str(producto.id)],
            "cantidad[]": ["3"],  # 3 litros para las 2 clientas
        }

        response = client.post(f"{url}?fecha={dia.isoformat()}", data=payload, follow=True)
        assert response.status_code == 200

        producto.refresh_from_db()
        assert producto.stock_actual == 12  # 15 - 3 = 12


@pytest.mark.django_db
class TestClientesWebViews:
    """Pruebas de integración de la ficha de clientas y tratamientos multisesión."""

    def test_clientes_web_crud_y_tratamiento(self, client) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)

        # 1. Crear clienta
        url_crear = reverse("clientes:crear_cliente")
        payload_cliente = {
            "nombre": "Lorena Clienta VIP",
            "telefono": "1133221100",
            "email": "lore@vip.com",
            "fecha_nacimiento": timezone.localdate().isoformat(),
            "notas_alergias": "Ninguna",
            "preferencias": "Corte bob texturizado",
        }
        res_crear = client.post(url_crear, data=payload_cliente)
        assert res_crear.status_code == 302

        cliente_obj = Cliente.objects.get(nombre="Lorena Clienta VIP")
        assert cliente_obj.telefono == "1133221100"

        # 2. Ver ficha técnica de la clienta
        url_detalle = reverse("clientes:detalle_cliente", kwargs={"pk": cliente_obj.pk})
        res_detalle = client.get(url_detalle)
        assert res_detalle.status_code == 200
        assert "Lorena Clienta VIP" in res_detalle.content.decode("utf-8")
        assert "Cumple Hoy" in res_detalle.content.decode("utf-8")

        # 3. Iniciar tratamiento multisesión
        url_tratamiento = reverse("clientes:iniciar_tratamiento", kwargs={"cliente_pk": cliente_obj.pk})
        payload_tratamiento = {
            "titulo_tratamiento": "Transición a Rubio Platinado",
            "servicio_nombre": "Balayage",
            "total_sesiones_estimadas": 3,
            "notas_objetivo": "Decolorar progresivamente respetando puente de azufre.",
        }
        res_trat = client.post(url_tratamiento, data=payload_tratamiento)
        assert res_trat.status_code == 302

        tratamiento_obj = TratamientoProgreso.objects.get(cliente=cliente_obj)
        assert tratamiento_obj.total_sesiones_estimadas == 3

        # 4. Registrar sesión técnica de evolución
        url_evolucion = reverse("clientes:registrar_evolucion", kwargs={"tratamiento_pk": tratamiento_obj.pk})
        payload_evolucion = {
            "numero_sesion": 1,
            "diagnostico_fibra": "Base 5 natural, elasticidad óptima",
            "formula_quimica_utilizada": "Deco 30g + Ox 20 vol + Bond Protector",
            "tiempo_exposicion_minutos": 45,
            "resultado_obtenido": "Aclaración a altura 7 dorada sin daño",
            "indicaciones_hogar": "Nutrición ácida 2 veces por semana",
        }
        res_evo = client.post(url_evolucion, data=payload_evolucion)
        assert res_evo.status_code == 302

        tratamiento_obj.refresh_from_db()
        assert tratamiento_obj.sesion_actual == 1
        assert tratamiento_obj.sesiones_evolucion.count() == 1

    def test_dar_de_baja_cliente_web_preserva_tratamiento(self, client) -> None:
        """RF 4.2: la baja debe ser lógica, sin borrar el historial de tratamientos."""
        empleada = EmpleadaFactory()
        client.force_login(empleada)

        cliente_obj = Cliente.objects.create(
            nombre="Clienta a Dar de Baja",
            telefono="1155667788",
        )
        tratamiento_obj = TratamientoProgreso.objects.create(
            cliente=cliente_obj,
            titulo_tratamiento="Nutrición Capilar",
            servicio_nombre="Hidratación",
            total_sesiones_estimadas=2,
        )

        url = reverse("clientes:eliminar_cliente", kwargs={"pk": cliente_obj.pk})
        res_confirmacion = client.get(url)
        assert res_confirmacion.status_code == 200

        res_baja = client.post(url)
        assert res_baja.status_code == 302

        cliente_obj.refresh_from_db()
        assert cliente_obj.activo is False
        # El historial de tratamientos debe seguir existiendo.
        assert TratamientoProgreso.objects.filter(pk=tratamiento_obj.pk).exists()

    def test_api_delete_cliente_es_baja_logica(self, authenticated_client_administradora) -> None:
        """Un DELETE por la API de clientas no debe borrar el registro, solo desactivarlo."""
        cliente_obj = Cliente.objects.create(
            nombre="Clienta API Delete",
            telefono="1144556677",
        )
        tratamiento_obj = TratamientoProgreso.objects.create(
            cliente=cliente_obj,
            titulo_tratamiento="Tratamiento API",
            servicio_nombre="Color",
            total_sesiones_estimadas=1,
        )

        url = f"/clientes/api/{cliente_obj.pk}/"
        response = authenticated_client_administradora.delete(url)
        assert response.status_code == 204

        cliente_obj.refresh_from_db()
        assert cliente_obj.activo is False
        assert TratamientoProgreso.objects.filter(pk=tratamiento_obj.pk).exists()
