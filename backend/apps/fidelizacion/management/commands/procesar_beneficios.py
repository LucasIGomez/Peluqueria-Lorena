"""
Peluquería Lorena — Comando de automatización de Beneficios y Fidelización (RF10).

Uso diario vía Cron / tarea programada (ejemplo Linux):
    0 8 * * * /home/fabrizio/ProyectosWeb/PeluLorena/peluqueria_lorena/backend/venv/bin/python /home/fabrizio/ProyectosWeb/PeluLorena/peluqueria_lorena/backend/manage.py procesar_beneficios --settings=config.settings.local

Ejemplos:
    python manage.py procesar_beneficios
    python manage.py procesar_beneficios --solo-cumpleanos
    python manage.py procesar_beneficios --solo-regularidad --canal EMAIL
    python manage.py procesar_beneficios --dry-run
"""
from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.fidelizacion.models import MensajeBeneficio
from apps.fidelizacion.services import FidelizacionService


class Command(BaseCommand):
    help = "Revisa cumpleaños (RF 10.2) y regularidad (RF 10.3), genera cupones y dispara avisos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--solo-cumpleanos",
            action="store_true",
            help="Ejecuta únicamente la revisión de cumpleaños (RF 10.2).",
        )
        parser.add_argument(
            "--solo-regularidad",
            action="store_true",
            help="Ejecuta únicamente la evaluación de regularidad (RF 10.3).",
        )
        parser.add_argument(
            "--canal",
            type=str,
            default=MensajeBeneficio.Canal.WHATSAPP,
            choices=[c for c, _ in MensajeBeneficio.Canal.choices],
            help="Canal de aviso para los mensajes generados (defecto: WHATSAPP).",
        )
        parser.add_argument(
            "--fecha",
            type=str,
            default=None,
            help="Fecha de proceso en formato YYYY-MM-DD (defecto: hoy). Útil para reprocesos.",
        )
        parser.add_argument(
            "--regla-id",
            type=int,
            default=None,
            help="Limita el proceso a una regla específica (por PK).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula el proceso sin crear beneficios ni mensajes.",
        )

    def handle(self, *args, **options):
        if options["solo_cumpleanos"] and options["solo_regularidad"]:
            raise CommandError("Use solo una opción: --solo-cumpleanos o --solo-regularidad, no ambas.")

        hoy = self._parsear_fecha(options["fecha"])
        canal = options["canal"]
        regla_id = options["regla_id"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[SIMULACIÓN] Fecha de proceso: {hoy.isoformat()}"))
            self._simular(hoy, options, canal, regla_id)
            return

        solo_cumple = options["solo_cumpleanos"]
        solo_regul = options["solo_regularidad"]

        if solo_cumple:
            vencidos = FidelizacionService.marcar_vencidos(hoy=hoy)
            resultado = FidelizacionService.procesar_cumpleanos(hoy=hoy, canal=canal, regla_id=regla_id)
            self._informar_cumpleanos(resultado, vencidos)
        elif solo_regul:
            vencidos = FidelizacionService.marcar_vencidos(hoy=hoy)
            resultado = FidelizacionService.procesar_regularidad(hoy=hoy, canal=canal, regla_id=regla_id)
            self._informar_regularidad(resultado, vencidos)
        else:
            resumen = FidelizacionService.procesar_todo(hoy=hoy, canal=canal) if regla_id is None else self._procesar_con_regla(hoy, canal, regla_id)
            self._informar_todo(resumen)

    # ── Auxiliares ──

    def _parsear_fecha(self, valor: str | None) -> date:
        if not valor:
            from django.utils import timezone
            return timezone.localdate()
        try:
            return date.fromisoformat(valor)
        except ValueError as exc:
            raise CommandError(f"Fecha inválida '{valor}'. Use formato YYYY-MM-DD.") from exc

    def _procesar_con_regla(self, hoy: date, canal: str, regla_id: int) -> dict:
        from apps.fidelizacion.models import ReglaBeneficio
        try:
            regla = ReglaBeneficio.objects.get(pk=regla_id)
        except ReglaBeneficio.DoesNotExist as exc:
            raise CommandError(f"No existe la regla #{regla_id}.") from exc
        vencidos = FidelizacionService.marcar_vencidos(hoy=hoy)
        if regla.tipo == ReglaBeneficio.Tipo.CUMPLEANOS:
            cumple = FidelizacionService.procesar_cumpleanos(hoy=hoy, canal=canal, regla_id=regla_id)
            regul = {"reglas_evaluadas": 0, "clientas_evaluadas": 0, "otorgados": []}
        else:
            cumple = {"reglas_evaluadas": 0, "otorgados": [], "omitidos_duplicados": 0}
            regul = FidelizacionService.procesar_regularidad(hoy=hoy, canal=canal, regla_id=regla_id)
        return {
            "fecha": hoy.isoformat(),
            "vencidos": vencidos,
            "cumpleanos": cumple,
            "regularidad": regul,
            "total_otorgados": len(cumple["otorgados"]) + len(regul["otorgados"]),
        }

    def _informar_cumpleanos(self, resultado: dict, vencidos: int) -> None:
        self.stdout.write(self.style.SUCCESS(
            f"Cumpleaños: {len(resultado['otorgados'])} otorgados, "
            f"{resultado['omitidos_duplicados']} omitidos (ya enviados este año), "
            f"{vencidos} vencidos marcados."
        ))
        for b in resultado["otorgados"]:
            self.stdout.write(f"  + {b.codigo} → {b.cliente.nombre} (vence {b.fecha_vencimiento})")

    def _informar_regularidad(self, resultado: dict, vencidos: int) -> None:
        self.stdout.write(self.style.SUCCESS(
            f"Regularidad: {len(resultado['otorgados'])} otorgados sobre "
            f"{resultado['clientas_evaluadas']} evaluaciones, {vencidos} vencidos marcados."
        ))
        for b in resultado["otorgados"]:
            self.stdout.write(
                f"  + {b.codigo} → {b.cliente.nombre} "
                f"({b.visitas_contadas} visitas, ${b.monto_acumulado:,.2f})"
            )

    def _informar_todo(self, resumen: dict) -> None:
        self.stdout.write(self.style.SUCCESS(
            f"[{resumen['fecha']}] Proceso integral: {resumen['total_otorgados']} beneficios otorgados, "
            f"{resumen['vencidos']} vencidos marcados."
        ))
        self._informar_cumpleanos(resumen["cumpleanos"], vencidos=0)
        self._informar_regularidad(resumen["regularidad"], vencidos=0)

    def _simular(self, hoy: date, options: dict, canal: str, regla_id) -> None:
        """Informa qué haría el proceso sin escribir en la base."""
        from apps.fidelizacion.models import ReglaBeneficio
        reglas = ReglaBeneficio.objects.filter(activo=True)
        if regla_id:
            reglas = reglas.filter(pk=regla_id)
        if options["solo_regularidad"]:
            reglas = reglas.filter(tipo=ReglaBeneficio.Tipo.REGULARIDAD)
        if options["solo_cumpleanos"]:
            reglas = reglas.filter(tipo=ReglaBeneficio.Tipo.CUMPLEANOS)
        self.stdout.write(f"Reglas activas alcanzadas: {reglas.count()} (canal: {canal}).")
        for regla in reglas:
            if regla.tipo == ReglaBeneficio.Tipo.CUMPLEANOS:
                candidatas = FidelizacionService.clientas_cumpleanos_en_ventana(regla.ventana_dias, hoy=hoy)
                self.stdout.write(f"  - [{regla.pk}] {regla.nombre}: {len(candidatas)} cumpleañeras en ventana de {regla.ventana_dias} días.")
            else:
                fecha_desde, _ = FidelizacionService._rango_regularidad(regla, hoy)
                desde_txt = fecha_desde.isoformat() if fecha_desde else "historial total"
                self.stdout.write(
                    f"  - [{regla.pk}] {regla.nombre}: umbral {regla.min_visitas} visitas o "
                    f"${regla.min_monto:,.2f} desde {desde_txt}."
                )
        self.stdout.write(self.style.WARNING("Simulación completa: no se creó ningún registro."))
