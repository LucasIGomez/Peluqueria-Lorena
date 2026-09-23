"""
Peluquería Lorena — Tests de integración de las vistas del módulo de Turnos.
"""
from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.servicios.models import Servicio, ServicioRealizado
from apps.servicios.services import ServicioService
from apps.turnos.models import Turno
from apps.turnos.services import TurnoService
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


def _proximo_dia_de_semana(objetivo_weekday, desde=None):
    """Próxima fecha futura (a partir de mañana) que caiga en el día de semana indicado."""
    dia = (desde or timezone.localdate()) + timedelta(days=1)
    while dia.weekday() != objetivo_weekday:
        dia += timedelta(days=1)
    return dia


def _proximo_dia_habil(desde=None):
    """Primer día Martes a Sábado a partir de mañana (el form rechaza Lunes y Domingo)."""
    dia = (desde or timezone.localdate()) + timedelta(days=1)
    while dia.weekday() not in {1, 2, 3, 4, 5}:
        dia += timedelta(days=1)
    return dia


@pytest.fixture
def servicio_corte(db):
    return ServicioService.crear_servicio(
        nombre="Corte Test Vistas Turnos",
        categoria=Servicio.Categoria.CORTES,
        precio_base=Decimal("25000.00"),
        duracion_estimada_minutos=45,
    )


