"""
Peluquería Lorena — Tests de integración para Login y Gestión de Usuarios.

Verifica:
1. El registro público ya no existe (solo la Administradora crea usuarios).
2. Inicio de sesión Web (Login) y recuperación de datos y rol en sesión.
3. Restricción de acceso al panel de Gestión de Usuarios (exclusivo Administradora).
4. Alta / edición / baja de usuarios por parte de la Administradora, usando el DNI como contraseña.
"""
import pytest
from django.urls import reverse
from apps.usuarios.models import Usuario
from tests.factories.usuario_factory import AdministradoraFactory, EmpleadaFactory


@pytest.mark.django_db
class TestRegistroPublicoDeshabilitado:
    """El auto-registro de usuarios fue eliminado."""

    def test_no_hay_nombre_de_url_registro(self) -> None:
        """El name 'usuarios:registro' ya no puede resolverse."""
        from django.urls import NoReverseMatch

        with pytest.raises(NoReverseMatch):
            reverse("usuarios:registro")

    def test_registro_no_sirve_formulario(self, client) -> None:
        """/usuarios/registro/ ya no devuelve un formulario de registro."""
        response = client.get("/usuarios/registro/")
        assert response.status_code != 200

    def test_pantalla_login_no_ofrece_registrarse(self, client) -> None:
        """La pantalla de login ya no tiene el link para auto-registrarse."""
        response = client.get(reverse("usuarios:login"))
        assert response.status_code == 200
        cuerpo = response.content.decode("utf-8").lower()
        assert "registrate" not in cuerpo
        assert "/usuarios/registro/" not in cuerpo


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
            "dni": "40123456",
        }
        response = client.post(url, data, follow=True)
        assert response.status_code == 200

        nuevo_user = Usuario.objects.filter(email="mariana@peluquerialorena.com").first()
        assert nuevo_user is not None
        assert nuevo_user.nombre == "Mariana Manicura"
        assert nuevo_user.rol == Usuario.Rol.EMPLEADA
        assert nuevo_user.dni == "40123456"
        # El DNI es la contraseña de acceso
        assert nuevo_user.check_password("40123456") is True

    def test_administradora_edita_usuario_existente(self, client) -> None:
        """La administradora modifica el nombre y rol de un usuario."""
        admin = AdministradoraFactory(email="admin.editora@test.com")
        empleada = EmpleadaFactory(
            email="empleada.para.editar@test.com", nombre="Nombre Viejo", dni="30111222"
        )
        client.force_login(admin)

        url = reverse("usuarios:editar_usuario", kwargs={"pk": empleada.pk})
        data = {
            "nombre": "Nombre Corregido",
            "email": "empleada.para.editar@test.com",
            "rol": Usuario.Rol.EMPLEADA,
            "dni": "30111222",
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


@pytest.mark.django_db
class TestValidacionesGestionUsuarios:
    """Validaciones del alta/edición de usuarios."""

    def _login_admin(self, client):
        # Partimos de una única administradora conocida (la migración crea una
        # cuenta semilla que acá no queremos que interfiera con los conteos).
        Usuario.objects.filter(rol=Usuario.Rol.ADMINISTRADORA).delete()
        admin = AdministradoraFactory(email="admin.valida@test.com")
        client.force_login(admin)
        return admin

    def test_dni_trivial_es_rechazado(self, client) -> None:
        self._login_admin(client)
        response = client.post(
            reverse("usuarios:crear_usuario"),
            {"nombre": "Ana Perez", "email": "ana@test.com", "rol": Usuario.Rol.EMPLEADA, "dni": "00000000"},
        )
        assert response.status_code == 200
        assert Usuario.objects.filter(email="ana@test.com").exists() is False

    def test_dni_con_letras_es_rechazado(self, client) -> None:
        self._login_admin(client)
        response = client.post(
            reverse("usuarios:crear_usuario"),
            {"nombre": "Ana Perez", "email": "ana2@test.com", "rol": Usuario.Rol.EMPLEADA, "dni": "40ABC123"},
        )
        assert response.status_code == 200
        assert Usuario.objects.filter(email="ana2@test.com").exists() is False

    def test_nombre_invalido_es_rechazado(self, client) -> None:
        self._login_admin(client)
        response = client.post(
            reverse("usuarios:crear_usuario"),
            {"nombre": "1", "email": "ana3@test.com", "rol": Usuario.Rol.EMPLEADA, "dni": "40555666"},
        )
        assert response.status_code == 200
        assert Usuario.objects.filter(email="ana3@test.com").exists() is False

    def test_editar_normaliza_el_email(self, client) -> None:
        self._login_admin(client)
        emp = EmpleadaFactory(email="emp.norm@test.com", nombre="Original", dni="35111000")
        response = client.post(
            reverse("usuarios:editar_usuario", kwargs={"pk": emp.pk}),
            {
                "nombre": "Original",
                "email": "  EMP.Norm@TEST.com  ",
                "rol": Usuario.Rol.EMPLEADA,
                "dni": "35111000",
                "is_active": True,
            },
            follow=True,
        )
        assert response.status_code == 200
        emp.refresh_from_db()
        assert emp.email == "emp.norm@test.com"

    def test_no_se_puede_degradar_a_la_ultima_administradora(self, client) -> None:
        """Editar la única admin activa cambiándole el rol se rechaza."""
        admin = self._login_admin(client)
        response = client.post(
            reverse("usuarios:editar_usuario", kwargs={"pk": admin.pk}),
            {
                "nombre": admin.nombre,
                "email": admin.email,
                "rol": Usuario.Rol.EMPLEADA,
                "dni": "36999888",
                "is_active": True,
            },
        )
        assert response.status_code == 200
        admin.refresh_from_db()
        assert admin.rol == Usuario.Rol.ADMINISTRADORA

    def test_no_se_puede_desactivar_a_la_ultima_administradora(self, client) -> None:
        """Editar la única admin activa desactivándola se rechaza."""
        admin = self._login_admin(client)
        response = client.post(
            reverse("usuarios:editar_usuario", kwargs={"pk": admin.pk}),
            {
                "nombre": admin.nombre,
                "email": admin.email,
                "rol": Usuario.Rol.ADMINISTRADORA,
                "dni": "36999888",
                "is_active": False,
            },
        )
        assert response.status_code == 200
        admin.refresh_from_db()
        assert admin.is_active is True

    def test_se_puede_degradar_una_admin_si_hay_otra(self, client) -> None:
        """Si hay más de una admin activa, degradar a una está permitido."""
        self._login_admin(client)
        otra = AdministradoraFactory(email="otra.admin.ok@test.com", nombre="Otra Admin", dni="37222333")
        response = client.post(
            reverse("usuarios:editar_usuario", kwargs={"pk": otra.pk}),
            {
                "nombre": "Otra Admin",
                "email": "otra.admin.ok@test.com",
                "rol": Usuario.Rol.EMPLEADA,
                "dni": "37222333",
                "is_active": True,
            },
            follow=True,
        )
        assert response.status_code == 200
        otra.refresh_from_db()
        assert otra.rol == Usuario.Rol.EMPLEADA
