"""
Peluquería Lorena — Tests de integración de vistas de Caja y Ventas.

Valida el render de las pantallas y la presencia del modal de
cancelación en los formularios con datos ingresados.
"""
import pytest
from django.urls import reverse

from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.mark.django_db
class TestPagosWebViews:
    """Pruebas de integración de las vistas de caja basadas en plantillas HTML."""

    @pytest.fixture(autouse=True)
    def _login(self, db, client):
        """Las vistas web de caja exigen sesión iniciada."""
        client.force_login(EmpleadaFactory(email="caja.web@test.com"))

    def test_registrar_cobro_muestra_modal_cancelacion(self, client) -> None:
        """El formulario de cobro incluye el modal de cancelación estilo Stock e Insumos."""
        response = client.get(reverse("pagos:registrar_cobro"))

        assert response.status_code == 200
        contenido = response.content.decode("utf-8")
        assert 'id="formCobro"' in contenido
        assert 'id="btnCancelarCobro"' in contenido
        assert "modalCancelarCobro" in contenido
        assert "¿Estás seguro de Cancelar?" in contenido
        assert "Continuar editando" in contenido
        assert "Sí, cancelar" in contenido
        assert "hayCambiosSinGuardar" in contenido
        assert "_sinAvisoNavegador" in contenido

    def test_cierre_muestra_modal_cancelacion_para_observaciones(self, client) -> None:
        """El formulario de cierre incluye el modal de cancelación estilo Stock e Insumos."""
        client.force_login(AdministradoraFactory(email="caja.admin@test.com"))
        response = client.get(reverse("pagos:cierre_caja"))

        assert response.status_code == 200
        contenido = response.content.decode("utf-8")
        assert 'id="formCierre"' in contenido
        assert 'id="btnCancelarCierre"' in contenido
        assert "modalCancelarCierre" in contenido
        assert "¿Estás seguro de Cancelar?" in contenido
        assert "Continuar editando" in contenido
        assert "Sí, cancelar" in contenido
        assert "_sinAvisoNavegador" in contenido

    def test_cierre_restringido_a_administradora(self, client) -> None:
        """Una empleada no puede ver la pantalla de cierre."""
        response = client.get(reverse("pagos:cierre_caja"))

        assert response.status_code == 302
