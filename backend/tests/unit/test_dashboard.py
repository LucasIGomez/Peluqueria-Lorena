"""
Peluquería Lorena — Tests automatizados del Dashboard (RF 2).

Valida la lógica de negocio y las vistas para:
- RF 2.1: Turnos del día
- RF 2.2: Resumen de ingresos acumulados (día, semana y mes)
- RF 2.3: Alertas de stock crítico y reposición
- RF 2.4: Próximos turnos agendados
- RF 2.5: Cumpleaños del mes en curso
"""
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.inventario.models import Producto
from apps.pagos.models import Cobro
from apps.servicios.models import Servicio
from apps.turnos.models import Turno
from config.dashboard_service import DashboardService
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.fixture
def servicio_prueba(db):
    return Servicio.objects.create(
        nombre="Corte de Pelo Test",
        precio_base=Decimal("15000.00"),
        duracion_estimada_minutos=45,
    )


@pytest.fixture
def profesional(db):
    return EmpleadaFactory(email="peluquera_test@lorena.com", nombre="Lucía Peluquera")


@pytest.fixture
def administradora(db):
    return AdministradoraFactory(email="admin_test@lorena.com", nombre="Lorena Dueña")


@pytest.mark.django_db
class TestDashboardService:
    def test_rf2_1_turnos_del_dia(self, servicio_prueba, profesional):
        """RF 2.1: Retorna correctamente los turnos agendados para el día de hoy."""
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)
        manana = hoy + timedelta(days=1)

        t_hoy_1 = Turno.objects.create(
            cliente_nombre="Valeria Hoy 1",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=hoy,
            hora=time(10, 0),
            estado=Turno.Estado.PENDIENTE,
        )
        t_hoy_2 = Turno.objects.create(
            cliente_nombre="Marta Hoy 2",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=hoy,
            hora=time(12, 0),
            estado=Turno.Estado.COMPLETADO,
        )
        t_hoy_cancelado = Turno.objects.create(
            cliente_nombre="Silvia Cancelada",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=hoy,
            hora=time(14, 0),
            estado=Turno.Estado.CANCELADO,
        )
        # Turnos en otras fechas (no deben aparecer en turnos_hoy)
        Turno.objects.create(
            cliente_nombre="Carla Ayer",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=ayer,
            hora=time(11, 0),
        )
        Turno.objects.create(
            cliente_nombre="Luciana Mañana",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=manana,
            hora=time(11, 0),
        )

        metricas = DashboardService.obtener_metricas(hoy=hoy)

        assert metricas["turnos_hoy_total"] == 3
        assert metricas["turnos_hoy_activos_count"] == 2
        assert metricas["turnos_hoy_completados_count"] == 1
        assert metricas["turnos_hoy_pendientes_count"] == 1
        nombres_hoy = [t.cliente_nombre for t in metricas["turnos_hoy"]]
        assert "Valeria Hoy 1" in nombres_hoy
        assert "Marta Hoy 2" in nombres_hoy
        assert "Silvia Cancelada" in nombres_hoy
        assert "Carla Ayer" not in nombres_hoy
        assert "Luciana Mañana" not in nombres_hoy

    def test_rf2_2_resumen_ingresos(self, profesional):
        """RF 2.2: Calcula correctamente los ingresos acumulados de hoy, la semana y el mes."""
        # Fijamos una fecha de referencia: por ejemplo, un Miércoles a mitad de mes
        # 2026-10-14 es Miércoles
        hoy = date(2026, 10, 14)
        inicio_semana = date(2026, 10, 12)  # Lunes 12 de Octubre
        ayer = date(2026, 10, 13)  # Martes 13 de Octubre (misma semana y mes)
        semana_anterior = date(2026, 10, 5)  # Mismo mes, pero semana anterior
        mes_anterior = date(2026, 9, 30)  # Mes anterior

        # 1. Cobro hoy ($10.000)
        Cobro.objects.create(
            cliente_nombre="Clienta Hoy",
            profesional=profesional,
            tipo=Cobro.Tipo.SERVICIO,
            precio_unitario=Decimal("10000.00"),
            subtotal=Decimal("10000.00"),
            total=Decimal("10000.00"),
            fecha=hoy,
        )
        # 2. Cobro ayer ($5.000) - misma semana y mes
        Cobro.objects.create(
            cliente_nombre="Clienta Ayer",
            profesional=profesional,
            tipo=Cobro.Tipo.SERVICIO,
            precio_unitario=Decimal("5000.00"),
            subtotal=Decimal("5000.00"),
            total=Decimal("5000.00"),
            fecha=ayer,
        )
        # 3. Cobro semana anterior ($8.000) - mismo mes, distinta semana
        Cobro.objects.create(
            cliente_nombre="Clienta Semana Pasada",
            profesional=profesional,
            tipo=Cobro.Tipo.SERVICIO,
            precio_unitario=Decimal("8000.00"),
            subtotal=Decimal("8000.00"),
            total=Decimal("8000.00"),
            fecha=semana_anterior,
        )
        # 4. Cobro mes anterior ($20.000) - mes diferente
        Cobro.objects.create(
            cliente_nombre="Clienta Mes Pasado",
            profesional=profesional,
            tipo=Cobro.Tipo.SERVICIO,
            precio_unitario=Decimal("20000.00"),
            subtotal=Decimal("20000.00"),
            total=Decimal("20000.00"),
            fecha=mes_anterior,
        )
        # 5. Cobro anulado hoy ($50.000) - NO debe sumarse
        Cobro.objects.create(
            cliente_nombre="Cobro Anulado",
            profesional=profesional,
            tipo=Cobro.Tipo.SERVICIO,
            precio_unitario=Decimal("50000.00"),
            subtotal=Decimal("50000.00"),
            total=Decimal("50000.00"),
            fecha=hoy,
            anulado=True,
        )

        metricas = DashboardService.obtener_metricas(hoy=hoy)

        # Hoy = $10.000
        assert metricas["ingresos_dia"] == Decimal("10000.00")
        assert metricas["cobros_count_dia"] == 1
        # Semana = Hoy ($10.000) + Ayer ($5.000) = $15.000
        assert metricas["ingresos_semana"] == Decimal("15000.00")
        # Mes = Hoy ($10.000) + Ayer ($5.000) + Semana Pasada ($8.000) = $23.000
        assert metricas["ingresos_mes"] == Decimal("23000.00")

    def test_rf2_3_alertas_stock(self):
        """RF 2.3: Filtra productos cuyo stock se encuentra por debajo del mínimo."""
        # Producto en nivel crítico (stock_actual <= stock_minimo)
        prod_critico = Producto.objects.create(
            nombre="Shampoo Ácido Crítico",
            precio=Decimal("4500.00"),
            stock_actual=2,
            stock_minimo=5,
            activo=True,
        )
        # Producto agotado (stock_actual = 0)
        prod_agotado = Producto.objects.create(
            nombre="Decolorante Polvo Agotado",
            precio=Decimal("8000.00"),
            stock_actual=0,
            stock_minimo=3,
            activo=True,
        )
        # Producto con stock saludable (stock_actual > stock_minimo)
        Producto.objects.create(
            nombre="Acondicionador Saludable",
            precio=Decimal("4000.00"),
            stock_actual=10,
            stock_minimo=4,
            activo=True,
        )
        # Producto inactivo (no debe figurar)
        Producto.objects.create(
            nombre="Crema Inactiva",
            precio=Decimal("2000.00"),
            stock_actual=1,
            stock_minimo=5,
            activo=False,
        )

        metricas = DashboardService.obtener_metricas()

        nombres_bajo_stock = [p.nombre for p in metricas["productos_bajo_stock"]]
        assert "Shampoo Ácido Crítico" in nombres_bajo_stock
        assert "Decolorante Polvo Agotado" in nombres_bajo_stock
        assert "Acondicionador Saludable" not in nombres_bajo_stock
        assert "Crema Inactiva" not in nombres_bajo_stock
        assert metricas["total_alertas_stock"] == 2
        assert metricas["sin_stock_count"] == 1

    def test_rf2_4_proximos_turnos(self, servicio_prueba, profesional):
        """RF 2.4: Lista turnos futuros más allá del día en curso, excluyendo cancelados."""
        hoy = timezone.localdate()
        manana = hoy + timedelta(days=1)
        pasado_manana = hoy + timedelta(days=2)

        # Turno hoy (no debe estar en próximos turnos)
        Turno.objects.create(
            cliente_nombre="Turno Hoy",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=hoy,
            hora=time(16, 0),
        )
        # Turno mañana (debe estar)
        Turno.objects.create(
            cliente_nombre="Turno Mañana",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=manana,
            hora=time(10, 0),
        )
        # Turno pasado mañana cancelado (no debe estar)
        Turno.objects.create(
            cliente_nombre="Turno Futuro Cancelado",
            servicio=servicio_prueba,
            profesional=profesional,
            fecha=pasado_manana,
            hora=time(11, 0),
            estado=Turno.Estado.CANCELADO,
        )

        metricas = DashboardService.obtener_metricas(hoy=hoy)

        nombres_proximos = [t.cliente_nombre for t in metricas["proximos_turnos"]]
        assert "Turno Mañana" in nombres_proximos
        assert "Turno Hoy" not in nombres_proximos
        assert "Turno Futuro Cancelado" not in nombres_proximos
        assert metricas["proximos_turnos_total"] == 1

    def test_rf2_5_cumpleanos_del_mes(self):
        """RF 2.5: Lista clientas que cumplen años en el mes en curso y detecta si es hoy."""
        hoy = date(2026, 10, 15)

        # Clienta cumple hoy
        c_hoy = Cliente.objects.create(
            nombre="Ana Cumple Hoy",
            telefono="2975001111",
            fecha_nacimiento=date(1995, 10, 15),
            activo=True,
        )
        # Clienta cumple este mes pero otro día
        c_mes = Cliente.objects.create(
            nombre="Beatriz Cumple Octubre",
            telefono="2975002222",
            fecha_nacimiento=date(1990, 10, 28),
            activo=True,
        )
        # Clienta cumple en Noviembre (otro mes)
        Cliente.objects.create(
            nombre="Clara Cumple Noviembre",
            telefono="2975003333",
            fecha_nacimiento=date(1992, 11, 10),
            activo=True,
        )
        # Clienta inactiva
        Cliente.objects.create(
            nombre="Diana Inactiva",
            telefono="2975004444",
            fecha_nacimiento=date(1998, 10, 15),
            activo=False,
        )

        metricas = DashboardService.obtener_metricas(hoy=hoy)

        nombres_mes = [c.nombre for c in metricas["cumpleaneras_mes"]]
        assert "Ana Cumple Hoy" in nombres_mes
        assert "Beatriz Cumple Octubre" in nombres_mes
        assert "Clara Cumple Noviembre" not in nombres_mes
        assert "Diana Inactiva" not in nombres_mes

        nombres_hoy = [c.nombre for c in metricas["cumpleaneras_hoy"]]
        assert "Ana Cumple Hoy" in nombres_hoy
        assert "Beatriz Cumple Octubre" not in nombres_hoy


@pytest.mark.django_db
class TestDashboardViewIntegration:
    def test_dashboard_requiere_login(self, client):
        """Visitante sin sesión debe ser redirigido al login."""
        response = client.get(reverse("index"))
        assert response.status_code == 302
        assert "/usuarios/login/" in response.url

    def test_dashboard_renderiza_con_usuario_autenticado(self, client, administradora):
        """Usuario logueado accede correctamente al Dashboard con código HTTP 200 y métricas."""
        client.force_login(administradora)
        response = client.get(reverse("index"))
        assert response.status_code == 200
        assert "Turnos del Día" in response.content.decode("utf-8")
        assert "Ingresos de Hoy" in response.content.decode("utf-8")
        assert "Alertas de Stock" in response.content.decode("utf-8")
        assert "Próximos Turnos" in response.content.decode("utf-8")
        assert "Cumpleaños" in response.content.decode("utf-8")
