# AGENTS.md — Peluquería Lorena

## Idioma y Comunicación
- Responder, explicar y documentar siempre en **español**.
- Mensajes de commit, nombres de migraciones, docstrings y comentarios de código en español.

## Entorno y Quirks Operativos
- **Ubicación de trabajo:** Unidad montada de red (`Z:\peluqueria_lorena`).
- **Rendimiento I/O:** Prohibido realizar búsquedas ciegas recursivas o comandos pesados en todo el árbol de archivos. Usar siempre referencias quirúrgicas (`@backend/...` o `@frontend/...`) para evitar congelamientos por latencia de red.
- **Entorno virtual:** Usar los intérpretes dedicados en `backend\.venv-win\Scripts\python.exe` o `backend\venv\Scripts\python.exe`. No ejecutar `python` o `pip` globales del sistema.
- **Archivos ignorados:** Respetar estrictamente `.gitignore` (`.venv*/`, `__pycache__/`, `db.sqlite3`, `*.pyc`, temporales).

## Stack Técnico y Arquitectura
- **Backend:** Python (3.11/3.12+) con **Django 5.1** y **Django REST Framework (DRF 3.15+)**.
  - Settings modularizados en `backend/config/settings/` (`base.py`, `local.py`, `testing.py`).
  - Entorno de desarrollo por defecto: `DJANGO_SETTINGS_MODULE=config.settings.local`.
- **Base de Datos:** SQLite local (`db.sqlite3`), SQLite en memoria para tests (`:memory:`) y PostgreSQL previsto para producción (`psycopg2-binary`).
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
Ejecutar siempre parados dentro del directorio `backend/`:
- **Servidor local:**
  `python manage.py runserver --settings=config.settings.local`
- **Migraciones:**
  `python manage.py makemigrations --settings=config.settings.local`
  `python manage.py migrate --settings=config.settings.local`
- **Testing (pytest):**
  `pytest` (usa `pytest.ini` y `config.settings.testing` automáticamente)
  - Correr un archivo de test específico: `pytest tests/unit/test_nombre.py`
  - Con cobertura: `pytest --cov=apps`
- **Creación de fixtures:** Usar `factory-boy` y `Faker` según las convenciones en `backend/tests/`.

## Reglas de Modificación de Código
1. **Ediciones quirúrgicas:** No reescribir vistas o modelos enteros si solo se añade un método o campo.
2. **Seguridad y Secretos:** Jamás hardcodear credenciales, API keys o PINs; usar `python-decouple` (`config(...)`).
3. **ORM & Migraciones:** No modificar archivos de migración ya aplicados; generar siempre una nueva migración con `makemigrations`.
4. **Formularios y Vistas:** Mantener validaciones de negocio en forms/serializers o modelos, no acumular lógica en plantillas HTML.

## Ordenador de Hosteo
- El proyecto reside en una computadora de marca Lenovo YOGA (con el sistema operativo Linux Mint), la cual es accedida desde esta computadora (Windows 11) mediante una unidad de red que se conecta por una IP de Tailscale (100.82.23.52); por ende, no debes ejecutar ningun comando que pueda apagar, suspender, hibernar, etc la computadora de hosteo, ni se debería ejecutar ningún comando que impacte en el sistema desde la computadora que está emitiendo los prompts (Windows 11).