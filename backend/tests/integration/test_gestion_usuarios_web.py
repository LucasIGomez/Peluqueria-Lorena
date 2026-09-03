"""
Peluquería Lorena — Tests de integración para Registro, Login y Gestión de Usuarios.

Verifica:
1. Registro con validación de PIN para rol ADMINISTRADORA (PIN=1234).
2. Registro de EMPLEADA sin necesidad de PIN.
3. Inicio de sesión Web (Login) y recuperación de datos y rol en sesión.
4. Restricción de acceso al panel de Gestión de Usuarios (exclusivo Administradora).
5. Operaciones CRUD de usuarios por parte de la Administradora.
"""
import pytest
from django.urls import reverse
from apps.usuarios.models import Usuario
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.mark.django_db
class TestRegistroUsuariosWeb:
    """Pruebas del formulario de registro público de usuarios."""

    def test_registro_empleada_exitoso_sin_pin(self, client) -> None:
        """Una empleada se registra exitosamente sin ingresar PIN de administradora."""
        url = reverse("usuarios:registro")
        data = {
            "nombre": "Florencia Peluquera",
            "email": "florencia@peluquerialorena.com",
            "rol": Usuario.Rol.EMPLEADA,
            "admin_pin": "",
            "password": "PasswordSegura123!",
            "confirm_password": "PasswordSegura123!",
        }
        response = client.post(url, data, follow=True)
        assert response.status_code == 200

        # Verificar que se persistió en la base de datos
        usuario = Usuario.objects.filter(email="florencia@peluquerialorena.com").first()
        assert usuario is not None
        assert usuario.nombre == "Florencia Peluquera"
        assert usuario.rol == Usuario.Rol.EMPLEADA
        assert usuario.es_empleada is True
        assert usuario.es_administradora is False
        assert usuario.is_staff is False
        assert usuario.check_password("PasswordSegura123!") is True

    def test_registro_administradora_con_pin_correcto(self, client) -> None:
        """Una administradora se registra exitosamente ingresando el PIN de seguridad 1234."""
        url = reverse("usuarios:registro")
        data = {
            "nombre": "Lorena Dueña",
            "email": "lorena@peluquerialorena.com",
            "rol": Usuario.Rol.ADMINISTRADORA,
            "admin_pin": "1234",
            "password": "LorenaPassword123!",
            "confirm_password": "LorenaPassword123!",
        }
        response = client.post(url, data, follow=True)
        assert response.status_code == 200

        usuario = Usuario.objects.filter(email="lorena@peluquerialorena.com").first()
        assert usuario is not None
        assert usuario.nombre == "Lorena Dueña"
        assert usuario.rol == Usuario.Rol.ADMINISTRADORA
        assert usuario.es_administradora is True
        assert usuario.is_staff is True
        assert usuario.check_password("LorenaPassword123!") is True

    def test_registro_administradora_con_pin_incorrecto_falla(self, client) -> None:
        """El intento de registrar Administradora con PIN incorrecto se rechaza y no se guarda."""
        url = reverse("usuarios:registro")
        data = {
            "nombre": "Intruso",
            "email": "intruso@test.com",
            "rol": Usuario.Rol.ADMINISTRADORA,
            "admin_pin": "9999",  # PIN erróneo
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        response = client.post(url, data)
        assert response.status_code == 200

        # No debe haberse guardado en la base de datos
        assert Usuario.objects.filter(email="intruso@test.com").exists() is False

    def test_registro_administradora_sin_pin_falla(self, client) -> None:
        """El intento de registrar Administradora sin PIN se rechaza."""
        url = reverse("usuarios:registro")
        data = {
            "nombre": "Sin Pin",
            "email": "sinpin@test.com",
            "rol": Usuario.Rol.ADMINISTRADORA,
            "admin_pin": "",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        response = client.post(url, data)
        assert response.status_code == 200
        assert Usuario.objects.filter(email="sinpin@test.com").exists() is False


@pytest.mark.django_db
class TestLoginUsuariosWeb:
    """Pruebas del inicio de sesión web y recuperación de datos y rol."""

    def test_login_exitoso_empleada_establece_sesion(self, client) -> None:
        """Una empleada inicia sesión, se guardan sus datos en la sesión y se reconoce su rol."""
        empleada = EmpleadaFactory(email="empleada.login@test.com", nombre="Ana Gomez")

        url = reverse("usuarios:login")
        response = client.post(
            url,
            {"email": "empleada.login@test.com", "password": "TestPass123!"},
            follow=True,
        )
        assert response.status_code == 200

        # Verificar sesión de Django
        usuario_sesion = response.context["user"]
        assert usuario_sesion.is_authenticated is True
        assert usuario_sesion.email == "empleada.login@test.com"
        assert usuario_sesion.es_empleada is True
        assert usuario_sesion.es_administradora is False

    def test_login_exitoso_administradora_establece_sesion(self, client) -> None:
        """Una administradora inicia sesión y el contexto reconoce su rol administrativo."""
        admin = AdministradoraFactory(email="admin.login@test.com", nombre="Lorena Gomez")

        url = reverse("usuarios:login")
        response = client.post(
            url,
            {"email": "admin.login@test.com", "password": "TestPass123!"},
            follow=True,
        )
        assert response.status_code == 200

        usuario_sesion = response.context["user"]
        assert usuario_sesion.is_authenticated is True
        assert usuario_sesion.es_administradora is True
        assert usuario_sesion.rol == Usuario.Rol.ADMINISTRADORA

    def test_login_con_password_incorrecta_rechaza(self, client) -> None:
        """Intento de login con credenciales erróneas es rechazado y no autentica."""
        EmpleadaFactory(email="test.error@test.com")

        url = reverse("usuarios:login")
        response = client.post(
            url,
            {"email": "test.error@test.com", "password": "PasswordEquivocada!"},
        )
        assert response.status_code == 200
        assert response.context["user"].is_authenticated is False


@pytest.mark.django_db
class TestGestionUsuariosPermisosYCRUD:
    """Pruebas de la sección de gestión de usuarios (CRUD exclusivo Administradora)."""

    def test_empleada_no_puede_acceder_a_gestion_usuarios(self, client) -> None:
        """Una empleada autenticada no tiene permiso para entrar al panel de gestión de usuarios."""
        empleada = EmpleadaFactory(email="empleada.bloqueada@test.com")
        client.force_login(empleada)

        url = reverse("usuarios:lista_usuarios")
        response = client.get(url)
        # Debe redirigir (302) porque user_passes_test falla
        assert response.status_code == 302

    def test_administradora_puede_acceder_a_gestion_usuarios(self, client) -> None:
        """La administradora accede correctamente al listado de usuarios (200 OK)."""
        admin = AdministradoraFactory(email="admin.acceso@test.com")
        client.force_login(admin)

        url = reverse("usuarios:lista_usuarios")
        response = client.get(url)
        assert response.status_code == 200
        assert "Gestión de Usuarios y Personal" in response.content.decode("utf-8")

    def test_administradora_crea_nuevo_usuario_desde_panel(self, client) -> None:
        """La administradora registra una nueva empleada desde el panel administrativo."""
        admin = AdministradoraFactory(email="admin.creadora@test.com")
        client.force_login(admin)

        url = reverse("usuarios:crear_usuario")
        data = {
            "nombre": "Mariana Manicura",
            "email": "mariana@peluquerialorena.com",
            "rol": Usuario.Rol.EMPLEADA,
            "password": "PasswordMariana123!",
            "admin_pin": "",
        }
        response = client.post(url, data, follow=True)
        assert response.status_code == 200

        nuevo_user = Usuario.objects.filter(email="mariana@peluquerialorena.com").first()
        assert nuevo_user is not None
        assert nuevo_user.nombre == "Mariana Manicura"
        assert nuevo_user.rol == Usuario.Rol.EMPLEADA

    def test_administradora_edita_usuario_existente(self, client) -> None:
        """La administradora modifica el nombre y rol de un usuario."""
        admin = AdministradoraFactory(email="admin.editora@test.com")
        empleada = EmpleadaFactory(email="empleada.para.editar@test.com", nombre="Nombre Viejo")
        client.force_login(admin)

        url = reverse("usuarios:editar_usuario", kwargs={"pk": empleada.pk})
        data = {
            "nombre": "Nombre Corregido",
            "email": "empleada.para.editar@test.com",
            "rol": Usuario.Rol.EMPLEADA,
            "is_active": True,
        }
        response = client.post(url, data, follow=True)
        assert response.status_code == 200

        empleada.refresh_from_db()
        assert empleada.nombre == "Nombre Corregido"

    def test_administradora_da_de_baja_logica_usuario(self, client) -> None:
        """La administradora desactiva (baja lógica) a un usuario."""
        admin = AdministradoraFactory(email="admin.baja@test.com")
        empleada = EmpleadaFactory(email="empleada.para.baja@test.com")
        client.force_login(admin)

        url = reverse("usuarios:eliminar_usuario", kwargs={"pk": empleada.pk})
        response = client.post(url, follow=True)
        assert response.status_code == 200

        empleada.refresh_from_db()
        assert empleada.is_active is False
