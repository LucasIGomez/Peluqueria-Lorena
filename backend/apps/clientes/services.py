"""
Peluquería Lorena — Capa de Servicios del módulo de Clientes.

Centraliza la lógica de negocio para:
- Gestión integral de clientas y fidelización (cumpleaños, WhatsApp).
- Ficha de seguimiento de tratamientos multisesión y evoluciones técnicas.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Cliente, EvolucionSesion, TratamientoProgreso


class ClienteService:
    """
    Servicio de dominio para operaciones sobre clientas y tratamientos multisesión.
    """

    # ── CRUD de Clientas ──

    @staticmethod
    def crear_cliente(
        nombre: str,
        telefono: str,
        email: Optional[str] = None,
        fecha_nacimiento: Optional[date | str] = None,
        notas_alergias: str = "",
        preferencias: str = "",
        **extra_fields: Any,
    ) -> Cliente:
        """Crea y persiste una nueva clienta en el sistema."""
        return Cliente.objects.create(
            nombre=nombre.strip(),
            telefono=telefono.strip(),
            email=email.strip() if email else None,
            fecha_nacimiento=fecha_nacimiento if fecha_nacimiento else None,
            notas_alergias=notas_alergias.strip(),
            preferencias=preferencias.strip(),
            **extra_fields,
        )

    @staticmethod
    def listar_clientes(
        busqueda: Optional[str] = None,
        solo_activos: bool = True,
    ) -> QuerySet[Cliente]:
        """Lista clientas con buscador inteligente por nombre, teléfono o email."""
        queryset = Cliente.objects.all()
        if solo_activos:
            queryset = queryset.filter(activo=True)

        if busqueda:
            q = busqueda.strip()
            queryset = queryset.filter(
                Q(nombre__icontains=q) | Q(telefono__icontains=q) | Q(email__icontains=q)
            )
        return queryset.order_by("nombre")

    @staticmethod
    def obtener_cliente_por_id(cliente_id: int) -> Optional[Cliente]:
        """Obtiene una clienta por su clave primaria."""
        try:
            return Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            return None

    @staticmethod
    def actualizar_cliente(
        cliente: Cliente,
        nombre: Optional[str] = None,
        telefono: Optional[str] = None,
        email: Optional[str] = None,
        fecha_nacimiento: Optional[date | str] = None,
        notas_alergias: Optional[str] = None,
        preferencias: Optional[str] = None,
        activo: Optional[bool] = None,
    ) -> Cliente:
        """Actualiza los datos personales o de salud de una clienta."""
        if nombre is not None:
            cliente.nombre = nombre.strip()
        if telefono is not None:
            cliente.telefono = telefono.strip()
        if email is not None:
            cliente.email = email.strip() if email else None
        if fecha_nacimiento is not None:
            cliente.fecha_nacimiento = fecha_nacimiento if fecha_nacimiento else None
        if notas_alergias is not None:
            cliente.notas_alergias = notas_alergias.strip()
        if preferencias is not None:
            cliente.preferencias = preferencias.strip()
        if activo is not None:
            cliente.activo = activo

        cliente.save()
        return cliente

    @staticmethod
    def eliminar_cliente(cliente: Cliente) -> None:
        """Baja lógica de la clienta para preservar su historial de tratamientos."""
        cliente.activo = False
        cliente.save(update_fields=["activo"])

    # ── Fidelización y Cumpleaños ──

    @staticmethod
    def obtener_cumpleaneras_del_mes(mes: Optional[int] = None) -> QuerySet[Cliente]:
        """Retorna clientas que cumplen años en el mes especificado (o el actual)."""
        if mes is None:
            mes = timezone.localdate().month
        return Cliente.objects.filter(activo=True, fecha_nacimiento__month=mes).order_by("fecha_nacimiento__day")

    @staticmethod
    def obtener_cumpleaneras_proximos_dias(dias: int = 7) -> list[Cliente]:
        """Retorna clientas que cumplen años hoy o en los próximos N días."""
        hoy = timezone.localdate()
        todos = Cliente.objects.filter(activo=True, fecha_nacimiento__isnull=False)
        cumpleaneras: list[Cliente] = []

        for c in todos:
            dias_restantes = c.dias_para_cumpleanos
            if dias_restantes is not None and 0 <= dias_restantes <= dias:
                cumpleaneras.append(c)

        cumpleaneras.sort(key=lambda x: x.dias_para_cumpleanos or 999)
        return cumpleaneras

    # ── Tratamientos Multisesión y Evolución ──

    @staticmethod
    def iniciar_tratamiento_progreso(
        cliente: Cliente,
        titulo_tratamiento: str,
        servicio_nombre: str,
        total_sesiones_estimadas: int = 1,
        notas_objetivo: str = "",
        fecha_inicio: Optional[date] = None,
    ) -> TratamientoProgreso:
        """Inicia una ficha de seguimiento para un tratamiento por etapas."""
        return TratamientoProgreso.objects.create(
            cliente=cliente,
            titulo_tratamiento=titulo_tratamiento.strip(),
            servicio_nombre=servicio_nombre.strip(),
            total_sesiones_estimadas=max(1, total_sesiones_estimadas),
            sesion_actual=1,
            notas_objetivo=notas_objetivo.strip(),
            fecha_inicio=fecha_inicio or timezone.localdate(),
        )

    @staticmethod
    def registrar_evolucion_sesion(
        tratamiento: TratamientoProgreso,
        numero_sesion: int,
        diagnostico_fibra: str,
        formula_quimica_utilizada: str,
        resultado_obtenido: str,
        tiempo_exposicion_minutos: int = 0,
        profesional: Any = None,
        proxima_cita_recomendada: Optional[date] = None,
        indicaciones_hogar: str = "",
    ) -> EvolucionSesion:
        """Registra la evolución técnica de una sesión y actualiza el avance del tratamiento."""
        sesion = EvolucionSesion.objects.create(
            tratamiento=tratamiento,
            numero_sesion=numero_sesion,
            profesional=profesional,
            diagnostico_fibra=diagnostico_fibra.strip(),
            formula_quimica_utilizada=formula_quimica_utilizada.strip(),
            tiempo_exposicion_minutos=tiempo_exposicion_minutos,
            resultado_obtenido=resultado_obtenido.strip(),
            proxima_cita_recomendada=proxima_cita_recomendada,
            indicaciones_hogar=indicaciones_hogar.strip(),
        )

        # Actualizar sesión actual del tratamiento
        if numero_sesion >= tratamiento.sesion_actual:
            tratamiento.sesion_actual = numero_sesion
            if tratamiento.sesion_actual >= tratamiento.total_sesiones_estimadas:
                tratamiento.estado = TratamientoProgreso.Estado.FINALIZADO
                tratamiento.fecha_finalizacion = timezone.localdate()
            tratamiento.save(update_fields=["sesion_actual", "estado", "fecha_finalizacion"])

        return sesion

    # ── Aliases camelCase ──

    @classmethod
    def crearCliente(cls, *args: Any, **kwargs: Any) -> Cliente:
        return cls.crear_cliente(*args, **kwargs)

    @classmethod
    def listarClientes(cls, *args: Any, **kwargs: Any) -> QuerySet[Cliente]:
        return cls.listar_clientes(*args, **kwargs)

    @classmethod
    def obtenerClientePorId(cls, *args: Any, **kwargs: Any) -> Optional[Cliente]:
        return cls.obtener_cliente_por_id(*args, **kwargs)

    @classmethod
    def actualizarCliente(cls, *args: Any, **kwargs: Any) -> Cliente:
        return cls.actualizar_cliente(*args, **kwargs)

    @classmethod
    def eliminarCliente(cls, *args: Any, **kwargs: Any) -> None:
        return cls.eliminar_cliente(*args, **kwargs)

    @classmethod
    def obtenerCumpleanerasDelMes(cls, *args: Any, **kwargs: Any) -> QuerySet[Cliente]:
        return cls.obtener_cumpleaneras_del_mes(*args, **kwargs)

    @classmethod
    def obtenerCumpleanerasProximosDias(cls, *args: Any, **kwargs: Any) -> list[Cliente]:
        return cls.obtener_cumpleaneras_proximos_dias(*args, **kwargs)

    @classmethod
    def iniciarTratamientoProgreso(cls, *args: Any, **kwargs: Any) -> TratamientoProgreso:
        return cls.iniciar_tratamiento_progreso(*args, **kwargs)

    @classmethod
    def registrarEvolucionSesion(cls, *args: Any, **kwargs: Any) -> EvolucionSesion:
        return cls.registrar_evolucion_sesion(*args, **kwargs)
