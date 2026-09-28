"""
Peluquería Lorena — Pruebas del módulo de Fidelización y Beneficios (RF10).

Cubre:
- RF 10.1: Creación y parametrización de ReglaBeneficio (Cumpleaños y Regularidad).
- RF 10.2: Detección de cumpleaños y otorgamiento idempotente anual de cupones.
- RF 10.3: Evaluación de regularidad por visitas y monto acumulado (anti-spam y ventanas móviles).
- Despacho de avisos mediante MensajeriaService (mock WhatsApp/Email).
- Canje y control de vencimiento de BeneficioOtorgado.
- Reemplazo y render de variables en plantillas de mensaje.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.fidelizacion.models import BeneficioOtorgado, MensajeBeneficio, ReglaBeneficio
from apps.fidelizacion.services import (
    FidelizacionService,
    MensajeriaService,
    generar_codigo_beneficio,
    renderizar_plantilla,
)
from apps.servicios.models import Servicio, ServicioRealizado
from apps.turnos.models import Turno
from apps.usuarios.models import Usuario


class FidelizacionTestCase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            email="admin.fiel@pelulorena.com",
            password="pass",
            nombre="Lorena Admin",
            dni="33333333",
            rol=Usuario.Rol.ADMIN,
        )
        self.peluquera = Usuario.objects.create_user(
            email="peluquera.fiel@pelulorena.com",
            password="pass",
            nombre="Andrea Peluquera",
            dni="44444444",
            rol=Usuario.Rol.EMPLEADA,
        )

        self.servicio = Servicio.objects.create(
            nombre="Corte Damas",
            categoria=Servicio.Categoria.CORTES,
            precio_base=Decimal("25000.00"),
            duracion_estimada_minutos=45,
        )

        self.hoy = timezone.localdate()

        # Clienta con cumple en 2 días
        cumple_proximo = (self.hoy + timedelta(days=2)).replace(year=1995)
        self.clienta_cumple = Cliente.objects.create(
            nombre="Sofía Cumpleañera",
            telefono="1122334455",
            email="sofia@test.com",
            fecha_nacimiento=cumple_proximo,
            activo=True,
        )

        # Clienta con cumple lejano (en 30 días)
        cumple_lejano = (self.hoy + timedelta(days=30)).replace(year=1990)
        self.clienta_lejana = Cliente.objects.create(
            nombre="Lucía Lejana",
            telefono="1199887766",
            email="lucia@test.com",
            fecha_nacimiento=cumple_lejano,
            activo=True,
        )

        # Regla de Cumpleaños
        self.regla_cumple = ReglaBeneficio.objects.create(
            nombre="Cumpleaños 15% OFF",
            tipo=ReglaBeneficio.Tipo.CUMPLEANOS,
            ventana_dias=5,
            tipo_recompensa=ReglaBeneficio.TipoRecompensa.PORCENTAJE,
            valor=Decimal("15.00"),
            dias_validez=30,
            plantilla_mensaje="¡Feliz cumple {nombre_cliente}! Tenés {descuento} con código {codigo} hasta {fecha_limite}.",
            activo=True,
        )

        # Regla de Regularidad (3 visitas en los últimos 30 días)
        self.regla_regularidad = ReglaBeneficio.objects.create(
            nombre="Fidelidad 3 Visitas",
            tipo=ReglaBeneficio.Tipo.REGULARIDAD,
            min_visitas=3,
            min_monto=Decimal("0.00"),
            periodo_dias=30,
            tipo_recompensa=ReglaBeneficio.TipoRecompensa.PORCENTAJE,
            valor=Decimal("20.00"),
            dias_validez=15,
            plantilla_mensaje="¡Hola {nombre_cliente}! Por ser clienta fiel tenés {descuento}. Código: {codigo}.",
            activo=True,
        )

    def test_utilidades_codigo_y_plantilla(self):
        """Verifica generación de código y reemplazo de variables en plantilla."""
        codigo = generar_codigo_beneficio("CUM")
        self.assertTrue(codigo.startswith("CUM-"))
        self.assertEqual(len(codigo), 10)  # CUM- + 6 hex

        contexto = {
            "nombre_cliente": "Sofía",
            "descuento": "15,00% OFF",
            "codigo": "CUM-TEST01",
            "fecha_limite": "25/10/2026",
        }
        res = renderizar_plantilla("Hola {nombre_cliente}, cupón {codigo} con {descuento} hasta {fecha_limite}.", contexto)
        self.assertIn("Sofía", res)
        self.assertIn("CUM-TEST01", res)
        self.assertIn("15,00% OFF", res)
        self.assertIn("25/10/2026", res)

    def test_regla_propiedades_y_descripcion(self):
        """Verifica descripciones dinámicas de recompensas en ReglaBeneficio."""
        self.assertEqual(self.regla_cumple.descripcion_recompensa, "15,00% OFF")
        self.assertIn("Cumpleaños", str(self.regla_cumple))

        regla_fija = ReglaBeneficio.objects.create(
            nombre="Descuento Fijo",
            tipo=ReglaBeneficio.Tipo.REGULARIDAD,
            tipo_recompensa=ReglaBeneficio.TipoRecompensa.MONTO_FIJO,
            valor=Decimal("5000.00"),
            dias_validez=10,
        )
        self.assertEqual(regla_fija.descripcion_recompensa, "$5.000,00 OFF")

    def test_clientas_cumpleanos_en_ventana(self):
        """Lista correctamente las clientas cuyo cumpleaños cae dentro de la ventana de aviso."""
        clientas = FidelizacionService.clientas_cumpleanos_en_ventana(ventana_dias=5, hoy=self.hoy)
        self.assertIn(self.clienta_cumple, clientas)
        self.assertNotIn(self.clienta_lejana, clientas)

    def test_procesar_cumpleanos_crea_beneficio_e_idempotencia_anual(self):
        """El proceso de cumpleaños otorga el cupón una sola vez por año para cada clienta."""
        res1 = FidelizacionService.procesar_cumpleanos(hoy=self.hoy)
        self.assertEqual(len(res1["otorgados"]), 1)
        beneficio = res1["otorgados"][0]
        self.assertEqual(beneficio.cliente, self.clienta_cumple)
        self.assertEqual(beneficio.estado, BeneficioOtorgado.Estado.DISPONIBLE)
        self.assertTrue(beneficio.codigo.startswith("CUM-"))
        self.assertEqual(beneficio.ciclo_referencia, str(self.hoy.year))

        # Mensaje despachado
        mensajes = MensajeBeneficio.objects.filter(beneficio=beneficio)
        self.assertEqual(mensajes.count(), 1)
        self.assertEqual(mensajes.first().estado_envio, MensajeBeneficio.EstadoEnvio.ENVIADO)

        # Segunda ejecución en el mismo año: debe omitirse por duplicado
        res2 = FidelizacionService.procesar_cumpleanos(hoy=self.hoy)
        self.assertEqual(len(res2["otorgados"]), 0)
        self.assertEqual(res2["omitidos_duplicados"], 1)

    def test_contar_actividad_cliente_y_evitar_doble_conteo(self):
        """Visitas no se duplican cuando el turno ya tiene un servicio_realizado vinculado."""
        # 1. Crear un servicio realizado
        sr = ServicioRealizado.objects.create(
            servicio=self.servicio,
            profesional=self.peluquera,
            cliente=self.clienta_lejana,
            cliente_nombre=self.clienta_lejana.nombre,
            fecha=self.hoy,
            precio_acordado=Decimal("25000.00"),
            estado=ServicioRealizado.Estado.COMPLETADO,
        )
        # 2. Crear un turno completado vinculado a ese mismo servicio realizado
        Turno.objects.create(
            cliente=self.clienta_lejana,
            cliente_nombre=self.clienta_lejana.nombre,
            servicio=self.servicio,
            profesional=self.peluquera,
            servicio_realizado=sr,
            fecha=self.hoy,
            hora=timezone.localtime().time(),
            estado=Turno.Estado.COMPLETADO,
        )

        visitas, monto = FidelizacionService.contar_actividad_cliente(
            cliente=self.clienta_lejana,
            fecha_desde=self.hoy - timedelta(days=30),
            fecha_hasta=self.hoy,
        )
        # Debe contar exactamente 1 visita (no 2)
        self.assertEqual(visitas, 1)
        self.assertEqual(monto, Decimal("25000.00"))

    def test_procesar_regularidad_con_visitas(self):
        """Alcanzar el umbral de visitas otorga el beneficio y no lo duplica si ya está disponible."""
        # Registrar 3 atenciones completadas para la clienta
        for i in range(3):
            ServicioRealizado.objects.create(
                servicio=self.servicio,
                profesional=self.peluquera,
                cliente=self.clienta_lejana,
                cliente_nombre=self.clienta_lejana.nombre,
                fecha=self.hoy - timedelta(days=i),
                precio_acordado=Decimal("20000.00"),
                estado=ServicioRealizado.Estado.COMPLETADO,
            )

        res = FidelizacionService.procesar_regularidad(hoy=self.hoy)
        self.assertEqual(len(res["otorgados"]), 1)
        beneficio = res["otorgados"][0]
        self.assertEqual(beneficio.cliente, self.clienta_lejana)
        self.assertEqual(beneficio.visitas_contadas, 3)

        # Si corre nuevamente con un cupón DISPONIBLE vigente, no genera otro
        res2 = FidelizacionService.procesar_regularidad(hoy=self.hoy)
        self.assertEqual(len(res2["otorgados"]), 0)

    def test_canje_de_beneficio(self):
        """Un beneficio disponible puede ser canjeado por una profesional."""
        beneficio, _ = FidelizacionService.otorgar_beneficio(
            cliente=self.clienta_cumple,
            regla=self.regla_cumple,
            ciclo_referencia="TEST-CANJE",
            hoy=self.hoy,
        )
        self.assertTrue(beneficio.esta_vigente)

        beneficio.canjear(profesional=self.peluquera, observaciones="Canjeado en corte")
        self.assertEqual(beneficio.estado, BeneficioOtorgado.Estado.CANJEADO)
        self.assertEqual(beneficio.canjeado_por, self.peluquera)
        self.assertIsNotNone(beneficio.fecha_canje)
        self.assertFalse(beneficio.esta_vigente)

        # Canjear de nuevo debe fallar
        with self.assertRaises(ValueError):
            beneficio.canjear(profesional=self.peluquera)

    def test_marcar_vencidos(self):
        """Cupones vencidos cambian a estado VENCIDO automáticamente."""
        beneficio, _ = FidelizacionService.otorgar_beneficio(
            cliente=self.clienta_cumple,
            regla=self.regla_cumple,
            ciclo_referencia="TEST-VENCE",
            hoy=self.hoy - timedelta(days=40),
        )
        self.assertEqual(beneficio.estado, BeneficioOtorgado.Estado.DISPONIBLE)

        vencidos = FidelizacionService.marcar_vencidos(hoy=self.hoy)
        self.assertGreaterEqual(vencidos, 1)

        beneficio.refresh_from_db()
        self.assertEqual(beneficio.estado, BeneficioOtorgado.Estado.VENCIDO)
        self.assertFalse(beneficio.esta_vigente)
