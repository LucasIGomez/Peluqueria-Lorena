"""
Peluquería Lorena — Capa de servicios del módulo de Beneficios y Fidelización (RF10).

Aísla la lógica de evaluación y cálculo en funciones puras y transaccionales:
- Detección de cumpleaños en ventana configurable (RF 10.2), idempotente por año.
- Evaluación de regularidad por visitas/monto en ventana móvil (RF 10.3).
- Render de plantillas con variables {nombre_cliente}, {descuento}, {codigo}, {fecha_limite}.
- Adaptador de mensajería mock (WhatsApp/Email) extensible con logger.

Fuentes de actividad consideradas "visita completada" (en orden de prioridad):
1. Turnos en estado COMPLETADO vinculados a la clienta.
2. Servicios realizados (ServicioRealizado COMPLETADO) vinculados a la clienta.
3. Cobros no anulados vinculados a la clienta (monto acumulado).
"""
from __future__ import annotations

import logging
import secrets
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.db.models import Count, QuerySet, Sum
from django.utils import timezone

from apps.clientes.models import Cliente
from .models import BeneficioOtorgado, MensajeBeneficio, ReglaBeneficio

logger = logging.getLogger("fidelizacion")


# ──────────────────────────────────────────────────────────────
# Utilidades puras
# ──────────────────────────────────────────────────────────────

def generar_codigo_beneficio(prefijo: str = "FID") -> str:
    """Genera un código de cupón único legible (ej: CUM-A1B2C3)."""
    sufijo = secrets.token_hex(3).upper()
    return f"{prefijo}-{sufijo}"


def renderizar_plantilla(plantilla: str, contexto: dict[str, Any]) -> str:
    """
    Reemplaza variables {nombre_cliente}, {descuento}, {codigo}, {fecha_limite}.

    Las variables ausentes se dejan intactas en lugar de romper el mensaje.
    """
    texto = plantilla or ""
    for clave, valor in (contexto or {}).items():
        texto = texto.replace("{" + str(clave) + "}", str(valor))
    return texto


# ──────────────────────────────────────────────────────────────
# Adaptador de mensajería (mock extensible)
# ──────────────────────────────────────────────────────────────

class CanalBase:
    """Interfaz de canal de aviso. Implementar `despachar` para integrar proveedor real."""

    codigo = "BASE"

    def despachar(self, mensaje: MensajeBeneficio) -> bool:
        raise NotImplementedError


class CanalWhatsappMock(CanalBase):
    """Simula el envío por WhatsApp: registra en log y marca ENVIADO."""

    codigo = "WHATSAPP"

    def despachar(self, mensaje: MensajeBeneficio) -> bool:
        logger.info(
            "[WhatsApp mock] Para %s (%s): %s",
            mensaje.cliente.nombre,
            mensaje.destinatario,
            mensaje.contenido,
        )
        return True


class CanalEmailMock(CanalBase):
    """Simula el envío por Email: registra en log y marca ENVIADO."""

    codigo = "EMAIL"

    def despachar(self, mensaje: MensajeBeneficio) -> bool:
        logger.info(
            "[Email mock] Para %s (%s): %s",
            mensaje.cliente.nombre,
            mensaje.destinatario,
            mensaje.contenido,
        )
        return True


class CanalManual(CanalBase):
    """Aviso presencial en salón: siempre queda registrado como ENVIADO."""

    codigo = "MANUAL"

    def despachar(self, mensaje: MensajeBeneficio) -> bool:
        logger.info("[Manual] Aviso en salón a %s: %s", mensaje.cliente.nombre, mensaje.contenido)
        return True


CANALES: dict[str, CanalBase] = {
    MensajeBeneficio.Canal.WHATSAPP: CanalWhatsappMock(),
    MensajeBeneficio.Canal.EMAIL: CanalEmailMock(),
    MensajeBeneficio.Canal.MANUAL: CanalManual(),
}


