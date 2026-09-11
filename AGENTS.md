# AGENTS.md — Peluquería Lorena

## Idioma y Comunicación
- Responder, explicar y documentar siempre en **español**.
- Mensajes de commit, nombres de migraciones, docstrings y comentarios de código en español.

## Entorno y Quirks Operativos
- **Ubicación de trabajo:** Unidad montada de red (`Z:\peluqueria_lorena`).
- **Rendimiento I/O:** Prohibido realizar búsquedas ciegas recursivas o comandos pesados en todo el árbol de archivos. Usar siempre referencias quirúrgicas (`@backend/...` o `@frontend/...`) para evitar congelamientos por latencia de red.
- **Entorno virtual:** Usar los intérpretes dedicados en `backend\.venv-win\Scripts\python.exe` o `backend\venv\Scripts\python.exe`. No ejecutar `python` o `pip` globales del sistema.
- **Archivos ignorados:** Respetar estrictamente `.gitignore` (`.venv*/`, `__pycache__/`, `db.sqlite3`, `*.pyc`, temporales).

## Ordenador de Hosteo y Seguridad de Infraestructura
- **Ubicación del Host:** El proyecto reside físicamente en una computadora marca Lenovo YOGA con sistema operativo **Linux Mint**.
- **Acceso Remoto:** Es accedida desde esta computadora cliente (**Windows 11**) a través de una unidad de red montada (`Z:`) conectada mediante una IP privada de **Tailscale (`100.82.23.52`)**.
- **Servicio Systemd de Backend:** `backend.pelulorena.service` en Linux Mint (ejecuta `/home/fabrizio/ProyectosWeb/PeluLorena/peluqueria_lorena/backend/venv/bin/python manage.py runserver`).
  - Reinicio tras cambios estructurales o migraciones: `sudo systemctl restart backend.pelulorena.service`
  - Estado del servicio: `systemctl status backend.pelulorena.service`
- **Restricciones de Comandos:**
  - Está **estrictamente prohibido** ejecutar cualquier comando que pueda apagar, suspender, reiniciar, hibernar o alterar la conectividad de red de la computadora de hosteo (`shutdown`, `reboot`, `systemctl stop tailscaled`, etc.).
  - No se debe ejecutar ningún comando que impacte a nivel del sistema operativo en la computadora cliente que emite los prompts (Windows 11).
  - Cualquier comando de consola debe limitarse pura y exclusivamente al entorno del proyecto (`backend/` o scripts de desarrollo locales).

## Stack Técnico y Arquitectura
- **Backend:** Python (3.11/3.12+) con **Django 5.1** y **Django REST Framework (DRF 3.15+)**.
  - Settings modularizados en `backend/config/settings/` (`base.py`, `local.py`).
  - Entorno de desarrollo por defecto: `DJANGO_SETTINGS_MODULE=config.settings.local`.
- **Base de Datos:** SQLite local (`db.sqlite3`) y PostgreSQL previsto para producción (`psycopg2-binary`).
- **Autenticación:** Sesiones Django (SSR) + JWT (`djangorestframework-simplejwt`) para `/api/v1/`.
  - Roles RBAC: modelo personalizado `Usuario` (`backend/apps/usuarios/models.py`) con Proxy Models (`Administradora`, `Empleada`).
- **Frontend:** Server-Side Rendering con **Django Templates** (`frontend/base.html`), **Bootstrap 5.3.3** (modo oscuro `data-bs-theme="dark"` con acentos dorados), **Bootstrap Icons** y **Vanilla JS (ES6+)**. No introducir frameworks pesados (React/Vue/Angular).
- **Módulos Core (`backend/apps/`):**
  - `usuarios`: Autenticación, roles y registro administrativo protegido por PIN.
  - `clientes`: Fichas, historial capilar, alergias y evolución química.
  - `servicios`: Catálogo, precios, registro diario de trabajos y consentimiento informado.
  - `inventario`: Stock de insumos/reventa, alertas críticas y movimientos.
  - `proveedores`: Directorio y órdenes de compra.
  - `turnos`, `pagos`, `notificaciones`, `bot_asistente`: Automatizaciones y pasarelas.

## Comandos Clave de Desarrollo
Ejecutar siempre dentro del directorio `backend/`:
- **Servidor local:**
  `python manage.py runserver --settings=config.settings.local`
- **Migraciones:**
  `python manage.py makemigrations --settings=config.settings.local`
  `python manage.py migrate --settings=config.settings.local`

## Reglas de Modificación de Código
1. **Ediciones quirúrgicas:** No reescribir vistas o modelos enteros si solo se añade un método o campo.
2. **Seguridad y Secretos:** Jamás hardcodear credenciales, API keys o PINs; usar `python-decouple` (`config(...)`).
3. **ORM & Migraciones:** No modificar archivos de migración ya aplicados; generar siempre una nueva migración con `makemigrations`.
4. **Formularios y Vistas:** Mantener validaciones de negocio en forms/serializers o modelos, no acumular lógica en plantillas HTML.