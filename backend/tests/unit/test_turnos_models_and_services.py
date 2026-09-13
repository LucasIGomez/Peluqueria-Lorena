"""
Pruebas unitarias para el modelo Turno y TurnoService.
"""
from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.servicios.services import ServicioService
from apps.servicios.models import Servicio
from apps.turnos.models import Turno
from apps.turnos.services import SolapamientoError, TurnoInvalidoError, TurnoService
from tests.factories.usuario_factory import EmpleadaFactory


@pytest.fixture
def servicio_corte():
    return ServicioService.crear_servicio(
        nombre="Corte Test Turnos",
        categoria=Servicio.Categoria.CORTES,
        precio_base=Decimal("25000.00"),
        duracion_estimada_minutos=45,
    )


@pytest.mark.django_db
class TestTurnoModelo:
    def test_hora_fin_calculada_segun_duracion(self, servicio_corte) -> None:
        turno = Turno.objects.create(
            cliente_nombre="Marina Test",
            servicio=servicio_corte,
            fecha=timezone.localdate(),
            hora=time(10, 0),
            duracion_minutos=45,
        )
        assert turno.hora_fin == time(10, 45)

    def test_esta_activo_es_false_si_cancelado(self, servicio_corte) -> None:
        turno = Turno.objects.create(
            cliente_nombre="Marina Test",
            servicio=servicio_corte,
            fecha=timezone.localdate(),
            hora=time(10, 0),
            estado=Turno.Estado.CANCELADO,
        )
        assert turno.esta_activo is False