class MensajeriaService:
    """Crea el registro de mensaje y simula su despacho por el canal elegido."""

    @staticmethod
    def destinatario_por_canal(cliente: Cliente, canal: str) -> str:
        if canal == MensajeBeneficio.Canal.EMAIL:
            return (cliente.email or "").strip()
        if canal == MensajeBeneficio.Canal.WHATSAPP:
            return (cliente.telefono or "").strip()
        return (cliente.telefono or cliente.email or "").strip()

    @classmethod
    def avisar_beneficio(
        cls,
        beneficio: BeneficioOtorgado,
        canal: str = MensajeBeneficio.Canal.WHATSAPP,
    ) -> MensajeBeneficio:
        """Registra el mensaje y lo despacha vía el adaptador correspondiente."""
        cliente = beneficio.cliente
        mensaje = MensajeBeneficio.objects.create(
            beneficio=beneficio,
            cliente=cliente,
            canal=canal,
            destinatario=cls.destinatario_por_canal(cliente, canal),
            contenido=beneficio.mensaje_renderizado,
            estado_envio=MensajeBeneficio.EstadoEnvio.PENDIENTE,
        )
        adaptador = CANALES.get(canal, CanalWhatsappMock())
        try:
            exito = adaptador.despachar(mensaje)
        except Exception as exc:  # noqa: BLE001 — el mock nunca debe romper el cron
            logger.exception("Fallo al despachar mensaje %s: %s", mensaje.pk, exc)
            mensaje.estado_envio = MensajeBeneficio.EstadoEnvio.FALLIDO
            mensaje.detalle_error = str(exc)[:500]
            mensaje.save(update_fields=["estado_envio", "detalle_error"])
            return mensaje
        mensaje.estado_envio = (
            MensajeBeneficio.EstadoEnvio.ENVIADO if exito else MensajeBeneficio.EstadoEnvio.FALLIDO
        )
        mensaje.fecha_envio = timezone.now()
        mensaje.save(update_fields=["estado_envio", "fecha_envio"])
        return mensaje


# ──────────────────────────────────────────────────────────────
# Servicio de dominio: fidelización
# ──────────────────────────────────────────────────────────────

