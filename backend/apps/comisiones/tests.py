"""
Peluquería Lorena — Pruebas unitarias del módulo de Comisiones y Liquidación (RF8).

Verifica:
- RF 8.1: Configuración de porcentajes por categoría y defaults relevados (50% cortes, 25% técnicos).
- RF 8.2: Cálculo automático de comisión sobre el presupuesto cargado.
- RF 8.3: Registro ágil de trabajos por peluquera.
- RF 8.4: Generación de reporte de liquidación por período y profesional.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.comisiones.models import ConfiguracionComision, Liquidacion
from apps.comisiones.services import ComisionService
from apps.servicios.models import Servicio, ServicioRealizado
from apps.usuarios.models import Usuario


class ComisionesTestCase(TestCase):
    def setUp(self):
        # Crear usuarios con roles
        self.admin = Usuario.objects.create_superuser(
            email="admin@pelulorena.com",
            password="adminpassword123",
            nombre="Lorena Administradora",
            dni="11111111",
            rol=Usuario.Rol.ADMIN,
        )
        self.peluquera = Usuario.objects.create_user(
            email="peluquera@pelulorena.com",
            password="empleadapassword123",
            nombre="María Peluquera",
            dni="22222222",
            rol=Usuario.Rol.EMPLEADA,
        )

        # Crear servicios de distintas categorías
        self.servicio_corte = Servicio.objects.create(
            nombre="Corte Damas Test",
            categoria=Servicio.Categoria.CORTES,
            precio_base=Decimal("20000.00"),
            duracion_estimada_minutos=45,
        )
        self.servicio_color = Servicio.objects.create(
            nombre="Color Raíz Test",
            categoria=Servicio.Categoria.COLOR,
            precio_base=Decimal("60000.00"),
            duracion_estimada_minutos=90,
        )
        self.servicio_mechas = Servicio.objects.create(
            nombre="Balayage Test",
            categoria=Servicio.Categoria.MECHAS,
            precio_base=Decimal("100000.00"),
            duracion_estimada_minutos=180,
            requiere_consentimiento=True,
        )

        # Cliente
        self.cliente = Cliente.objects.create(
            nombre="Laura Clienta",
            telefono="1122334455",
            email="laura@test.com",
        )

    def test_rf8_1_configuracion_comisiones_defaults(self):
        """RF 8.1: Sembrado y obtención de comisiones por categoría (50% corte, 25% técnicos)."""
        ComisionService.sembrar_configuracion_defecto()

        pct_corte = ComisionService.obtener_porcentaje_categoria(Servicio.Categoria.CORTES)
        pct_color = ComisionService.obtener_porcentaje_categoria(Servicio.Categoria.COLOR)
        pct_mechas = ComisionService.obtener_porcentaje_categoria(Servicio.Categoria.MECHAS)
        pct_trat = ComisionService.obtener_porcentaje_categoria(Servicio.Categoria.TRATAMIENTOS)

        self.assertEqual(pct_corte, Decimal("50.00"))
        self.assertEqual(pct_color, Decimal("25.00"))
        self.assertEqual(pct_mechas, Decimal("25.00"))
        self.assertEqual(pct_trat, Decimal("25.00"))

    def test_rf8_1_modificacion_porcentaje_categoria(self):
        """RF 8.1: Permitir que la administradora modifique el porcentaje de una categoría."""
        ComisionService.sembrar_configuracion_defecto()

        config = ConfiguracionComision.objects.get(categoria=Servicio.Categoria.CORTES)
        config.porcentaje = Decimal("55.00")
        config.save()

        nuevo_pct = ComisionService.obtener_porcentaje_categoria(Servicio.Categoria.CORTES)
        self.assertEqual(nuevo_pct, Decimal("55.00"))

    def test_rf8_2_calculo_automatico_comision_sobre_presupuesto(self):
        """RF 8.2: Cálculo automático de la comisión sobre el presupuesto pactado."""
        ComisionService.sembrar_configuracion_defecto()

        # Corte con presupuesto pactado de $24.000 (50% de comisión = $12.000)
        pct_corte, monto_corte = ComisionService.calcular_comision(
            servicio=self.servicio_corte,
            precio_acordado=Decimal("24000.00"),
        )
        self.assertEqual(pct_corte, Decimal("50.00"))
        self.assertEqual(monto_corte, Decimal("12000.00"))

        # Color con presupuesto personalizado de $70.000 (25% de comisión = $17.500)
        pct_color, monto_color = ComisionService.calcular_comision(
            servicio=self.servicio_color,
            precio_acordado=Decimal("70000.00"),
        )
        self.assertEqual(pct_color, Decimal("25.00"))
        self.assertEqual(monto_color, Decimal("17500.00"))

    def test_rf8_2_persistencia_automatica_en_servicio_realizado(self):
        """RF 8.2: Al guardar un ServicioRealizado, se calcula y persiste monto_comision."""
        ComisionService.sembrar_configuracion_defecto()

        trabajo = ServicioRealizado.objects.create(
            servicio=self.servicio_corte,
            profesional=self.peluquera,
            cliente_nombre="Paula Gómez",
            precio_acordado=Decimal("30000.00"),
            fecha=timezone.localdate(),
        )

        self.assertEqual(trabajo.porcentaje_comision, Decimal("50.00"))
        self.assertEqual(trabajo.monto_comision, Decimal("15000.00"))

    def test_rf8_3_registro_trabajo_peluquera(self):
        """RF 8.3: Registro simple de trabajos por la peluquera."""
        trabajo = ComisionService.registrar_trabajo_peluquera(
            servicio=self.servicio_mechas,
            profesional=self.peluquera,
            cliente_nombre="Camila Flores",
            precio_acordado=Decimal("120000.00"),
            cliente=self.cliente,
            notas="Balayage con decolorante bajo en amoníaco",
        )

        self.assertIsNotNone(trabajo.pk)
        self.assertEqual(trabajo.profesional, self.peluquera)
        self.assertEqual(trabajo.precio_acordado, Decimal("120000.00"))
        # 25% de 120.000 = 30.000
        self.assertEqual(trabajo.monto_comision, Decimal("30000.00"))
        self.assertEqual(trabajo.estado, ServicioRealizado.Estado.COMPLETADO)

    def test_rf8_4_reporte_liquidacion_por_periodo_y_peluquera(self):
        """RF 8.4: Generación del reporte de liquidación consolidado por peluquera y período."""
        ComisionService.sembrar_configuracion_defecto()

        hoy = timezone.localdate()
        hace_tres_dias = hoy - timedelta(days=3)

        # Trabajo 1: Corte $20.000 -> comisión $10.000
        ServicioRealizado.objects.create(
            servicio=self.servicio_corte,
            profesional=self.peluquera,
            cliente_nombre="Clienta 1",
            precio_acordado=Decimal("20000.00"),
            fecha=hoy,
        )

        # Trabajo 2: Color $60.000 -> comisión $15.000
        ServicioRealizado.objects.create(
            servicio=self.servicio_color,
            profesional=self.peluquera,
            cliente_nombre="Clienta 2",
            precio_acordado=Decimal("60000.00"),
            fecha=hace_tres_dias,
        )

        resumen = ComisionService.obtener_resumen_liquidacion(
            profesional_id=self.peluquera.pk,
            fecha_desde=hace_tres_dias,
            fecha_hasta=hoy,
        )

        self.assertEqual(resumen["total_servicios"], 2)
        self.assertEqual(resumen["total_bruto"], Decimal("80000.00"))
        self.assertEqual(resumen["total_comisiones"], Decimal("25000.00"))

        self.assertEqual(len(resumen["por_profesional"]), 1)
        self.assertEqual(resumen["por_profesional"][0]["profesional"], self.peluquera)
        self.assertEqual(resumen["por_profesional"][0]["comision"], Decimal("25000.00"))

    def test_rf8_4_cerrar_liquidacion_periodo(self):
        """RF 8.4: Asiento formal de liquidación y cierre."""
        ComisionService.sembrar_configuracion_defecto()
        hoy = timezone.localdate()

        trabajo = ServicioRealizado.objects.create(
            servicio=self.servicio_corte,
            profesional=self.peluquera,
            cliente_nombre="Clienta Test",
            precio_acordado=Decimal("20000.00"),
            fecha=hoy,
        )

        liquidacion = ComisionService.cerrar_liquidacion_periodo(
            profesional=self.peluquera,
            fecha_desde=hoy,
            fecha_hasta=hoy,
            liquidado_por=self.admin,
            observaciones="Pago en efectivo contra recibo",
        )

        self.assertIsNotNone(liquidacion.pk)
        self.assertEqual(liquidacion.total_servicios, 1)
        self.assertEqual(liquidacion.total_comision, Decimal("10000.00"))

        trabajo.refresh_from_db()
        self.assertEqual(trabajo.liquidacion, liquidacion)

    def test_vistas_render_exitoso(self):
        """Verifica que las plantillas de comisiones compilen y rendericen correctamente."""
        self.client.force_login(self.admin)

        resp_registrar = self.client.get("/comisiones/registrar/")
        self.assertEqual(resp_registrar.status_code, 200)
        self.assertTemplateUsed(resp_registrar, "comisiones/registro_trabajo.html")

        resp_config = self.client.get("/comisiones/configuracion/")
        self.assertEqual(resp_config.status_code, 200)
        self.assertTemplateUsed(resp_config, "comisiones/configuracion.html")

        resp_mis = self.client.get("/comisiones/mis-comisiones/")
        self.assertEqual(resp_mis.status_code, 200)
        self.assertTemplateUsed(resp_mis, "comisiones/mis_comisiones.html")

        resp_liq = self.client.get("/comisiones/liquidacion/")
        self.assertEqual(resp_liq.status_code, 200)
        self.assertTemplateUsed(resp_liq, "comisiones/reporte_liquidacion.html")
