"""
Peluquería Lorena — Tests unitarios del módulo de Usuarios.

Valida la lógica de negocio a nivel de modelos y servicios:
- Hasheo de contraseñas (PBKDF2)
- Validación de roles
- Métodos de proxy models (Empleada / Administradora)
- Creación y actualización de usuarios via UsuarioService
- Unicidad del campo email
"""
import pytest
from django.contrib.auth.hashers import check_password

from apps.usuarios.models import Administradora, Empleada, Usuario
from apps.usuarios.services import UsuarioService
from tests.factories.usuario_factory import (
    AdministradoraFactory,
    EmpleadaFactory,
    UsuarioFactory,
)


# ──────────────────────────────────────────────────────────────
# Tests de Modelo: Hasheo de Contraseñas
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestHasheoPassword:
    """Verifica que las contraseñas se almacenen hasheadas."""

    def test_password_se_almacena_hasheada(self) -> None:
        """La contraseña no se guarda en texto plano."""
        usuario = UsuarioFactory(email="hash@test.com")
        assert usuario.password != "TestPass123!"
        assert usuario.password.startswith(("pbkdf2_", "md5$"))

    def test_check_password_valida_correctamente(self) -> None:
        """check_password retorna True con la contraseña correcta."""
        usuario = UsuarioFactory(email="check@test.com")
        assert check_password("TestPass123!", usuario.password) is True

    def test_check_password_rechaza_incorrecta(self) -> None:
        """check_password retorna False con contraseña incorrecta."""
        usuario = UsuarioFactory(email="wrong@test.com")
        assert check_password("PasswordIncorrecta", usuario.password) is False


# ──────────────────────────────────────────────────────────────
# Tests de Modelo: Roles
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRolesUsuario:
    """Verifica la asignación y validación de roles."""

    def test_rol_empleada_por_defecto(self) -> None:
        """Un usuario creado sin especificar rol es EMPLEADA."""
        usuario = UsuarioFactory(email="default@test.com")
        assert usuario.rol == Usuario.Rol.EMPLEADA

    def test_rol_administradora_asignable(self) -> None:
        """Se puede asignar el rol ADMINISTRADORA."""
        admin = AdministradoraFactory(email="admin-rol@test.com")
        assert admin.rol == Usuario.Rol.ADMINISTRADORA

    def test_choices_de_rol_validos(self) -> None:
        """Solo existen dos roles válidos."""
        roles_validos = {choice[0] for choice in Usuario.Rol.choices}
        assert roles_validos == {"ADMINISTRADORA", "EMPLEADA"}

    def test_es_administradora_property(self) -> None:
        """El método es_administradora retorna True solo para admins."""
        admin = AdministradoraFactory(email="prop-admin@test.com")
        empleada = EmpleadaFactory(email="prop-emp@test.com")
        assert admin.es_administradora is True
        assert empleada.es_administradora is False

    def test_es_empleada_property(self) -> None:
        """El método es_empleada retorna True para empleadas y admins."""
        admin = AdministradoraFactory(email="emp-admin@test.com")
        empleada = EmpleadaFactory(email="emp-emp@test.com")
        # Administradora hereda de Empleada, por lo que también es empleada
        assert empleada.es_empleada is True
        assert admin.es_empleada is True


# ──────────────────────────────────────────────────────────────
# Tests de Modelo: Proxy Models
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProxyModels:
    """Verifica los métodos de las clases Empleada y Administradora."""

    def test_empleada_tiene_metodos_operativos(self) -> None:
        """Empleada tiene acceso a métodos operativos."""
        empleada = EmpleadaFactory(email="metodos-emp@test.com")
        assert hasattr(empleada, "consultar_agenda")
        assert hasattr(empleada, "gestionar_clientas")
        assert hasattr(empleada, "registrar_cobro")
        assert hasattr(empleada, "registrar_trabajo")

    def test_administradora_tiene_metodos_de_gestion(self) -> None:
        """Administradora tiene acceso a métodos de gestión completa."""
        admin = AdministradoraFactory(email="metodos-admin@test.com")
        assert hasattr(admin, "gestionar_usuarios")
        assert hasattr(admin, "gestionar_servicios")
        assert hasattr(admin, "cerrar_caja")
        assert hasattr(admin, "gestionar_proveedores")
        assert hasattr(admin, "generar_reportes")
        assert hasattr(admin, "configurar_beneficios")

    def test_administradora_hereda_metodos_de_empleada(self) -> None:
        """Administradora también tiene los métodos de Empleada."""
        admin = AdministradoraFactory(email="herencia@test.com")
        assert hasattr(admin, "consultar_agenda")
        assert hasattr(admin, "registrar_cobro")

    def test_proxy_models_usan_misma_tabla(self) -> None:
        """Empleada y Administradora comparten la tabla de Usuario."""
        assert Empleada._meta.proxy is True
        assert Administradora._meta.proxy is True