@pytest.mark.django_db
class TestTurnoServiceAltaYSolapamiento:
    def test_crear_turno_sin_profesional_no_valida_solapamiento(self, servicio_corte) -> None:
        t1 = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        t2 = TurnoService.crear_turno(
            cliente_nombre="Beatriz", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        assert t1.pk != t2.pk

    def test_crear_turno_con_solapamiento_de_la_misma_peluquera_falla(self, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        dia = timezone.localdate()
        TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=dia, hora=time(10, 0), profesional=empleada
        )
        with pytest.raises(SolapamientoError):
            TurnoService.crear_turno(
                cliente_nombre="Beatriz", servicio=servicio_corte, fecha=dia, hora=time(10, 20), profesional=empleada
            )

    def test_crear_turno_sin_solapamiento_si_no_se_superponen_horarios(self, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        dia = timezone.localdate()
        TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=dia, hora=time(10, 0), profesional=empleada
        )
        # El primer turno dura 45 min (10:00 a 10:45); este empieza a las 10:45, no se superpone.
        turno2 = TurnoService.crear_turno(
            cliente_nombre="Beatriz", servicio=servicio_corte, fecha=dia, hora=time(10, 45), profesional=empleada
        )
        assert turno2.pk is not None

    def test_crear_turno_toma_duracion_del_servicio_si_no_se_indica(self, servicio_corte) -> None:
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        assert turno.duracion_minutos == 45

    def test_crear_turno_sin_nombre_falla(self, servicio_corte) -> None:
        with pytest.raises(TurnoInvalidoError):
            TurnoService.crear_turno(
                cliente_nombre="   ", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
            )

    def test_turno_cancelado_no_bloquea_el_horario(self, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        dia = timezone.localdate()
        t1 = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=dia, hora=time(10, 0), profesional=empleada
        )
        TurnoService.cancelar_turno(t1)
        # Ahora otro turno en el mismo horario con la misma peluquera debe poder crearse.
        turno2 = TurnoService.crear_turno(
            cliente_nombre="Beatriz", servicio=servicio_corte, fecha=dia, hora=time(10, 0), profesional=empleada
        )
        assert turno2.pk is not None


@pytest.mark.django_db
class TestTurnoServiceEdicionYEstados:
    def test_asignar_profesional_confirma_turno_pendiente(self, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        assert turno.estado == Turno.Estado.PENDIENTE

        TurnoService.asignar_profesional(turno, empleada)
        turno.refresh_from_db()
        assert turno.profesional == empleada
        assert turno.estado == Turno.Estado.CONFIRMADO

    def test_asignar_profesional_con_solapamiento_falla(self, servicio_corte) -> None:
        empleada = EmpleadaFactory()
        dia = timezone.localdate()
        TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=dia, hora=time(10, 0), profesional=empleada
        )
        turno2 = TurnoService.crear_turno(
            cliente_nombre="Beatriz", servicio=servicio_corte, fecha=dia, hora=time(10, 15)
        )
        with pytest.raises(SolapamientoError):
            TurnoService.asignar_profesional(turno2, empleada)

    def test_cambiar_estado_a_ausente(self, servicio_corte) -> None:
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        TurnoService.cambiar_estado(turno, Turno.Estado.AUSENTE)
        turno.refresh_from_db()
        assert turno.estado == Turno.Estado.AUSENTE

    def test_cambiar_estado_no_permite_completar_directamente(self, servicio_corte) -> None:
        turno = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        with pytest.raises(TurnoInvalidoError):
            TurnoService.cambiar_estado(turno, Turno.Estado.COMPLETADO)

    def test_cambiar_estado_de_turno_completado_falla(self, servicio_corte) -> None:
        from apps.servicios.services import ServicioService as SS

        turno = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        atencion = SS.registrar_servicio_realizado(
            servicio=servicio_corte, profesional=EmpleadaFactory(), cliente_nombre="Ana"
        )
        TurnoService.completar_turno(turno, atencion)
        with pytest.raises(TurnoInvalidoError):
            TurnoService.cambiar_estado(turno, Turno.Estado.AUSENTE)

    def test_cancelar_turno_completado_falla(self, servicio_corte) -> None:
        from apps.servicios.services import ServicioService as SS

        turno = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        atencion = SS.registrar_servicio_realizado(
            servicio=servicio_corte, profesional=EmpleadaFactory(), cliente_nombre="Ana"
        )
        TurnoService.completar_turno(turno, atencion)
        with pytest.raises(TurnoInvalidoError):
            TurnoService.cancelar_turno(turno)

    def test_completar_turno_vincula_atencion_y_cambia_estado(self, servicio_corte) -> None:
        from apps.servicios.services import ServicioService as SS

        turno = TurnoService.crear_turno(
            cliente_nombre="Ana", servicio=servicio_corte, fecha=timezone.localdate(), hora=time(10, 0)
        )
        atencion = SS.registrar_servicio_realizado(
            servicio=servicio_corte, profesional=EmpleadaFactory(), cliente_nombre="Ana"
        )
        TurnoService.completar_turno(turno, atencion)
        turno.refresh_from_db()
        assert turno.estado == Turno.Estado.COMPLETADO
        assert turno.servicio_realizado_id == atencion.pk


@pytest.mark.django_db
class TestTurnoServiceConsultas:
    def test_listar_turnos_dia_incluye_cancelados(self, servicio_corte) -> None:
        dia = timezone.localdate()
        t1 = TurnoService.crear_turno(cliente_nombre="Ana", servicio=servicio_corte, fecha=dia, hora=time(9, 0))
        t2 = TurnoService.crear_turno(cliente_nombre="Beatriz", servicio=servicio_corte, fecha=dia, hora=time(11, 0))
        TurnoService.cancelar_turno(t2)

        turnos = TurnoService.listar_turnos_dia(dia)
        assert t1 in turnos
        assert t2 in turnos

    def test_listar_turnos_rango_filtra_por_fechas(self, servicio_corte) -> None:
        hoy = timezone.localdate()
        TurnoService.crear_turno(cliente_nombre="Ana", servicio=servicio_corte, fecha=hoy, hora=time(9, 0))
        TurnoService.crear_turno(
            cliente_nombre="Beatriz", servicio=servicio_corte, fecha=hoy + timedelta(days=10), hora=time(9, 0)
        )
        turnos = TurnoService.listar_turnos_rango(hoy, hoy + timedelta(days=6))
        assert turnos.count() == 1