@pytest.mark.django_db
class TestAgendaView:
    def test_agenda_requiere_login(self, client) -> None:
        response = client.get(reverse("turnos:agenda"))
        assert response.status_code == 302
        assert "/usuarios/login/" in response.url

    def test_agenda_vista_dia_muestra_turnos_del_dia(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        dia = timezone.localdate()
        TurnoService.crear_turno(cliente_nombre="Rosa Agenda", servicio=servicio_corte, fecha=dia, hora=time(10, 0))

        response = client.get(f"{reverse('turnos:agenda')}?vista=dia&fecha={dia.isoformat()}")
        assert response.status_code == 200
        assert "Rosa Agenda" in response.content.decode("utf-8")

    def test_agenda_vista_semana_muestra_turnos_agrupados(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        dia = timezone.localdate()
        TurnoService.crear_turno(cliente_nombre="Vera Semana", servicio=servicio_corte, fecha=dia, hora=time(10, 0))

        response = client.get(f"{reverse('turnos:agenda')}?vista=semana&fecha={dia.isoformat()}")
        assert response.status_code == 200
        assert "Vera Semana" in response.content.decode("utf-8")

    def test_agenda_vista_semana_distingue_turno_completado(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        dia = timezone.localdate()
        turno = TurnoService.crear_turno(
            cliente_nombre="Lucia Completa", servicio=servicio_corte, fecha=dia, hora=time(10, 0)
        )
        servicio_realizado = ServicioService.registrar_servicio_realizado(
            servicio=servicio_corte,
            cliente_nombre=turno.cliente_nombre,
            profesional=empleada,
            fecha=dia,
            hora=time(10, 0),
            precio_acordado=servicio_corte.precio_base,
            duracion_minutos=turno.duracion_minutos,
        )
        TurnoService.completar_turno(turno, servicio_realizado)

        response = client.get(f"{reverse('turnos:agenda')}?vista=semana&fecha={dia.isoformat()}")
        contenido = response.content.decode("utf-8")
        assert response.status_code == 200
        assert "Lucia Completa" in contenido
        # El turno completado no debe ofrecerse como editable, y debe distinguirse visualmente.
        assert reverse("turnos:editar_turno", kwargs={"pk": turno.pk}) not in contenido


@pytest.mark.django_db
class TestCrearTurnoView:
    def test_crear_turno_web(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        dia = _proximo_dia_habil()

        response = client.post(
            reverse("turnos:crear_turno"),
            data={
                "cliente_nombre": "Carla Nueva",
                "cliente_telefono": "1155667788",
                "servicio": servicio_corte.id,
                "fecha": dia.isoformat(),
                "hora": "14:00",
                "duracion_minutos": "45",
                "notas": "",
            },
        )
        assert response.status_code == 302
        assert Turno.objects.filter(cliente_nombre="Carla Nueva").exists()

    def test_crear_turno_fuera_de_horario_comercial_muestra_error(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        dia = _proximo_dia_habil()

        response = client.post(
            reverse("turnos:crear_turno"),
            data={
                "cliente_nombre": "Carla Madrugada",
                "servicio": servicio_corte.id,
                "fecha": dia.isoformat(),
                "hora": "03:00",
                "duracion_minutos": "45",
                "notas": "",
            },
        )
        assert response.status_code == 200  # Vuelve a mostrar el form con el error
        assert Turno.objects.filter(cliente_nombre="Carla Madrugada").exists() is False

    def test_crear_turno_en_dia_no_habilitado_muestra_error(self, client, servicio_corte) -> None:
        """El salón atiende Martes a Sábado: Lunes y Domingo deben rechazarse."""
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        domingo = _proximo_dia_de_semana(6)
        lunes = _proximo_dia_de_semana(0)

        for nombre, fecha_invalida in [("Carla Domingo", domingo), ("Carla Lunes", lunes)]:
            response = client.post(
                reverse("turnos:crear_turno"),
                data={
                    "cliente_nombre": nombre,
                    "servicio": servicio_corte.id,
                    "fecha": fecha_invalida.isoformat(),
                    "hora": "14:00",
                    "duracion_minutos": "45",
                    "notas": "",
                },
            )
            assert response.status_code == 200  # Vuelve a mostrar el form con el error
            assert Turno.objects.filter(cliente_nombre=nombre).exists() is False

    def test_crear_turno_con_solapamiento_muestra_error(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        dia = _proximo_dia_habil()
        TurnoService.crear_turno(
            cliente_nombre="Primera", servicio=servicio_corte, fecha=dia, hora=time(10, 0), profesional=empleada
        )

        response = client.post(
            reverse("turnos:crear_turno"),
            data={
                "cliente_nombre": "Segunda",
                "servicio": servicio_corte.id,
                "profesional": empleada.pk,
                "fecha": dia.isoformat(),
                "hora": "10:15",
                "duracion_minutos": "45",
            },
        )
        assert response.status_code == 200  # Vuelve a mostrar el form con el error
        assert Turno.objects.filter(cliente_nombre="Segunda").exists() is False


@pytest.mark.django_db
class TestAccionesRapidasAgenda:
    def test_cancelar_turno_confirmacion_y_post(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana Cancelar", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )

        res_confirmacion = client.get(reverse("turnos:cancelar_turno", kwargs={"pk": turno.pk}))
        assert res_confirmacion.status_code == 200

        res_post = client.post(reverse("turnos:cancelar_turno", kwargs={"pk": turno.pk}))
        assert res_post.status_code == 302
        turno.refresh_from_db()
        assert turno.estado == Turno.Estado.CANCELADO

    def test_asignar_profesional_desde_agenda(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana Asignar", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )

        response = client.post(
            reverse("turnos:asignar_profesional", kwargs={"pk": turno.pk}),
            data={"profesional": empleada.pk, "vista": "dia", "fecha": turno.fecha.isoformat()},
        )
        assert response.status_code == 302
        turno.refresh_from_db()
        assert turno.profesional == empleada
        assert turno.estado == Turno.Estado.CONFIRMADO

    def test_marcar_ausente_desde_agenda(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana Ausente", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )

        response = client.post(
            reverse("turnos:cambiar_estado", kwargs={"pk": turno.pk}),
            data={"estado": Turno.Estado.AUSENTE, "vista": "dia", "fecha": turno.fecha.isoformat()},
        )
        assert response.status_code == 302
        turno.refresh_from_db()
        assert turno.estado == Turno.Estado.AUSENTE


@pytest.mark.django_db
class TestCompletarTurnoIntegracionConServicios:
    def test_completar_turno_redirige_a_registrar_servicio_realizado(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana Completar", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )

        response = client.get(reverse("turnos:completar_turno", kwargs={"pk": turno.pk}))
        assert response.status_code == 302
        assert f"turno={turno.pk}" in response.url
        assert reverse("servicios:registrar_servicio_realizado") in response.url

    def test_registrar_atencion_desde_turno_lo_marca_completado(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        dia = timezone.localdate()
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana Vinculo",
            servicio=servicio_corte,
            fecha=dia,
            hora=time(10, 0),
            profesional=empleada,
        )

        url = reverse("servicios:registrar_servicio_realizado")
        response = client.post(
            url,
            data={
                "turno_id": turno.pk,
                "servicio": servicio_corte.id,
                "profesional": empleada.pk,
                "cliente_nombre": turno.cliente_nombre,
                "cliente_telefono": "",
                "fecha": dia.isoformat(),
                "hora": "10:00",
                "precio_acordado": "25000.00",
                "duracion_minutos": "45",
                "estado": ServicioRealizado.Estado.COMPLETADO,
                "notas": "",
            },
        )
        assert response.status_code == 302

        turno.refresh_from_db()
        assert turno.estado == Turno.Estado.COMPLETADO
        assert turno.servicio_realizado is not None
        assert turno.servicio_realizado.cliente_nombre == "Ana Vinculo"

    def test_completar_turno_cancelado_muestra_error(self, client, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        client.force_login(empleada)
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana Cancelada", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        TurnoService.cancelar_turno(turno)

        response = client.get(reverse("turnos:completar_turno", kwargs={"pk": turno.pk}))
        assert response.status_code == 302
        assert reverse("turnos:agenda") in response.url
