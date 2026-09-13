"""
Peluquería Lorena — Tests de integración de vistas de Caja y Ventas.

Valida el render de las pantallas y la presencia del modal de
cancelación en los formularios con datos ingresados.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.pagos.models import CierreCaja, Cobro
from apps.pagos.services import CajaService
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
        assert 'name="porcentaje_descuento"' in contenido
        assert 'id="id_descuento"' in contenido
        assert 'placeholder="Ej: 10"' in contenido
        assert "actualizarEstadoDescuento" in contenido
        assert "no admite descuento" in contenido

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

    def test_reporte_restringido_a_administradora(self, client) -> None:
        """Una empleada no puede ver el reporte de ingresos por medio de pago."""
        response = client.get(reverse("pagos:reporte_medios"))

        assert response.status_code == 302

    def test_reporte_accesible_para_administradora(self, client) -> None:
        """La administradora sí puede ver el reporte de ingresos."""
        client.force_login(AdministradoraFactory(email="caja.admin.reporte@test.com"))
        response = client.get(reverse("pagos:reporte_medios"))

        assert response.status_code == 200

    def test_reabrir_restringido_a_administradora(self, client) -> None:
        """Una empleada no puede reabrir una caja cerrada."""
        response = client.get(reverse("pagos:reabrir_caja"))

        assert response.status_code == 302

    def test_reabrir_caja_elimina_el_cierre(self, client) -> None:
        """La administradora puede reabrir una caja ya cerrada."""
        admin = AdministradoraFactory(email="caja.admin.reabrir@test.com")
        client.force_login(admin)
        hoy = date.today()
        CierreCaja.objects.create(
            fecha=hoy,
            responsable=admin,
            cantidad_cobros=0,
            total_general=0,
        )

        response = client.post(reverse("pagos:reabrir_caja"), data={"fecha": hoy.isoformat()})

        assert response.status_code == 302
        assert not CierreCaja.objects.filter(fecha=hoy).exists()

    def test_cierre_muestra_modal_cierre_definitivo(self, client) -> None:
        """La pantalla de cierre confirma con modal propio en vez del diálogo nativo."""
        client.force_login(AdministradoraFactory(email="caja.admin.cierre@test.com"))
        response = client.get(reverse("pagos:cierre_caja"))

        assert response.status_code == 200
        contenido = response.content.decode("utf-8")
        assert "modalConfirmarCierre" in contenido
        assert "¿Cerrar la caja definitivamente?" in contenido
        assert "btnConfirmarCierreDefinitivo" in contenido

    def test_caja_cerrada_muestra_modal_reapertura(self, client) -> None:
        """Con caja cerrada, /pagos/ ofrece reabrir con modal propio."""
        admin = AdministradoraFactory(email="caja.admin.reapertura@test.com")
        client.force_login(admin)
        hoy = date.today()
        CierreCaja.objects.create(
            fecha=hoy,
            responsable=admin,
            cantidad_cobros=0,
            total_general=0,
        )

        response = client.get(reverse("pagos:caja_diaria"))

        assert response.status_code == 200
        contenido = response.content.decode("utf-8")
        assert "modalReabrirCaja" in contenido
        assert "¿Reabrir la caja?" in contenido
        assert "btnConfirmarReabrirCaja" in contenido

    def test_registrar_cobro_con_descuento_manual(self, client) -> None:
        """POST con 20% en efectivo registra el cobro con ese descuento."""
        empleada = EmpleadaFactory(email="caja.descuento@test.com")
        client.force_login(empleada)
        dia = timezone.localdate()
        response = client.post(
            reverse("pagos:registrar_cobro"),
            data={
                "tipo": Cobro.Tipo.SERVICIO,
                "medio_pago": Cobro.MedioPago.EFECTIVO,
                "porcentaje_descuento": "20",
                "fecha": dia.isoformat(),
                "cliente_nombre": "Olga Descuento",
                "profesional": str(empleada.pk),
                "cantidad": "1",
                "precio_unitario": "20000.00",
            },
        )

        assert response.status_code == 302
        cobro = Cobro.objects.get(cliente_nombre="Olga Descuento")
        assert cobro.porcentaje_descuento == Decimal("20.00")
        assert cobro.monto_descuento == Decimal("4000.00")
        assert cobro.total == Decimal("16000.00")

    def test_registrar_cobro_con_descuento_cero(self, client) -> None:
        """POST con 0% en efectivo registra el cobro sin descuento."""
        empleada = EmpleadaFactory(email="caja.sindescuento@test.com")
        client.force_login(empleada)
        dia = timezone.localdate()
        response = client.post(
            reverse("pagos:registrar_cobro"),
            data={
                "tipo": Cobro.Tipo.SERVICIO,
                "medio_pago": Cobro.MedioPago.MERCADO_PAGO,
                "porcentaje_descuento": "0",
                "fecha": dia.isoformat(),
                "cliente_nombre": "Rosa Cero",
                "profesional": str(empleada.pk),
                "cantidad": "1",
                "precio_unitario": "15000.00",
            },
        )

        assert response.status_code == 302
        cobro = Cobro.objects.get(cliente_nombre="Rosa Cero")
        assert cobro.porcentaje_descuento == Decimal("0.00")
        assert cobro.monto_descuento == Decimal("0.00")
        assert cobro.total == Decimal("15000.00")

    def test_registrar_cobro_tarjeta_con_descuento_es_rechazado(self, client) -> None:
        """POST con descuento en tarjeta de crédito es rechazado por el formulario."""
        empleada = EmpleadaFactory(email="caja.tarjeta@test.com")
        client.force_login(empleada)
        dia = timezone.localdate()
        response = client.post(
            reverse("pagos:registrar_cobro"),
            data={
                "tipo": Cobro.Tipo.SERVICIO,
                "medio_pago": Cobro.MedioPago.TARJETA_CREDITO,
                "porcentaje_descuento": "10",
                "fecha": dia.isoformat(),
                "cliente_nombre": "Teresa Tarjeta",
                "profesional": str(empleada.pk),
                "cantidad": "1",
                "precio_unitario": "20000.00",
            },
        )

        assert response.status_code == 200
        assert "no admite descuento" in response.content.decode("utf-8")
        assert not Cobro.objects.filter(cliente_nombre="Teresa Tarjeta").exists()

    def test_caja_diaria_muestra_fecha_formateada(self, client) -> None:
        """Los encabezados de /pagos/ muestran la fecha sin código de plantilla crudo."""
        response = client.get(reverse("pagos:caja_diaria"))

        assert response.status_code == 200
        contenido = response.content.decode("utf-8")
        assert "{{" not in contenido
        assert f"Ingresos por Medio de Pago — {timezone.localdate().strftime('%d/%m/%Y')}" in contenido
        assert "Cobros del" in contenido

    def test_caja_diaria_muestra_descuento_variable_por_medio(self, client) -> None:
        """La tabla por medio de pago muestra el descuento real otorgado, no un fijo."""
        empleada = EmpleadaFactory(email="caja.var@test.com")
        CajaService.registrar_cobro(
            tipo=Cobro.Tipo.SERVICIO,
            medio_pago=Cobro.MedioPago.EFECTIVO,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("20000.00"),
            porcentaje_descuento=Decimal("20.00"),
            profesional=empleada,
            cliente_nombre="Vera Variable",
        )

        response = client.get(reverse("pagos:caja_diaria"))

        assert response.status_code == 200
        contenido = response.content.decode("utf-8")
        assert "-$4000,00" in contenido
        assert "-10% auto" not in contenido
        assert "(10%)" not in contenido
        assert "(20%)" in contenido
