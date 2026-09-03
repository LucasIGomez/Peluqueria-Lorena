"""
Peluquería Lorena — Capa de Servicios del módulo de Servicios.

Centraliza la lógica de negocio para:
- Catálogo de servicios oficial y personalización de precios/tiempos por clienta.
- Control diario de servicios por fecha y horario.
- Emisión y validación de consentimientos informados (decoloración y alisado).
- Cierre del día: cómputo consolidado de personas atendidas y descuento automático de insumos en inventario.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.inventario.services import InventarioService
from .models import ConsentimientoInformado, ConsumoInsumoCierre, Servicio, ServicioRealizado


class ServicioService:
    """
    Servicio de dominio para la gestión del catálogo, la atención diaria,
    los consentimientos informados y el cierre de insumos.
    """

    # ── Catálogo Inicial Oficial ──

    @classmethod
    def cargar_catalogo_inicial(cls) -> int:
        """
        Siembra o actualiza el catálogo inicial según la lista de precios oficial
        del salón de Lorena. Retorna la cantidad de servicios procesados.
        """
        tarifario = [
            # Cortes
            {"nombre": "Corte Damas", "categoria": Servicio.Categoria.CORTES, "precio_base": Decimal("25000.00"), "duracion_estimada_minutos": 45, "requiere_consentimiento": False},
            {"nombre": "Corte Caballeros", "categoria": Servicio.Categoria.CORTES, "precio_base": Decimal("20000.00"), "duracion_estimada_minutos": 30, "requiere_consentimiento": False},
            {"nombre": "Corte Niños", "categoria": Servicio.Categoria.CORTES, "precio_base": Decimal("20000.00"), "duracion_estimada_minutos": 30, "requiere_consentimiento": False},
            # Color
            {"nombre": "Color Raíz (desde)", "categoria": Servicio.Categoria.COLOR, "precio_base": Decimal("50000.00"), "duracion_estimada_minutos": 90, "requiere_consentimiento": False},
            {"nombre": "Shampoo Color", "categoria": Servicio.Categoria.COLOR, "precio_base": Decimal("35000.00"), "duracion_estimada_minutos": 45, "requiere_consentimiento": False},
            {"nombre": "Color Completo (desde)", "categoria": Servicio.Categoria.COLOR, "precio_base": Decimal("65000.00"), "duracion_estimada_minutos": 120, "requiere_consentimiento": False},
            # Mechas (Procesos de Decoloración)
            {"nombre": "Iluminación (desde)", "categoria": Servicio.Categoria.MECHAS, "precio_base": Decimal("90000.00"), "duracion_estimada_minutos": 150, "requiere_consentimiento": True},
            {"nombre": "Reflejos (desde)", "categoria": Servicio.Categoria.MECHAS, "precio_base": Decimal("95000.00"), "duracion_estimada_minutos": 150, "requiere_consentimiento": True},
            {"nombre": "Balayage (desde)", "categoria": Servicio.Categoria.MECHAS, "precio_base": Decimal("120000.00"), "duracion_estimada_minutos": 180, "requiere_consentimiento": True},
            {"nombre": "Mechas Localizadas (desde)", "categoria": Servicio.Categoria.MECHAS, "precio_base": Decimal("120000.00"), "duracion_estimada_minutos": 180, "requiere_consentimiento": True},
            # Tratamientos Capilares
            {"nombre": "Alisado (desde)", "categoria": Servicio.Categoria.TRATAMIENTOS, "precio_base": Decimal("80000.00"), "duracion_estimada_minutos": 180, "requiere_consentimiento": True},
            {"nombre": "Ampolla Nutritiva", "categoria": Servicio.Categoria.TRATAMIENTOS, "precio_base": Decimal("30000.00"), "duracion_estimada_minutos": 30, "requiere_consentimiento": False},
            {"nombre": "Hidratación Profunda", "categoria": Servicio.Categoria.TRATAMIENTOS, "precio_base": Decimal("25000.00"), "duracion_estimada_minutos": 45, "requiere_consentimiento": False},
            # Otros
            {"nombre": "Brushing o Plancha", "categoria": Servicio.Categoria.OTROS, "precio_base": Decimal("35000.00"), "duracion_estimada_minutos": 40, "requiere_consentimiento": False},
            {"nombre": "Peinados de Fiesta (desde)", "categoria": Servicio.Categoria.OTROS, "precio_base": Decimal("40000.00"), "duracion_estimada_minutos": 60, "requiere_consentimiento": False},
        ]

        contador = 0
        for item in tarifario:
            Servicio.objects.update_or_create(
                nombre=item["nombre"],
                defaults={
                    "categoria": item["categoria"],
                    "precio_base": item["precio_base"],
                    "duracion_estimada_minutos": item["duracion_estimada_minutos"],
                    "requiere_consentimiento": item["requiere_consentimiento"],
                    "activo": True,
                },
            )
            contador += 1
        return contador

    # ── CRUD de Catálogo ──

    @staticmethod
    def crear_servicio(
        nombre: str,
        categoria: str,
        precio_base: Decimal | str,
        duracion_estimada_minutos: int = 60,
        requiere_consentimiento: bool = False,
        descripcion: str = "",
    ) -> Servicio:
        """Crea un nuevo servicio en el catálogo."""
        return Servicio.objects.create(
            nombre=nombre.strip(),
            categoria=categoria,
            precio_base=Decimal(str(precio_base)),
            duracion_estimada_minutos=duracion_estimada_minutos,
            requiere_consentimiento=requiere_consentimiento,
            descripcion=descripcion.strip(),
            activo=True,
        )

    @staticmethod
    def listar_servicios(categoria: Optional[str] = None, solo_activos: bool = True) -> QuerySet[Servicio]:
        """Retorna los servicios del catálogo, con filtro opcional por categoría."""
        queryset = Servicio.objects.all()
        if solo_activos:
            queryset = queryset.filter(activo=True)
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        return queryset.order_by("categoria", "nombre")

    @staticmethod
    def obtener_servicio_por_id(servicio_id: int) -> Optional[Servicio]:
        """Obtiene un servicio por su identificador único."""
        try:
            return Servicio.objects.get(pk=servicio_id)
        except Servicio.DoesNotExist:
            return None

    @staticmethod
    def actualizar_servicio(
        servicio: Servicio,
        nombre: Optional[str] = None,
        categoria: Optional[str] = None,
        precio_base: Optional[Decimal | str] = None,
        duracion_estimada_minutos: Optional[int] = None,
        requiere_consentimiento: Optional[bool] = None,
        descripcion: Optional[str] = None,
        activo: Optional[bool] = None,
    ) -> Servicio:
        """Actualiza la configuración o tarifa base de un servicio."""
        if nombre is not None:
            servicio.nombre = nombre.strip()
        if categoria is not None:
            servicio.categoria = categoria
        if precio_base is not None:
            servicio.precio_base = Decimal(str(precio_base))
        if duracion_estimada_minutos is not None:
            servicio.duracion_estimada_minutos = duracion_estimada_minutos
        if requiere_consentimiento is not None:
            servicio.requiere_consentimiento = requiere_consentimiento
        if descripcion is not None:
            servicio.descripcion = descripcion.strip()
        if activo is not None:
            servicio.activo = activo

        servicio.save()
        return servicio

    @staticmethod
    def eliminar_servicio(servicio: Servicio) -> None:
        """Baja lógica de un servicio del catálogo."""
        servicio.activo = False
        servicio.save(update_fields=["activo"])

    # ── Control Diario de Servicios (Personalización por Cliente) ──

    @staticmethod
    def registrar_servicio_realizado(
        servicio: Servicio,
        profesional: Any,
        cliente_nombre: str,
        precio_acordado: Optional[Decimal | str] = None,
        duracion_minutos: Optional[int] = None,
        cliente: Any = None,
        cliente_telefono: str = "",
        fecha: Optional[date] = None,
        hora: Optional[time] = None,
        estado: str = ServicioRealizado.Estado.COMPLETADO,
        notas: str = "",
        consentimiento: Optional[ConsentimientoInformado] = None,
    ) -> ServicioRealizado:
        """
        Registra la atención de un servicio en una fecha y horario específicos,
        permitiendo personalizar el precio y tiempo según el cabello de la clienta.
        """
        precio_final = Decimal(str(precio_acordado)) if precio_acordado is not None else servicio.precio_base
        duracion_final = duracion_minutos if duracion_minutos is not None else servicio.duracion_estimada_minutos

        return ServicioRealizado.objects.create(
            servicio=servicio,
            profesional=profesional,
            cliente=cliente,
            cliente_nombre=cliente_nombre.strip(),
            cliente_telefono=cliente_telefono.strip(),
            fecha=fecha or timezone.localdate(),
            hora=hora or timezone.localtime().time(),
            precio_acordado=precio_final,
            duracion_minutos=duracion_final,
            estado=estado,
            notas=notas.strip(),
            consentimiento=consentimiento,
        )

    @staticmethod
    def listar_servicios_por_fecha(
        fecha: Optional[date] = None,
        profesional_id: Optional[int] = None,
    ) -> QuerySet[ServicioRealizado]:
        """Lista los servicios brindados en una fecha específica, ordenados por hora."""
        dia = fecha or timezone.localdate()
        queryset = ServicioRealizado.objects.filter(fecha=dia).select_related(
            "servicio", "profesional", "cliente", "consentimiento"
        )
        if profesional_id:
            queryset = queryset.filter(profesional_id=profesional_id)
        return queryset.order_by("hora")

    # ── Ficha de Consentimiento Informado ──

    @staticmethod
    def crear_consentimiento(
        cliente_nombre: str,
        cliente_telefono: str,
        tipo_procedimiento: str = ConsentimientoInformado.TipoProcedimiento.DECOLORACION,
        cliente: Any = None,
        cliente_dni: str = "",
        profesional: Any = None,
        ha_usado_henna_o_sales_metalicas: bool = False,
        tiene_alisados_o_permanentes_previos: bool = False,
        detalle_quimicos_previos: str = "",
        tiene_decoloraciones_previas: bool = False,
        alergias_o_sensibilidad_cuero_cabelludo: bool = False,
        detalle_alergias: str = "",
        embarazo_o_lactancia: bool = False,
        medicacion_o_tratamiento_medico: bool = False,
        prueba_mecha_realizada: bool = True,
        resultado_prueba_mecha: str = ConsentimientoInformado.ResultadoPruebaMecha.APTO,
        elasticidad_cabello: str = ConsentimientoInformado.EstadoFibra.BUENA,
        porosidad_cabello: str = ConsentimientoInformado.EstadoFibra.REGULAR,
        acepta_terminos: bool = True,
        firma_digital: str = "",
        observaciones: str = "",
    ) -> ConsentimientoInformado:
        """Crea y almacena una ficha legal y técnica de consentimiento informado."""
        return ConsentimientoInformado.objects.create(
            cliente=cliente,
            cliente_nombre=cliente_nombre.strip(),
            cliente_telefono=cliente_telefono.strip(),
            cliente_dni=cliente_dni.strip(),
            tipo_procedimiento=tipo_procedimiento,
            profesional=profesional,
            ha_usado_henna_o_sales_metalicas=ha_usado_henna_o_sales_metalicas,
            tiene_alisados_o_permanentes_previos=tiene_alisados_o_permanentes_previos,
            detalle_quimicos_previos=detalle_quimicos_previos.strip(),
            tiene_decoloraciones_previas=tiene_decoloraciones_previas,
            alergias_o_sensibilidad_cuero_cabelludo=alergias_o_sensibilidad_cuero_cabelludo,
            detalle_alergias=detalle_alergias.strip(),
            embarazo_o_lactancia=embarazo_o_lactancia,
            medicacion_o_tratamiento_medico=medicacion_o_tratamiento_medico,
            prueba_mecha_realizada=prueba_mecha_realizada,
            resultado_prueba_mecha=resultado_prueba_mecha,
            elasticidad_cabello=elasticidad_cabello,
            porosidad_cabello=porosidad_cabello,
            acepta_terminos=acepta_terminos,
            firma_digital=firma_digital.strip(),
            observaciones=observaciones.strip(),
        )

    # ── Cierre Diario y Descuento Masivo de Insumos ──

    @staticmethod
    def obtener_resumen_servicios_dia(fecha: Optional[date] = None) -> List[Dict[str, Any]]:
        """
        Computa la cantidad de personas que se realizaron cada servicio en el día.
        Retorna lista de diccionarios con el conteo, recaudación y estado de descuento de stock.
        """
        dia = fecha or timezone.localdate()
        servicios_completados = ServicioRealizado.objects.filter(
            fecha=dia,
            estado=ServicioRealizado.Estado.COMPLETADO,
        )

        resumen: List[Dict[str, Any]] = []
        servicios_agrupados = (
            servicios_completados.values("servicio_id", "servicio__nombre", "servicio__categoria")
            .annotate(total_personas=Count("id"))
            .order_by("servicio__categoria", "servicio__nombre")
        )

        for grupo in servicios_agrupados:
            srv_id = grupo["servicio_id"]
            servicios_items = servicios_completados.filter(servicio_id=srv_id)
            total_recaudado = sum((s.precio_acordado for s in servicios_items), Decimal("0.00"))
            ya_descontados = all((s.insumos_descontados for s in servicios_items))

            resumen.append(
                {
                    "servicio_id": srv_id,
                    "servicio_nombre": grupo["servicio__nombre"],
                    "servicio_categoria": grupo["servicio__categoria"],
                    "total_personas": grupo["total_personas"],
                    "total_recaudado": total_recaudado,
                    "insumos_descontados": ya_descontados,
                    "items": list(servicios_items),
                }
            )

        return resumen

    @classmethod
    def descontar_insumos_cierre_dia(
        cls,
        servicio_id: int,
        fecha: date,
        insumos: List[Dict[str, Any]],
        usuario: Any = None,
    ) -> List[ConsumoInsumoCierre]:
        """
        Al terminar el día, descuenta del stock las cantidades de insumos ingresadas
        para el lote de personas que se realizaron dicho servicio.
        """
        servicio = Servicio.objects.get(pk=servicio_id)

        # Idempotencia: si ya se hizo el cierre de insumos de este servicio en
        # esta fecha, no volver a descontar (evita el doble descuento de stock
        # si se envía el formulario de cierre más de una vez).
        if ConsumoInsumoCierre.objects.filter(servicio=servicio, fecha=fecha).exists():
            raise ValueError(
                f"Los insumos del servicio '{servicio.nombre}' para el día "
                f"{fecha.strftime('%d/%m/%Y')} ya fueron descontados en un cierre anterior."
            )

        servicios_items = ServicioRealizado.objects.filter(
            fecha=fecha,
            servicio=servicio,
            estado=ServicioRealizado.Estado.COMPLETADO,
        )
        total_personas = servicios_items.count()
        consumos_registrados: List[ConsumoInsumoCierre] = []

        with transaction.atomic():
            for item in insumos:
                prod_id = item["producto_id"]
                cantidad = int(item["cantidad"])
                if cantidad <= 0:
                    continue

                # Descontar del inventario general con trazabilidad
                motivo_desc = f"Cierre del día {fecha.strftime('%d/%m/%Y')}: {total_personas}x {servicio.nombre}"
                InventarioService.descontar_stock(
                    producto_o_id=prod_id,
                    cantidad=cantidad,
                    motivo=motivo_desc,
                    usuario=usuario,
                )

                consumo = ConsumoInsumoCierre.objects.create(
                    servicio=servicio,
                    fecha=fecha,
                    producto_id=prod_id,
                    cantidad=cantidad,
                    cantidad_servicios_computados=total_personas,
                    usuario_responsable=usuario,
                )
                consumos_registrados.append(consumo)

            # Marcar servicios del día como procesados
            servicios_items.update(insumos_descontados=True)

        return consumos_registrados

    # ── Aliases camelCase ──

    @classmethod
    def cargarCatalogoInicial(cls) -> int:
        return cls.cargar_catalogo_inicial()

    @classmethod
    def crearServicio(cls, *args: Any, **kwargs: Any) -> Servicio:
        return cls.crear_servicio(*args, **kwargs)

    @classmethod
    def listarServicios(cls, *args: Any, **kwargs: Any) -> QuerySet[Servicio]:
        return cls.listar_servicios(*args, **kwargs)

    @classmethod
    def obtenerServicioPorId(cls, *args: Any, **kwargs: Any) -> Optional[Servicio]:
        return cls.obtener_servicio_por_id(*args, **kwargs)

    @classmethod
    def registrarServicioRealizado(cls, *args: Any, **kwargs: Any) -> ServicioRealizado:
        return cls.registrar_servicio_realizado(*args, **kwargs)

    @classmethod
    def listarServiciosPorFecha(cls, *args: Any, **kwargs: Any) -> QuerySet[ServicioRealizado]:
        return cls.listar_servicios_por_fecha(*args, **kwargs)

    @classmethod
    def crearConsentimiento(cls, *args: Any, **kwargs: Any) -> ConsentimientoInformado:
        return cls.crear_consentimiento(*args, **kwargs)

    @classmethod
    def obtenerResumenServiciosDia(cls, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return cls.obtener_resumen_servicios_dia(*args, **kwargs)

    @classmethod
    def descontarInsumosCierreDia(cls, *args: Any, **kwargs: Any) -> List[ConsumoInsumoCierre]:
        return cls.descontar_insumos_cierre_dia(*args, **kwargs)