# ──────────────────────────────────────────────────────────────
# Tests de Modelo: Unicidad de Email
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUnicidadEmail:
    """Verifica que el email sea único a nivel de base de datos."""

    def test_email_duplicado_lanza_error(self) -> None:
        """No se puede crear dos usuarios con el mismo email."""
        Usuario.objects.create_user(email="duplicado@test.com", nombre="Original", password="123")
        with pytest.raises(Exception):
            Usuario.objects.create_user(email="duplicado@test.com", nombre="Duplicado", password="123")

    def test_email_es_username_field(self) -> None:
        """El campo email se usa como USERNAME_FIELD."""
        assert Usuario.USERNAME_FIELD == "email"


# ──────────────────────────────────────────────────────────────
# Tests de Servicio: UsuarioService
# ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestUsuarioServiceCrear:
    """Verifica la creación de usuarios via el servicio."""

    def test_crear_usuario_retorna_instancia(self) -> None:
        """crear_usuario retorna un objeto Usuario persistido."""
        usuario = UsuarioService.crear_usuario(
            nombre="Ana Martínez",
            email="ana@test.com",
            password="SecurePass123!",
            rol=Usuario.Rol.EMPLEADA,
        )
        assert isinstance(usuario, Usuario)
        assert usuario.pk is not None

    def test_crear_usuario_hashea_password(self) -> None:
        """El servicio hashea la contraseña al crear."""
        usuario = UsuarioService.crear_usuario(
            nombre="Lucía Pérez",
            email="lucia@test.com",
            password="SecurePass123!",
            rol=Usuario.Rol.EMPLEADA,
        )
        assert usuario.password != "SecurePass123!"
        assert check_password("SecurePass123!", usuario.password) is True

    def test_crear_administradora_con_is_staff(self) -> None:
        """Una administradora se crea con is_staff=True."""
        admin = UsuarioService.crear_usuario(
            nombre="Lorena Admin",
            email="lorena-admin@test.com",
            password="AdminPass123!",
            rol=Usuario.Rol.ADMINISTRADORA,
        )
        assert admin.is_staff is True
        assert admin.rol == Usuario.Rol.ADMINISTRADORA


@pytest.mark.django_db
class TestUsuarioServiceActualizar:
    """Verifica la actualización de usuarios via el servicio."""

    def test_actualizar_nombre(self) -> None:
        """Se puede actualizar el nombre de un usuario."""
        usuario = UsuarioFactory(email="update@test.com", nombre="Original")
        actualizado = UsuarioService.actualizar_usuario(
            usuario=usuario,
            nombre="Nombre Nuevo",
        )
        assert actualizado.nombre == "Nombre Nuevo"

    def test_actualizar_no_modifica_password_si_no_se_envia(self) -> None:
        """Actualizar sin enviar password no cambia la contraseña."""
        usuario = UsuarioFactory(email="no-pw@test.com")
        password_original = usuario.password
        UsuarioService.actualizar_usuario(
            usuario=usuario,
            nombre="Otro Nombre",
        )
        usuario.refresh_from_db()
        assert usuario.password == password_original


@pytest.mark.django_db
class TestUsuarioServiceEliminar:
    """Verifica la eliminación (soft delete) de usuarios."""

    def test_eliminar_usuario_desactiva(self) -> None:
        """eliminar_usuario hace soft delete (is_active=False)."""
        usuario = UsuarioFactory(email="delete@test.com")
        assert usuario.is_active is True
        UsuarioService.eliminar_usuario(usuario)
        usuario.refresh_from_db()
        assert usuario.is_active is False


@pytest.mark.django_db
class TestUsuarioServiceCambiarPassword:
    """Verifica el cambio de contraseña via servicio."""

    def test_cambiar_password_exitoso(self) -> None:
        """Se puede cambiar la contraseña con la contraseña actual correcta."""
        usuario = UsuarioFactory(email="cambio@test.com")
        resultado = UsuarioService.cambiar_password(
            usuario=usuario,
            old_password="TestPass123!",
            new_password="NuevaPass456!",
        )
        assert resultado is True
        usuario.refresh_from_db()
        assert check_password("NuevaPass456!", usuario.password) is True

    def test_cambiar_password_con_old_incorrecta_falla(self) -> None:
        """No se puede cambiar la contraseña si la actual es incorrecta."""
        usuario = UsuarioFactory(email="fail-pw@test.com")
        resultado = UsuarioService.cambiar_password(
            usuario=usuario,
            old_password="IncorrectaVieja",
            new_password="NuevaPass456!",
        )
        assert resultado is False
