"""
Pruebas unitarias para el catálogo de Servicios, Consentimiento Informado y Cierre de Insumos.
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.clientes.services import ClienteService
from apps.inventario.models import Producto
from apps.servicios.models import ConsentimientoInformado, ConsumoInsumoCierre, Servicio, ServicioRealizado
from apps.servicios.services import ServicioService
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.mark.django_db
class TestCatalogoYControlDiarioServicios:
    """Pruebas del catálogo oficial y la atención diaria con personalización de tarifas."""

    def test_cargar_catalogo_inicial_oficial(self) -> None:
        cantidad = ServicioService.cargar_catalogo_inicial()
        assert cantidad >= 15

        balayage = Servicio.objects.get(nombre="Balayage (desde)")
        assert balayage.precio_base == Decimal("120000.00")
        assert balayage.duracion_estimada_minutos == 180
        assert balayage.requiere_consentimiento is True
        assert balayage.categoria == Servicio.Categoria.MECHAS

        corte_damas = Servicio.objects.get(nombre="Corte Damas")
        assert corte_damas.precio_base == Decimal("25000.00")
        assert corte_damas.duracion_estimada_minutos == 45
        assert corte_damas.requiere_consentimiento is False

        alisado = Servicio.objects.get(nombre="Alisado (desde)")
        assert alisado.precio_base == Decimal("80000.00")
        assert alisado.requiere_consentimiento is True

    def test_personalizar_precio_y_plazo_segun_clienta(self) -> None:
        profesional = EmpleadaFactory()
        servicio = ServicioService.crear_servicio(
            nombre="Balayage Especial",
            categoria=Servicio.Categoria.MECHAS,
            precio_base=Decimal("120000.00"),
            duracion_estimada_minutos=180,
            requiere_consentimiento=True,
        )

        # La clienta tiene cabello hasta la cintura y extra abundante
        # Se pacta $150.000 y 240 minutos
        atencion = ServicioService.registrar_servicio_realizado(
            servicio=servicio,
            profesional=profesional,
            cliente_nombre="Gabriela Long Hair",
            precio_acordado=Decimal("150000.00"),
            duracion_minutos=240,
            notas="Cabello por la cintura, requiere doble formulación",
        )

        assert atencion.precio_acordado == Decimal("150000.00")
        assert atencion.duracion_minutos == 240
        assert atencion.precioAcordado == Decimal("150000.00")
        assert atencion.duracionMinutos == 240
        assert atencion.servicio.precio_base == Decimal("120000.00")  # El catálogo base no se altera


@pytest.mark.django_db
class TestConsentimientoInformado:
    """Pruebas para la ficha técnica y de resguardo legal en decoloraciones y alisados."""

    def test_emision_consentimiento_con_declaracion_jurada(self) -> None:
        profesional = AdministradoraFactory()
        cliente = ClienteService.crear_cliente(nombre="Florencia Mechas", telefono="1144556677")

        consentimiento = ServicioService.crear_consentimiento(
            cliente=cliente,
            cliente_nombre=cliente.nombre,
            cliente_telefono=cliente.telefono,
            cliente_dni="35123456",
            tipo_procedimiento=ConsentimientoInformado.TipoProcedimiento.DECOLORACION,
            profesional=profesional,
            ha_usado_henna_o_sales_metalicas=False,
            tiene_alisados_o_permanentes_previos=True,
            detalle_quimicos_previos="Alisado con ácido glioxílico hace 4 meses",
            prueba_mecha_realizada=True,
            resultado_prueba_mecha=ConsentimientoInformado.ResultadoPruebaMecha.APTO_PRECAUCION,
            elasticidad_cabello=ConsentimientoInformado.EstadoFibra.REGULAR,
            porosidad_cabello=ConsentimientoInformado.EstadoFibra.REGULAR,
            acepta_terminos=True,
            firma_digital="Florencia Mechas - Acepto términos",
            observaciones="Aclarar con oxidante de 20 volúmenes máximo para cuidar la fibra",
        )

        assert consentimiento.cliente_nombre == "Florencia Mechas"
        assert consentimiento.tiene_alisados_o_permanentes_previos is True
        assert consentimiento.resultado_prueba_mecha == ConsentimientoInformado.ResultadoPruebaMecha.APTO_PRECAUCION
        assert consentimiento.acepta_terminos is True
        assert consentimiento.cliente == cliente


@pytest.mark.django_db
class TestCierreDiarioYDescuentoInsumos:
    """Pruebas para el cómputo consolidado de servicios y descuento masivo de stock."""

    def test_cierre_diario_computa_personas_y_descuenta_stock(self) -> None:
        profesional = EmpleadaFactory()
        admin = AdministradoraFactory()
        dia = timezone.localdate()

        # 1. Crear insumo en inventario
        polvo_deco = Producto.objects.create(
            nombre="Polvo Decolorante Azul 500g",
            stock_actual=10,
            stock_minimo=3,
            precio=Decimal("25000.00"),
            activo=True,
        )

        servicio_balayage = ServicioService.crear_servicio(
            nombre="Balayage Test",
            categoria=Servicio.Categoria.MECHAS,
            precio_base=Decimal("120000.00"),
        )

        # 2. Registrar 3 clientas que se hicieron Balayage hoy
        for i in range(3):
            ServicioService.registrar_servicio_realizado(
                servicio=servicio_balayage,
                profesional=profesional,
                cliente_nombre=f"Clienta Balayage {i+1}",
                fecha=dia,
                estado=ServicioRealizado.Estado.COMPLETADO,
            )

        # 3. Obtener resumen de cierre del día
        resumen = ServicioService.obtener_resumen_servicios_dia(fecha=dia)
        assert len(resumen) == 1
        assert resumen[0]["servicio_id"] == servicio_balayage.id
        assert resumen[0]["total_personas"] == 3
        assert resumen[0]["insumos_descontados"] is False

        # 4. Descontar insumos al terminar el día (se usaron 2 potes para las 3 clientas)
        consumos = ServicioService.descontar_insumos_cierre_dia(
            servicio_id=servicio_balayage.id,
            fecha=dia,
            insumos=[{"producto_id": polvo_deco.id, "cantidad": 2}],
            usuario=admin,
        )

        assert len(consumos) == 1
        assert consumos[0].cantidad == 2
        assert consumos[0].cantidad_servicios_computados == 3

        # Verificar que el stock de inventario se descontó correctamente (10 - 2 = 8)
        polvo_deco.refresh_from_db()
        assert polvo_deco.stock_actual == 8

        # Verificar que los servicios del día quedaron marcados como insumos_descontados = True
        resumen_post = ServicioService.obtener_resumen_servicios_dia(fecha=dia)
        assert resumen_post[0]["insumos_descontados"] is True

    def test_cierre_diario_no_descuenta_stock_dos_veces(self) -> None:
        """Repetir el cierre del mismo servicio y día no vuelve a descontar stock."""
        profesional = EmpleadaFactory()
        admin = AdministradoraFactory()
        dia = timezone.localdate()

        producto = Producto.objects.create(
            nombre="Oxigenta 20 vol",
            stock_actual=10,
            stock_minimo=2,
            precio=Decimal("12000.00"),
            activo=True,
        )
        servicio = ServicioService.crear_servicio(
            nombre="Reflejos Test",
            categoria=Servicio.Categoria.MECHAS,
            precio_base=Decimal("95000.00"),
        )
        ServicioService.registrar_servicio_realizado(
            servicio=servicio,
            profesional=profesional,
            cliente_nombre="Clienta Reflejos",
            fecha=dia,
            estado=ServicioRealizado.Estado.COMPLETADO,
        )

        ServicioService.descontar_insumos_cierre_dia(
            servicio_id=servicio.id,
            fecha=dia,
            insumos=[{"producto_id": producto.id, "cantidad": 2}],
            usuario=admin,
        )
        producto.refresh_from_db()
        assert producto.stock_actual == 8

        # Segundo intento: debe rechazarse y NO tocar el stock
        with pytest.raises(ValueError):
            ServicioService.descontar_insumos_cierre_dia(
                servicio_id=servicio.id,
                fecha=dia,
                insumos=[{"producto_id": producto.id, "cantidad": 2}],
                usuario=admin,
            )
        producto.refresh_from_db()
        assert producto.stock_actual == 8
