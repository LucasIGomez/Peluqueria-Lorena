"""
Pruebas del recordatorio automático de turno (RF 12.4).
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import NotificacionService
from apps.servicios.models import Servicio
from apps.servicios.services import ServicioService
from apps.turnos.models import Turno

POST = "apps.bot_asistente.handlers.whatsapp_client.requests.post"


@pytest.fixture
def servicio():
    return ServicioService.crear_servicio(
        nombre="Corte Recordatorio",
        categoria=Servicio.Categoria.CORTES,
        precio_base=Decimal("25000.00"),
        duracion_estimada_minutos=45,
    )


def _turno(servicio, ahora, minutos, **extra):
    inicio = timezone.localtime(ahora + timedelta(minutes=minutos))
    datos = dict(
        cliente_nombre="Marina Perez",
        cliente_telefono="+54 9 297 123-4567",
        servicio=servicio,
        fecha=inicio.date(),
        hora=inicio.time().replace(second=0, microsecond=0),
        estado=Turno.Estado.CONFIRMADO,
    )
    datos.update(extra)
    return Turno.objects.create(**datos)


def _respuesta(codigo=200):
    r = MagicMock()
    r.status_code = codigo
    r.text = ""
    return r


@pytest.mark.django_db
class TestRecordatorioDeTurno:
    def test_envia_recordatorio_del_turno_que_empieza_en_una_hora(self, servicio) -> None:
        ahora = timezone.now()
        turno = _turno(servicio, ahora, 45)
        with patch(POST, return_value=_respuesta()) as post:
            resumen = NotificacionService.enviar_recordatorios_turnos(ahora=ahora)
        assert resumen == {"enviadas": 1, "fallidas": 0, "omitidas": 0}
        assert post.call_count == 1
        payload = post.call_args.kwargs["json"]
        assert payload["to"] == "5492971234567"
        assert "Marina" in payload["text"]["body"]
        assert turno.hora.strftime("%H:%M") in payload["text"]["body"]
        n = Notificacion.objects.get(turno=turno)
        assert n.estado_envio == Notificacion.EstadoEnvio.ENVIADA
        assert n.fecha_envio is not None

    def test_no_envia_fuera_de_la_ventana_ni_a_turnos_cancelados_o_pasados(self, servicio) -> None:
        ahora = timezone.now()
        _turno(servicio, ahora, 180)  # falta mucho
        _turno(servicio, ahora, -30)  # ya empezó
        _turno(servicio, ahora, 30, estado=Turno.Estado.CANCELADO)
        _turno(servicio, ahora, 30, estado=Turno.Estado.COMPLETADO)
        with patch(POST, return_value=_respuesta()) as post:
            resumen = NotificacionService.enviar_recordatorios_turnos(ahora=ahora)
        assert resumen == {"enviadas": 0, "fallidas": 0, "omitidas": 0}
        post.assert_not_called()
        assert Notificacion.objects.count() == 0

    def test_es_idempotente_un_turno_recibe_un_solo_recordatorio(self, servicio) -> None:
        ahora = timezone.now()
        _turno(servicio, ahora, 30)
        with patch(POST, return_value=_respuesta()) as post:
            NotificacionService.enviar_recordatorios_turnos(ahora=ahora)
            resumen = NotificacionService.enviar_recordatorios_turnos(ahora=ahora + timedelta(minutes=10))
        assert resumen == {"enviadas": 0, "fallidas": 0, "omitidas": 1}
        assert post.call_count == 1
        assert Notificacion.objects.count() == 1

    def test_si_meta_falla_queda_fallida_y_se_reintenta(self, servicio) -> None:
        ahora = timezone.now()
        turno = _turno(servicio, ahora, 30)
        with patch(POST, return_value=_respuesta(500)):
            resumen = NotificacionService.enviar_recordatorios_turnos(ahora=ahora)
        assert resumen["fallidas"] == 1
        assert Notificacion.objects.get(turno=turno).estado_envio == Notificacion.EstadoEnvio.FALLIDA

        with patch(POST, return_value=_respuesta()):
            resumen = NotificacionService.enviar_recordatorios_turnos(ahora=ahora + timedelta(minutes=10))
        assert resumen["enviadas"] == 1
        assert Notificacion.objects.get(turno=turno).estado_envio == Notificacion.EstadoEnvio.ENVIADA

    def test_sin_telefono_queda_fallida_sin_llamar_a_meta(self, servicio) -> None:
        ahora = timezone.now()
        turno = _turno(servicio, ahora, 30, cliente_telefono="")
        with patch(POST) as post:
            resumen = NotificacionService.enviar_recordatorios_turnos(ahora=ahora)
        assert resumen["fallidas"] == 1
        post.assert_not_called()
        n = Notificacion.objects.get(turno=turno)
        assert "teléfono" in n.detalle_error

    def test_comando_enviar_recordatorios(self, servicio, capsys) -> None:
        ahora = timezone.now()
        _turno(servicio, ahora, 20)
        with patch(POST, return_value=_respuesta()):
            call_command("enviar_recordatorios")
        assert "1 enviados" in capsys.readouterr().out
