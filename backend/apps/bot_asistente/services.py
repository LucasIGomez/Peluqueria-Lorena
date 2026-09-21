"""
Peluquería Lorena — Capa de Servicios del Bot Asistente (WhatsApp).

Orquesta:
1. Modelo híbrido: Menú guiado (1 al 5) + Lenguaje libre con Gemini (Structured Outputs).
2. Validador de horario comercial de atención.
3. Agendado automático de turnos en bolsa común (profesional=None).
4. Consulta de catálogo oficial y cláusula de diagnóstico para servicios técnicos.
5. Escalado a atención humana (Lorena o Zaira).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import logging
import re
from typing import Optional

from django.utils import timezone

from apps.clientes.models import Cliente
from apps.servicios.models import Servicio
from apps.turnos.models import Turno
from apps.turnos.services import TurnoService

from .ai.interpreter import BotResponseSchema, InterpreteIA, IntencionEnum
from .handlers.business_hours import BusinessHoursValidator
from .models import ConversacionBot, MensajeBot

logger = logging.getLogger(__name__)


class TurnoBotService:
    """
    Servicio de dominio para el procesamiento de mensajes de WhatsApp
    y ejecución de acciones de agenda y catálogo.
    """

    @classmethod
    def _esta_en_horario(cls) -> bool:
        """Helper para permitir mocking en tests."""
        return BusinessHoursValidator.esta_en_horario()

    @classmethod
    def obtener_resumen_catalogo(cls) -> str:
        """Construye un resumen del tarifario vigente para contextualizar al modelo de IA."""
        servicios = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
        if not servicios.exists():
            return "Corte Damas: $15.000 (45 min), Balayage: desde $120.000 (180 min, técnico)"

        lineas = []
        for s in servicios:
            tipo = "Técnico (requiere diagnóstico previo)" if s.requiere_consentimiento else "Estándar"
            lineas.append(f"- {s.nombre}: ${s.precio_base:,.0f} ({s.duracion_estimada_minutos} min, {tipo})")
        return "\n".join(lineas)

    @classmethod
    def procesar_mensaje(
        cls,
        telefono: str = "",
        texto: str = "",
        nombre_remitente: str = "",
        *,
        telefono_cliente: str = "",
        mensaje_texto: str = "",
        nombre_cliente: str = "",
    ) -> str:
        """
        Punto de entrada principal para procesar cualquier mensaje entrante de WhatsApp.
        Soporta argumentos posicionales o por nombre (telefono / telefono_cliente).
        """
        telefono = telefono or telefono_cliente
        texto = texto or mensaje_texto
        nombre_remitente = nombre_remitente or nombre_cliente
        telefono_limpio = re.sub(r"\D", "", telefono)

        # 1. Regla de Negocio: Restricción de Horario Comercial
        if not cls._esta_en_horario():
            return BusinessHoursValidator.obtener_mensaje_fuera_de_horario()

        # 2. Recuperar o registrar la sesión de conversación
        conversacion, _ = ConversacionBot.objects.get_or_create(
            telefono_cliente=telefono_limpio,
            defaults={"nombre_remitente": nombre_remitente},
        )
        if nombre_remitente and not conversacion.nombre_remitente:
            conversacion.nombre_remitente = nombre_remitente
            conversacion.save(update_fields=["nombre_remitente"])

        # Vincular con la ficha de clienta si existe en la base de datos
        if not conversacion.cliente:
            cliente_existente = Cliente.objects.filter(
                telefono__icontains=telefono_limpio[-8:]
            ).first()
            if cliente_existente:
                conversacion.cliente = cliente_existente
                conversacion.save(update_fields=["cliente"])

        # 3. Guardar mensaje entrante para auditoría
        MensajeBot.objects.create(
            conversacion=conversacion,
            direccion=MensajeBot.Direccion.ENTRANTE,
            contenido=texto,
        )

        # 4. Si la conversación ya está escalada a atención humana
        if conversacion.requiere_humano:
            texto_lower = texto.strip().lower()
            if texto_lower in ["menu", "inicio", "volver", "reiniciar"]:
                conversacion.requiere_humano = False
                conversacion.estado = ConversacionBot.Estado.MENU
                conversacion.save(update_fields=["requiere_humano", "estado"])
            else:
                respuesta_humano = (
                    "Tu conversación ya se encuentra transferida al equipo del salón. "
                    "Lorena o Zaira te responderán en breve por acá. "
                    "(Escribí *menu* si querés volver al menú automatizado)."
                )
                cls._guardar_mensaje_saliente(conversacion, respuesta_humano, "ESCALADO_HUMANO")
                return respuesta_humano

        # 5. Evaluación del Menú Guiado Numérico
        texto_opcion = texto.strip()
        if texto_opcion in ["1", "1.", "1)"]:
            respuesta = cls._menu_agendar_turno(conversacion)
            cls._guardar_mensaje_saliente(conversacion, respuesta, "MENU_AGENDAR")
            return respuesta

        elif texto_opcion in ["2", "2.", "2)"]:
            respuesta = cls._menu_cancelar_turno(conversacion, telefono_limpio)
            cls._guardar_mensaje_saliente(conversacion, respuesta, "MENU_CANCELAR")
            return respuesta

        elif texto_opcion in ["3", "3.", "3)"]:
            respuesta = cls._menu_ver_turnos(conversacion, telefono_limpio)
            cls._guardar_mensaje_saliente(conversacion, respuesta, "MENU_VER_TURNOS")
            return respuesta

        elif texto_opcion in ["4", "4.", "4)"]:
            respuesta = cls._menu_consultar_precios()
            cls._guardar_mensaje_saliente(conversacion, respuesta, "MENU_PRECIOS")
            return respuesta

        elif texto_opcion in ["5", "5.", "5)"]:
            conversacion.requiere_humano = True
            conversacion.estado = ConversacionBot.Estado.ESCALADO_HUMANO
            conversacion.save(update_fields=["requiere_humano", "estado"])
            respuesta = (
                "¡Entendido! Ya transferí la conversación. "
                "Lorena o Zaira te van a escribir personalmente por acá en unos momentos. ¡Muchas gracias!"
            )
            cls._guardar_mensaje_saliente(conversacion, respuesta, "ESCALAR_HUMANO")
            return respuesta

        # Saludos y menú principal
        if texto_opcion.lower() in ["hola", "buenas", "buen dia", "buenas tardes", "buenas noches", "menu", "inicio", "empezar"]:
            respuesta = cls._mensaje_bienvenida_menu(nombre_remitente)
            conversacion.estado = ConversacionBot.Estado.MENU
            conversacion.save(update_fields=["estado"])
            cls._guardar_mensaje_saliente(conversacion, respuesta, "MENU_BIENVENIDA")
            return respuesta

        # 6. Lenguaje Libre: Procesamiento Inteligente con Gemini
        catalogo_resumen = cls.obtener_resumen_catalogo()
        interprete = InterpreteIA()
        schema_ia = interprete.interpretar_mensaje(texto, catalogo_resumen=catalogo_resumen)

        # Si requiere derivación humana
        if schema_ia.requiere_escalado or schema_ia.intencion == IntencionEnum.ESCALAR_HUMANO:
            conversacion.requiere_humano = True
            conversacion.estado = ConversacionBot.Estado.ESCALADO_HUMANO
            conversacion.save(update_fields=["requiere_humano", "estado"])
            cls._guardar_mensaje_saliente(conversacion, schema_ia.mensaje_respuesta, schema_ia.intencion.value, schema_ia.model_dump())
            return schema_ia.mensaje_respuesta

        # Intención: Agendar Turno
        if schema_ia.intencion == IntencionEnum.AGENDAR_TURNO:
            respuesta = cls._procesar_intencion_agendar(
                conversacion=conversacion,
                telefono=telefono_limpio,
                schema_ia=schema_ia,
                nombre_remitente=nombre_remitente,
            )
            cls._guardar_mensaje_saliente(conversacion, respuesta, schema_ia.intencion.value, schema_ia.model_dump())
            return respuesta

        # Intención: Cancelar Turno
        if schema_ia.intencion == IntencionEnum.CANCELAR_TURNO:
            respuesta = cls._menu_cancelar_turno(conversacion, telefono_limpio)
            cls._guardar_mensaje_saliente(conversacion, respuesta, schema_ia.intencion.value, schema_ia.model_dump())
            return respuesta

        # Intención: Consultar Turnos
        if schema_ia.intencion == IntencionEnum.CONSULTAR_TURNOS:
            respuesta = cls._menu_ver_turnos(conversacion, telefono_limpio)
            cls._guardar_mensaje_saliente(conversacion, respuesta, schema_ia.intencion.value, schema_ia.model_dump())
            return respuesta

        # Intención: Consultar Precios o General
        cls._guardar_mensaje_saliente(conversacion, schema_ia.mensaje_respuesta, schema_ia.intencion.value, schema_ia.model_dump())
        return schema_ia.mensaje_respuesta

    # ── Métodos Auxiliares de Negocio ──

    @classmethod
    def _guardar_mensaje_saliente(
        cls,
        conversacion: ConversacionBot,
        contenido: str,
        intencion: str = "",
        payload_ia: Optional[dict] = None,
    ) -> None:
        """Registra el mensaje saliente del bot en la base de datos."""
        MensajeBot.objects.create(
            conversacion=conversacion,
            direccion=MensajeBot.Direccion.SALIENTE,
            contenido=contenido,
            intencion=intencion,
            payload_ia=payload_ia,
        )

    @classmethod
    def _mensaje_bienvenida_menu(cls, nombre: str = "") -> str:
        saludo = f"¡Hola {nombre.strip()}! " if nombre else "¡Hola! "
        return (
            f"{saludo}Te damos la bienvenida a *Peluquería Lorena* 💇‍♀️✨\n\n"
            "¿En qué podemos ayudarte hoy?\n"
            "1️⃣ Sacar turno\n"
            "2️⃣ Cancelar turno\n"
            "3️⃣ Ver mis turnos\n"
            "4️⃣ Consultar precios\n"
            "5️⃣ Hablar con alguien\n\n"
            "_Podés responder con el número de opción o escribirnos directamente tu consulta_ (ej: _'Hola, tenés turno para corte y mechas este viernes a las 16?'_)."
        )

    @classmethod
    def _menu_agendar_turno(cls, conversacion: ConversacionBot) -> str:
        conversacion.estado = ConversacionBot.Estado.EN_PROGRESO
        conversacion.save(update_fields=["estado"])
        return (
            "¡Genial! Para agendar tu turno, contame por favor:\n"
            "1. ¿Qué servicio te gustaría realizarte? (ej: Corte, Balayage, Alisado, Nutrición)\n"
            "2. ¿Qué día y horario preferís? (Atendemos de Martes a Sábado de 09:00 a 19:00 hs)"
        )

    @classmethod
    def _menu_ver_turnos(cls, conversacion: ConversacionBot, telefono: str) -> str:
        turnos = Turno.objects.filter(
            cliente_telefono__icontains=telefono[-8:],
            fecha__gte=timezone.localdate(),
            estado__in=[Turno.Estado.CONFIRMADO, Turno.Estado.PENDIENTE],
        ).order_by("fecha", "hora")

        if not turnos.exists():
            return "No tenés turnos programados en este momento. Si querés agendar uno, escribí *1*."

        lineas = ["📅 *Tus próximos turnos en Peluquería Lorena:*"]
        for t in turnos:
            lineas.append(
                f"• {t.servicio.nombre}: el *{t.fecha.strftime('%d/%m/%Y')}* a las *{t.hora.strftime('%H:%M')} hs* "
                f"({t.get_estado_display()})"
            )
        lineas.append("\nSi necesitás modificar o cancelar alguno, respondé con *2*.")
        return "\n".join(lineas)

    @classmethod
    def _menu_cancelar_turno(cls, conversacion: ConversacionBot, telefono: str) -> str:
        turnos = Turno.objects.filter(
            cliente_telefono__icontains=telefono[-8:],
            fecha__gte=timezone.localdate(),
            estado__in=[Turno.Estado.CONFIRMADO, Turno.Estado.PENDIENTE],
        ).order_by("fecha", "hora")

        if not turnos.exists():
            return "No encontramos ningún turno activo próximo asociado a tu número para cancelar."

        if turnos.count() == 1:
            turno = turnos.first()
            turno.estado = Turno.Estado.CANCELADO
            turno.save(update_fields=["estado"])
            return f"Tu turno para *{turno.servicio.nombre}* del *{turno.fecha.strftime('%d/%m/%Y')}* a las *{turno.hora.strftime('%H:%M')} hs* fue cancelado correctamente. ¡Te esperamos cuando gustes!"

        # Si tiene varios turnos
        lineas = ["Tenés más de un turno activo. Por favor indicanos cuál querés cancelar:"]
        for t in turnos:
            lineas.append(f"• ID #{t.pk}: {t.servicio.nombre} el {t.fecha.strftime('%d/%m/%Y')} a las {t.hora.strftime('%H:%M')} hs")
        return "\n".join(lineas)

    @classmethod
    def _menu_consultar_precios(cls) -> str:
        servicios = Servicio.objects.filter(activo=True).order_by("categoria", "nombre")
        if not servicios.exists():
            return "En este momento estamos actualizando la lista de precios. Escribí *5* para consultar con Lorena."

        lineas = ["💇‍♀️ *Catálogo Oficial de Peluquería Lorena:*\n"]
        for s in servicios:
            precio_formateado = f"${s.precio_base:,.0f}".replace(",", ".")
            if s.requiere_consentimiento:
                lineas.append(f"• *{s.nombre}*: desde {precio_formateado} (Técnico)")
            else:
                lineas.append(f"• *{s.nombre}*: {precio_formateado}")

        lineas.append(
            "\n💡 *Nota importante para trabajos técnicos* (decoloraciones, mechas, alisados): "
            "los precios indicados son base. El presupuesto final se valida personalmente en el salón "
            "tras realizar un diagnóstico presencial de la fibra capilar."
        )
        return "\n".join(lineas)

    @classmethod
    def _procesar_intencion_agendar(
        cls,
        conversacion: ConversacionBot,
        telefono: str,
        schema_ia: BotResponseSchema,
        nombre_remitente: str = "",
    ) -> str:
        """
        Interpreta y materializa el agendado automático de turno en bolsa común.
        """
        # 1. Validar que tengamos fecha y hora
        if not schema_ia.fecha_sugerida or not schema_ia.hora_sugerida:
            return schema_ia.mensaje_respuesta or "Por favor, confirmame qué día y horario preferís para tu atención."

        try:
            fecha_turno = date.fromisoformat(schema_ia.fecha_sugerida)
            partes_hora = schema_ia.hora_sugerida.split(":")
            hora_turno = time(int(partes_hora[0]), int(partes_hora[1]))
        except (ValueError, IndexError):
            return "No pude interpretar con certeza la fecha u hora solicitada. ¿Podrías indicarla en formato de día y hora (ej: 'este jueves a las 16:00')?"

        # 2. Validar que la fecha del turno caiga dentro del horario comercial del salón
        dt_turno = datetime.combine(fecha_turno, hora_turno)
        if not BusinessHoursValidator.esta_en_horario(dt_turno):
            return (
                f"El horario solicitado ({fecha_turno.strftime('%d/%m/%Y')} a las {hora_turno.strftime('%H:%M')} hs) "
                "se encuentra fuera de nuestro horario comercial.\n"
                "Atendemos de *Martes a Sábado de 09:00 a 19:00 hs*. ¿Te gustaría elegir otro horario?"
            )

        # 3. Identificar el servicio
        servicio_obj = None
        if schema_ia.servicios_detectados:
            primer_servicio = schema_ia.servicios_detectados[0]
            servicio_obj = Servicio.objects.filter(
                nombre__icontains=primer_servicio, activo=True
            ).first()

        if not servicio_obj:
            # Fallback al primer servicio o genérico
            servicio_obj = Servicio.objects.filter(activo=True).first()

        if not servicio_obj:
            return "En este momento no contamos con servicios habilitados en el catálogo. Por favor comunicate con Lorena (opción 5)."

        # Calcular duración estimada
        duracion = servicio_obj.duracion_estimada_minutos

        # 4. Obtener o crear Clienta
        cliente = conversacion.cliente
        if not cliente:
            nombre_cliente = nombre_remitente or conversacion.nombre_remitente or "Clienta WhatsApp"
            cliente = Cliente.objects.filter(telefono__icontains=telefono[-8:]).first()
            if not cliente:
                cliente = Cliente.objects.create(
                    nombre=nombre_cliente,
                    telefono=telefono,
                )
            conversacion.cliente = cliente
            conversacion.save(update_fields=["cliente"])

        # 5. Crear el Turno en Bolsa Común (profesional=None)
        # La clienta no elige peluquera; se asigna internamente en el salón.
        turno = Turno.objects.create(
            cliente=cliente,
            cliente_nombre=cliente.nombre,
            cliente_telefono=telefono,
            servicio=servicio_obj,
            profesional=None,  # Bolsa común
            fecha=fecha_turno,
            hora=hora_turno,
            duracion_minutos=duracion,
            estado=Turno.Estado.CONFIRMADO,
            notas="Agendado automáticamente por Asistente Virtual WhatsApp",
        )

        aviso_tecnico = ""
        if servicio_obj.requiere_consentimiento:
            aviso_tecnico = (
                "\n\n⚠️ *Aviso:* Este servicio requiere un diagnóstico previo del cabello "
                "para validar el presupuesto definitivo y cuidar la salud capilar."
            )

        return (
            f"✅ ¡Listo, {cliente.nombre}! Tu turno para *{servicio_obj.nombre}* quedó agendado para el "
            f"*{fecha_turno.strftime('%d/%m/%Y')}* a las *{hora_turno.strftime('%H:%M')} hs*.\n"
            f"📍 Te esperamos en Peluquería Lorena."
            f"{aviso_tecnico}"
        )
