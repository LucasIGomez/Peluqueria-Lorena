"""
Pruebas unitarias para los modelos y servicios del módulo de Clientes.
"""
from datetime import date, timedelta
import pytest
from django.utils import timezone

from apps.clientes.forms import ClienteForm
from apps.clientes.models import Cliente, EvolucionSesion, TratamientoProgreso
from apps.clientes.services import ClienteService
from tests.factories.usuario_factory import EmpleadaFactory


@pytest.mark.django_db
class TestClienteDomainAndService:
    """Pruebas para el modelo Cliente y ClienteService."""

    def test_creacion_cliente_y_properties_camelcase(self) -> None:
        hoy = timezone.localdate()
        cliente = ClienteService.crear_cliente(
            nombre="Valeria Morales",
            telefono="1123456789",
            email="valeria@test.com",
            fecha_nacimiento=hoy,
            notas_alergias="Sensibilidad al peróxido de 30 vol",
            preferencias="Café cortado, prefiere corte en seco",
        )

        assert cliente.nombre == "Valeria Morales"
        assert cliente.es_cumpleanos_hoy is True
        assert cliente.esCumpleanosHoy is True
        assert cliente.dias_para_cumpleanos == 0
        assert cliente.diasParaCumpleanos == 0
        assert "wa.me" in cliente.link_whatsapp
        assert cliente.linkWhatsapp == cliente.link_whatsapp

    def test_dias_para_cumpleanos_calculo(self) -> None:
        hoy = timezone.localdate()
        cumple_proximo = hoy + timedelta(days=5)
        cliente = ClienteService.crear_cliente(
            nombre="Camila Ríos",
            telefono="1198765432",
            fecha_nacimiento=cumple_proximo,
        )

        assert cliente.es_cumpleanos_hoy is False
        assert cliente.dias_para_cumpleanos == 5
        assert cliente.diasParaCumpleanos == 5

    def test_listar_clientes_con_busqueda(self) -> None:
        c1 = ClienteService.crear_cliente(nombre="Lucía Gómez", telefono="11111111")
        c2 = ClienteService.crear_cliente(nombre="Sofía Fernández", telefono="22222222")

        resultados = ClienteService.listar_clientes(busqueda="Lucía")
        assert c1 in resultados
        assert c2 not in resultados

        resultados_tel = ClienteService.listar_clientes(busqueda="22222222")
        assert c2 in resultados_tel
        assert c1 not in resultados_tel

    def test_obtener_cumpleaneras_proximos_dias(self) -> None:
        hoy = timezone.localdate()
        c_hoy = ClienteService.crear_cliente(nombre="Ana Hoy", telefono="123", fecha_nacimiento=hoy)
        c_pronto = ClienteService.crear_cliente(nombre="Beatriz Pronto", telefono="456", fecha_nacimiento=hoy + timedelta(days=3))
        c_lejos = ClienteService.crear_cliente(nombre="Carla Lejos", telefono="789", fecha_nacimiento=hoy + timedelta(days=30))

        cumpleaneras = ClienteService.obtener_cumpleaneras_proximos_dias(dias=7)
        assert c_hoy in cumpleaneras
        assert c_pronto in cumpleaneras
        assert c_lejos not in cumpleaneras


@pytest.mark.django_db
class TestTratamientoProgresoYMultisesion:
    """Pruebas para tratamientos capilares multisesión y sesiones de evolución."""

    def test_iniciar_tratamiento_y_avance_porcentual(self) -> None:
        cliente = ClienteService.crear_cliente(nombre="Paula Balayage", telefono="11223344")
        tratamiento = ClienteService.iniciar_tratamiento_progreso(
            cliente=cliente,
            titulo_tratamiento="Aclaración progresiva en 3 etapas",
            servicio_nombre="Balayage",
            total_sesiones_estimadas=3,
            notas_objetivo="Llegar a rubio manteca sin sobreprocesar fibra",
        )

        assert tratamiento.sesion_actual == 1
        assert tratamiento.total_sesiones_estimadas == 3
        assert tratamiento.porcentaje_progreso == 33
        assert tratamiento.porcentajeProgreso == 33
        assert tratamiento.estado == TratamientoProgreso.Estado.EN_PROGRESO

    def test_registrar_evolucion_sesion_actualiza_estado(self) -> None:
        profesional = EmpleadaFactory()
        cliente = ClienteService.crear_cliente(nombre="Mariana Alisado", telefono="55667788")
        tratamiento = ClienteService.iniciar_tratamiento_progreso(
            cliente=cliente,
            titulo_tratamiento="Alisado progresivo en 2 sesiones",
            servicio_nombre="Alisado",
            total_sesiones_estimadas=2,
        )

        # Registrar sesión 1
        s1 = ClienteService.registrar_evolucion_sesion(
            tratamiento=tratamiento,
            numero_sesion=1,
            diagnostico_fibra="Cabello rizado con porosidad media",
            formula_quimica_utilizada="Activo orgánico ácido 60ml",
            tiempo_exposicion_minutos=40,
            resultado_obtenido="Reducción de frizz en un 70%",
            profesional=profesional,
        )

        tratamiento.refresh_from_db()
        assert tratamiento.sesion_actual == 1
        assert s1.tiempoExposicionMinutos == 40
        assert s1.formulaQuimicaUtilizada == "Activo orgánico ácido 60ml"

        # Registrar sesión 2 (final)
        s2 = ClienteService.registrar_evolucion_sesion(
            tratamiento=tratamiento,
            numero_sesion=2,
            diagnostico_fibra="Fibra alineada y sellada",
            formula_quimica_utilizada="Sellador térmico y mascarilla ácida",
            resultado_obtenido="Liso espejo completado",
            profesional=profesional,
        )

        tratamiento.refresh_from_db()
        assert tratamiento.sesion_actual == 2
        assert tratamiento.porcentaje_progreso == 100
        assert tratamiento.estado == TratamientoProgreso.Estado.FINALIZADO
        assert tratamiento.fecha_finalizacion is not None


@pytest.mark.django_db
class TestClienteFormValidacionTelefono:
    """RF 4.1: el teléfono no puede ser un solo dígito ni cualquier valor arbitrario."""

    def _datos_base(self, telefono: str) -> dict:
        return {
            "nombre": "Clienta de Prueba",
            "telefono": telefono,
            "email": "",
            "fecha_nacimiento": "",
            "notas_alergias": "",
            "preferencias": "",
        }

    @pytest.mark.parametrize(
        "telefono",
        ["5", "123", "abcdefgh", "11111111111", "", "12-34"],
    )
    def test_telefono_invalido_rechazado(self, telefono: str) -> None:
        form = ClienteForm(data=self._datos_base(telefono))
        assert not form.is_valid()
        assert "telefono" in form.errors

    @pytest.mark.parametrize(
        "telefono",
        ["1123456789", "11 2345-6789", "+54 9 11 2345 6789"],
    )
    def test_telefono_valido_aceptado(self, telefono: str) -> None:
        form = ClienteForm(data=self._datos_base(telefono))
        assert form.is_valid(), form.errors
