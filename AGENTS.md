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
- **Entorno Local (Desarrollo / Hosteo Actual):** Computadora Lenovo YOGA con **Linux Mint**.
  - Acceso Remoto: Conectada a Windows 11 vía Tailscale IP `100.82.23.52` (unidad `Z:` SMB).
  - Servicio Backend: `systemctl restart backend.pelulorena.service`.
  - Ruta local: `/home/fabrizio/ProyectosWeb/PeluLorena/peluqueria_lorena/backend`.
- **Servidor de Producción / VPS (Hostinger KVM 1):**
  - Proveedor: Hostinger (cuenta de Ludmila, vencimiento 2028-10-09).
  - Ubicación: Brazil - Campinas.
  - SO: Ubuntu 24.04 LTS.
  - Specs: 1 vCPU, 4 GB RAM, 50 GB NVMe, 4 TB ancho de banda.
  - Hostname: `srv2049787.hstgr.cloud`
  - IPv4 Pública: `179.199.155.141`
  - Tailscale IP: `100.116.140.71`
  - Dominio Público: `peluquerialorena.cloud` y `www.peluquerialorena.cloud` (HTTPS / Certbot SSL).
  - Usuario SSH: `root` (acceso directo restringido vía UFW a `tailscale0`).
  - Red Tailscale: Administrada por Fabrizio. Miembros del equipo acceden vía `100.116.140.71`.
  - Rutas clave en VPS:
    - Raíz del código: `/var/www/peluqueria_lorena`
    - Entorno virtual: `/var/www/peluqueria_lorena/backend/venv`
    - Archivos estáticos: `/var/www/peluqueria_lorena/backend/staticfiles`
    - Base de datos: `/var/www/peluqueria_lorena/backend/db.sqlite3`
  - Servicios y comandos de producción:
    - Backend (Gunicorn): `systemctl restart peluqueria.service` (logs: `journalctl -u peluqueria -f`).
    - Web Server (Nginx): `systemctl reload nginx` (conf: `/etc/nginx/sites-available/peluquerialorena`).
    - Permisos del proyecto: `chown -R :devteampelulorena /var/www/peluqueria_lorena && chmod -R 775 /var/www/peluqueria_lorena`.
    - Samba: Recurso compartido `[PeluLorena]` en `/var/www` montado como unidad `Z:` (restringido a `tailscale0`).
- **Restricciones de Comandos:**
  - Prohibido apagar, suspender o reiniciar la Lenovo YOGA (`shutdown`, `reboot`, etc.).
  - No ejecutar comandos que impacten al OS cliente de Windows 11.

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

## Modo de Salida (ADHD / Acción Inmediata)
- Comenzar siempre con la acción concreta en la primera línea (comando, archivo o snippet). Sin preámbulos.
- Listas numeradas para tareas de múltiples pasos: máximo un cambio por paso.
- Prohibido el texto introductorio ("Claro", "Aquí está...") y cierres de cortesía ("Espero que te sirva").
- Indicar siempre el archivo exacto a editar antes del bloque de código.
- Terminar siempre con exactamente una siguiente acción concreta de menos de 2 minutos.