# Generada manualmente para RF10 (entorno de verificación limitado en cliente Windows).
# Regenerar/verificar en el host con:
#   python manage.py makemigrations fidelizacion --settings=config.settings.local
#   python manage.py migrate --settings=config.settings.local

import decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("clientes", "0001_initial"),
        ("servicios", "0003_comisiones_serviciorealizado"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReglaBeneficio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(help_text='Ej: Cumpleaños 15% OFF, Clienta fiel 3 visitas.', max_length=150, verbose_name='nombre de la regla')),
                ('tipo', models.CharField(choices=[('CUMPLEANOS', 'Beneficio de Cumpleaños'), ('REGULARIDAD', 'Beneficio por Regularidad')], db_index=True, default='CUMPLEANOS', max_length=20, verbose_name='tipo de beneficio')),
                ('descripcion', models.CharField(blank=True, max_length=250, verbose_name='descripción / notas internas')),
                ('activo', models.BooleanField(db_index=True, default=True, verbose_name='regla activa')),
                ('min_visitas', models.PositiveIntegerField(default=3, help_text='Cantidad mínima de visitas completadas para disparar el beneficio. Solo aplica a REGULARIDAD.', verbose_name='mínimo de visitas (turnos/atenciones completadas)')),
                ('min_monto', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), help_text='Alternativa o complemento a visitas: monto acumulado mínimo. 0 = no se exige monto.', max_digits=12, verbose_name='monto total mínimo consumido ($)')),
                ('periodo_dias', models.PositiveIntegerField(default=30, help_text='Ventana móvil de análisis. Ej: 30 = últimos 30 días. 0 = todo el historial de la clienta.', verbose_name='período de evaluación (días hacia atrás)')),
                ('ventana_dias', models.PositiveIntegerField(default=5, help_text='Con cuántos días de anticipación se otorga el beneficio de cumpleaños. Solo aplica a CUMPLEAÑOS.', verbose_name='ventana de aviso previo (días)')),
                ('tipo_recompensa', models.CharField(choices=[('PORCENTAJE', 'Porcentaje de descuento (%)'), ('MONTO_FIJO', 'Monto fijo de descuento ($)'), ('SERVICIO', 'Servicio bonificado (sin cargo)')], default='PORCENTAJE', max_length=20, verbose_name='tipo de recompensa')),
                ('valor', models.DecimalField(decimal_places=2, default=decimal.Decimal('10.00'), help_text='Si es PORCENTAJE: 0–100. Si es MONTO_FIJO: pesos $. Si es SERVICIO: se ignora y se usa el servicio bonificado.', max_digits=12, verbose_name='valor de la recompensa')),
                ('servicio_bonificado', models.ForeignKey(blank=True, help_text='Solo cuando la recompensa es SERVICIO bonificado.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reglas_bonificacion', to='servicios.servicio', verbose_name='servicio bonificado')),
                ('plantilla_mensaje', models.TextField(default='Hola {nombre_cliente}, ¡Peluquería Lorena te saluda! Tenés un beneficio de {descuento} con el código {codigo}, válido hasta el {fecha_limite}. ¡Te esperamos!', help_text='Variables disponibles: {nombre_cliente}, {descuento}, {codigo}, {fecha_limite}.', verbose_name='plantilla de mensaje personalizada')),
                ('dias_validez', models.PositiveIntegerField(default=7, help_text='Cuántos días permanece DISPONIBLE el beneficio desde su otorgamiento.', verbose_name='vigencia del cupón (días)')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='fecha de creación')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True, verbose_name='última actualización')),
            ],
            options={
                'verbose_name': 'regla de beneficio',
                'verbose_name_plural': 'reglas de beneficios',
                'ordering': ['tipo', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='BeneficioOtorgado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('CUMPLEANOS', 'Beneficio de Cumpleaños'), ('REGULARIDAD', 'Beneficio por Regularidad')], db_index=True, max_length=20, verbose_name='tipo de beneficio (foto al otorgar)')),
                ('codigo', models.CharField(db_index=True, help_text='Código único para canje en caja (ej: CUM-A1B2C3).', max_length=20, unique=True, verbose_name='código de cupón')),
                ('descripcion_beneficio', models.CharField(help_text='Foto del beneficio al momento del otorgamiento (ej: 15,00% OFF).', max_length=250, verbose_name='detalle de la recompensa otorgada')),
                ('tipo_recompensa', models.CharField(choices=[('PORCENTAJE', 'Porcentaje de descuento (%)'), ('MONTO_FIJO', 'Monto fijo de descuento ($)'), ('SERVICIO', 'Servicio bonificado (sin cargo)')], default='PORCENTAJE', max_length=20, verbose_name='tipo de recompensa (foto)')),
                ('valor', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=12, verbose_name='valor otorgado (foto)')),
                ('mensaje_renderizado', models.TextField(blank=True, help_text='Texto final con variables ya reemplazadas.', verbose_name='mensaje personalizado enviado')),
                ('estado', models.CharField(choices=[('DISPONIBLE', 'Disponible'), ('CANJEADO', 'Canjeado'), ('VENCIDO', 'Vencido')], db_index=True, default='DISPONIBLE', max_length=20, verbose_name='estado del beneficio')),
                ('ciclo_referencia', models.CharField(db_index=True, help_text='Para CUMPLEAÑOS: año (ej: 2026). Para REGULARIDAD: período evaluado.', max_length=20, verbose_name='ciclo de referencia (anti-duplicados)')),
                ('visitas_contadas', models.PositiveIntegerField(default=0, verbose_name='visitas contabilizadas')),
                ('monto_acumulado', models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=12, verbose_name='monto acumulado evaluado ($)')),
                ('fecha_otorgamiento', models.DateTimeField(auto_now_add=True, verbose_name='fecha de asignación')),
                ('fecha_vencimiento', models.DateField(db_index=True, verbose_name='fecha de expiración')),
                ('fecha_canje', models.DateTimeField(blank=True, null=True, verbose_name='fecha de canje')),
                ('observaciones', models.TextField(blank=True, verbose_name='observaciones de canje')),
                ('canjeado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='beneficios_canjeados', to=settings.AUTH_USER_MODEL, verbose_name='canjeado por (profesional)')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='beneficios', to='clientes.cliente', verbose_name='clienta beneficiaria')),
                ('regla', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='beneficios_otorgados', to='fidelizacion.reglabeneficio', verbose_name='regla aplicada')),
            ],
            options={
                'verbose_name': 'beneficio otorgado',
                'verbose_name_plural': 'beneficios otorgados',
                'ordering': ['-fecha_otorgamiento'],
                'constraints': [models.UniqueConstraint(fields=('cliente', 'regla', 'ciclo_referencia'), name='unico_beneficio_por_ciclo')],
            },
        ),
        migrations.CreateModel(
            name='MensajeBeneficio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canal', models.CharField(choices=[('WHATSAPP', 'WhatsApp'), ('EMAIL', 'Email'), ('MANUAL', 'Aviso manual en salón')], default='WHATSAPP', max_length=20, verbose_name='canal de aviso')),
                ('destinatario', models.CharField(blank=True, max_length=200, verbose_name='destinatario (teléfono o email)')),
                ('contenido', models.TextField(verbose_name='contenido del mensaje')),
                ('estado_envio', models.CharField(choices=[('PENDIENTE', 'Pendiente de envío'), ('ENVIADO', 'Enviado / Simulado'), ('FALLIDO', 'Fallido')], db_index=True, default='PENDIENTE', max_length=20, verbose_name='estado del envío')),
                ('detalle_error', models.TextField(blank=True, verbose_name='detalle del error')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='fecha de registro')),
                ('fecha_envio', models.DateTimeField(blank=True, null=True, verbose_name='fecha de envío')),
                ('beneficio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mensajes', to='fidelizacion.beneficiootorgado', verbose_name='beneficio avisado')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mensajes_beneficios', to='clientes.cliente', verbose_name='clienta destinataria')),
            ],
            options={
                'verbose_name': 'mensaje de beneficio',
                'verbose_name_plural': 'historial de mensajes de beneficios',
                'ordering': ['-fecha_creacion'],
            },
        ),
    ]