class FidelizacionService:
    """Evaluación de cumpleaños y regularidad con transacciones atómicas."""

    # ── Consultas de actividad ──

    @staticmethod
    def _rango_regularidad(regla: ReglaBeneficio, hoy: date) -> tuple[Optional[date], date]:
        """Retorna (fecha_desde, fecha_hasta) según la ventana de la regla."""
        if not regla.periodo_dias:
            return None, hoy
        return hoy - timedelta(days=regla.periodo_dias), hoy

    @classmethod
    def contar_actividad_cliente(
        cls,
        cliente: Cliente,
        fecha_desde: Optional[date],
        fecha_hasta: date,
    ) -> tuple[int, Decimal]:
        """
        Cuenta visitas completadas y monto acumulado de la clienta en el rango.

        Visitas = turnos COMPLETADOS + servicios COMPLETADOS (evita doble conteo
        cuando el turno ya generó su atención: si el turno tiene servicio_realizado,
        solo cuenta una vez). Monto = cobros no anulados del período.
        """
        # Importación diferida para evitar ciclos entre apps.
        from apps.pagos.models import Cobro
        from apps.servicios.models import ServicioRealizado
        from apps.turnos.models import Turno

        turnos_qs = Turno.objects.filter(cliente=cliente, estado=Turno.Estado.COMPLETADO)
        servicios_qs = ServicioRealizado.objects.filter(
            cliente=cliente, estado=ServicioRealizado.Estado.COMPLETADO
        )
        cobros_qs = Cobro.objects.filter(cliente=cliente, anulado=False)
        if fecha_desde:
            turnos_qs = turnos_qs.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta)
            servicios_qs = servicios_qs.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta)
            cobros_qs = cobros_qs.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta)

        turnos_con_atencion = set(
            turnos_qs.exclude(servicio_realizado__isnull=True).values_list(
                "servicio_realizado_id", flat=True
            )
        )
        visitas_turnos = turnos_qs.count()
        visitas_servicios = servicios_qs.exclude(pk__in=turnos_con_atencion).count() if turnos_con_atencion else servicios_qs.count()
        visitas = visitas_turnos + visitas_servicios

        monto_servicios = servicios_qs.aggregate(total=Sum("precio_acordado"))["total"] or Decimal("0.00")
        monto_cobros = cobros_qs.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
        # Si hay cobros registrados, son la fuente de verdad del dinero; si no,
        # se usa el precio pactado de las atenciones como aproximación.
        monto = monto_cobros if cobros_qs.exists() else monto_servicios
        return visitas, Decimal(monto)

    @staticmethod
    def clientas_cumpleanos_en_ventana(ventana_dias: int, hoy: Optional[date] = None) -> list[Cliente]:
        """Lista clientas activas con cumpleaños dentro de los próximos N días."""
        hoy = hoy or timezone.localdate()
        candidatas = Cliente.objects.filter(activo=True, fecha_nacimiento__isnull=False)
        resultado: list[Cliente] = []
        for clienta in candidatas:
            dias = clienta.dias_para_cumpleanos
            if dias is not None and 0 <= dias <= ventana_dias:
                resultado.append(clienta)
        resultado.sort(key=lambda c: c.dias_para_cumpleanos or 999)
        return resultado

    # ── Creación de beneficios (idempotente) ──

    @classmethod
    @transaction.atomic
    def otorgar_beneficio(
        cls,
        cliente: Cliente,
        regla: ReglaBeneficio,
        ciclo_referencia: str,
        visitas: int = 0,
        monto: Decimal = Decimal("0.00"),
        hoy: Optional[date] = None,
        canal: str = MensajeBeneficio.Canal.WHATSAPP,
    ) -> tuple[BeneficioOtorgado, bool]:
        """
        Otorga el beneficio si no existe ya para (cliente, regla, ciclo).

        Retorna (beneficio, creado). Si ya existía, retorna el existente con creado=False.
        """
        hoy = hoy or timezone.localdate()
        if not regla.dias_validez or regla.dias_validez < 1:
            raise ValueError(
                f"La regla '{regla.nombre}' tiene vigencia de {regla.dias_validez} días; "
                "debe ser de al menos 1 día para otorgar cupones."
            )
        existente = BeneficioOtorgado.objects.filter(
            cliente=cliente, regla=regla, ciclo_referencia=ciclo_referencia
        ).first()
        if existente:
            return existente, False

        prefijo = "CUM" if regla.tipo == ReglaBeneficio.Tipo.CUMPLEANOS else "FID"
        codigo = generar_codigo_beneficio(prefijo)
        # Garantizar unicidad del código ante colisión aleatoria.
        while BeneficioOtorgado.objects.filter(codigo=codigo).exists():
            codigo = generar_codigo_beneficio(prefijo)

        vencimiento = hoy + timedelta(days=regla.dias_validez)
        contexto = {
            "nombre_cliente": cliente.nombre.split(" ")[0] if cliente.nombre else "clienta",
            "descuento": regla.descripcion_recompensa,
            "codigo": codigo,
            "fecha_limite": vencimiento.strftime("%d/%m/%Y"),
        }
        beneficio = BeneficioOtorgado.objects.create(
            cliente=cliente,
            regla=regla,
            tipo=regla.tipo,
            codigo=codigo,
            descripcion_beneficio=regla.descripcion_recompensa,
            tipo_recompensa=regla.tipo_recompensa,
            valor=regla.valor,
            mensaje_renderizado=renderizar_plantilla(regla.plantilla_mensaje, contexto),
            estado=BeneficioOtorgado.Estado.DISPONIBLE,
            ciclo_referencia=ciclo_referencia,
            visitas_contadas=visitas,
            monto_acumulado=monto,
            fecha_vencimiento=vencimiento,
        )
        MensajeriaService.avisar_beneficio(beneficio, canal=canal)
        logger.info("Beneficio %s otorgado a %s por regla %s.", codigo, cliente.nombre, regla.nombre)
        return beneficio, True

    # ── RF 10.2: Cumpleaños ──

    @classmethod
    def procesar_cumpleanos(
        cls,
        hoy: Optional[date] = None,
        canal: str = MensajeBeneficio.Canal.WHATSAPP,
        regla_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Revisa cumpleaños del día/ventana y otorga beneficios una vez por año."""
        hoy = hoy or timezone.localdate()
        reglas = ReglaBeneficio.objects.filter(tipo=ReglaBeneficio.Tipo.CUMPLEANOS, activo=True)
        if regla_id:
            reglas = reglas.filter(pk=regla_id)
        otorgados: list[BeneficioOtorgado] = []
        omitidos = 0
        for regla in reglas:
            for clienta in cls.clientas_cumpleanos_en_ventana(regla.ventana_dias, hoy=hoy):
                ciclo = str(hoy.year)  # un solo envío anual por clienta y regla
                _, creado = cls.otorgar_beneficio(
                    cliente=clienta, regla=regla, ciclo_referencia=ciclo, hoy=hoy, canal=canal
                )
                if creado:
                    otorgados.append(_)
                else:
                    omitidos += 1
        return {"reglas_evaluadas": reglas.count(), "otorgados": otorgados, "omitidos_duplicados": omitidos}

    # ── RF 10.3: Regularidad ──

    @staticmethod
    def _ciclo_regularidad(regla: ReglaBeneficio, hoy: date) -> str:
        """Ciclo anti-duplicado: mensual si hay ventana, anual si es historial total."""
        if regla.periodo_dias:
            return f"{hoy.year}-{hoy.month:02d}-R{regla.pk}"
        return f"{hoy.year}-HIST-R{regla.pk}"

    @classmethod
    def cumple_umbral_regularidad(
        cls, visitas: int, monto: Decimal, regla: ReglaBeneficio
    ) -> bool:
        """Evalúa si la actividad alcanza el umbral (visitas O monto)."""
        if regla.min_visitas and visitas >= regla.min_visitas:
            return True
        if regla.min_monto and regla.min_monto > Decimal("0.00") and monto >= regla.min_monto:
            return True
        return False

    @classmethod
    def procesar_regularidad(
        cls,
        hoy: Optional[date] = None,
        canal: str = MensajeBeneficio.Canal.WHATSAPP,
        regla_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Evalúa clientas activas frente a las reglas de regularidad vigentes."""
        hoy = hoy or timezone.localdate()
        reglas = ReglaBeneficio.objects.filter(tipo=ReglaBeneficio.Tipo.REGULARIDAD, activo=True)
        if regla_id:
            reglas = reglas.filter(pk=regla_id)
        otorgados: list[BeneficioOtorgado] = []
        evaluadas = 0
        for regla in reglas:
            fecha_desde, fecha_hasta = cls._rango_regularidad(regla, hoy)
            ciclo = cls._ciclo_regularidad(regla, hoy)
            for clienta in Cliente.objects.filter(activo=True):
                evaluadas += 1
                visitas, monto = cls.contar_actividad_cliente(clienta, fecha_desde, fecha_hasta)
                if not cls.cumple_umbral_regularidad(visitas, monto, regla):
                    continue
                # Anti-spam: si ya tiene un cupón DISPONIBLE de la misma regla, no duplicar.
                if BeneficioOtorgado.objects.filter(
                    cliente=clienta, regla=regla, estado=BeneficioOtorgado.Estado.DISPONIBLE
                ).exists():
                    continue
                beneficio, creado = cls.otorgar_beneficio(
                    cliente=clienta,
                    regla=regla,
                    ciclo_referencia=ciclo,
                    visitas=visitas,
                    monto=monto,
                    hoy=hoy,
                    canal=canal,
                )
                if creado:
                    otorgados.append(beneficio)
        return {"reglas_evaluadas": reglas.count(), "clientas_evaluadas": evaluadas, "otorgados": otorgados}

    # ── Proceso integral + mantenimiento ──

    @classmethod
    def marcar_vencidos(cls, hoy: Optional[date] = None) -> int:
        """Marca como VENCIDO todo cupón DISPONIBLE cuya fecha ya pasó."""
        hoy = hoy or timezone.localdate()
        return BeneficioOtorgado.objects.filter(
            estado=BeneficioOtorgado.Estado.DISPONIBLE, fecha_vencimiento__lt=hoy
        ).update(estado=BeneficioOtorgado.Estado.VENCIDO)

    @classmethod
    @transaction.atomic
    def procesar_todo(
        cls,
        hoy: Optional[date] = None,
        canal: str = MensajeBeneficio.Canal.WHATSAPP,
    ) -> dict[str, Any]:
        """Ejecuta el ciclo completo: vencimientos, cumpleaños y regularidad."""
        hoy = hoy or timezone.localdate()
        vencidos = cls.marcar_vencidos(hoy=hoy)
        cumple = cls.procesar_cumpleanos(hoy=hoy, canal=canal)
        regul = cls.procesar_regularidad(hoy=hoy, canal=canal)
        return {
            "fecha": hoy.isoformat(),
            "vencidos": vencidos,
            "cumpleanos": cumple,
            "regularidad": regul,
            "total_otorgados": len(cumple["otorgados"]) + len(regul["otorgados"]),
        }

    # ── Aliases camelCase ──
    @classmethod
    def procesarTodo(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return cls.procesar_todo(*args, **kwargs)
