"""
Peluquería Lorena — Capa de servicios del módulo de Inventario.

Encapsula la lógica de negocio, validaciones y reglas operativas de:
- RF 7.1: Gestión de productos (Alta, edición, baja física y lógica).
- RF 7.2: Descuento manual de stock por consumo en servicios con auditoría.
- RF 7.3: Verificación y generación de alertas automáticas de stock mínimo.

Sigue el paradigma orientado a objetos (POO) y buenas prácticas de Django.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Union

from django.db import transaction
from django.db.models import F, Q, QuerySet

from .models import MovimientoStock, Producto


# ──────────────────────────────────────────────────────────────
# Excepciones de Dominio
# ──────────────────────────────────────────────────────────────


class InventarioError(Exception):
    """Excepción base para errores del módulo de inventario."""
    pass


class StockInsuficienteError(InventarioError):
    """Lanzada cuando se intenta descontar más stock del disponible."""

    def __init__(self, producto_nombre: str, stock_actual: int, cantidad_solicitada: int) -> None:
        self.producto_nombre = producto_nombre
        self.stock_actual = stock_actual
        self.cantidad_solicitada = cantidad_solicitada
        super().__init__(
            f"Stock insuficiente para '{producto_nombre}'. "
            f"Disponible: {stock_actual}, solicitado: {cantidad_solicitada}."
        )


class ProductoNoEncontradoError(InventarioError):
    """Lanzada cuando un producto solicitado no existe en la base de datos."""
    pass


class CantidadInvalidaError(InventarioError):
    """Lanzada cuando la cantidad enviada no es un entero positivo válido."""
    pass


# ──────────────────────────────────────────────────────────────
# Servicio de Negocio
# ──────────────────────────────────────────────────────────────


class InventarioService:
    """
    Servicio de negocio para operaciones sobre productos y movimientos de stock.

    Centraliza la creación, edición, baja, auditoría de consumos y
    disparo de alertas de stock mínimo.
    """

    # ── RF 7.1: Gestión de Productos ──

    @staticmethod
    def crear_producto(
        nombre: str,
        precio: Union[Decimal, float, str],
        stock_actual: int = 0,
        stock_minimo: int = 0,
        descripcion: Optional[str] = None,
        activo: bool = True,
        usuario: Optional[Any] = None,
        unidad_medida: str = "UNIDAD",
        **extra_fields: Any,
    ) -> Producto:
        """
        Crea un nuevo producto en el catálogo del salón y registra automáticamente
        el movimiento de tipo 'Producto añadido' en el historial.

        Args:
            nombre: Nombre representativo del producto o insumo.
            precio: Precio unitario de venta o referencia.
            stock_actual: Cantidad inicial en existencia (>= 0).
            stock_minimo: Umbral de alerta para reposición (>= 0).
            descripcion: Descripción detallada u observaciones.
            activo: Estado inicial (por defecto True).
            usuario: Usuario que realiza el alta (opcional).
            unidad_medida: UNIDAD, LITRO, ML, KG o G. Define si se cuenta
                en unidades o en cantidad (litros, etc.).
            **extra_fields: Campos adicionales.

        Returns:
            Instancia de Producto creada y persistida.

        Raises:
            CantidadInvalidaError: Si los valores de stock o precio son inválidos.
        """
        stock_actual = int(stock_actual)
        stock_minimo = int(stock_minimo)
        precio = Decimal(str(precio))

        if stock_actual < 0:
            raise CantidadInvalidaError("El stock actual no puede ser negativo.")
        if stock_minimo < 0:
            raise CantidadInvalidaError("El stock mínimo no puede ser negativo.")
        if precio < Decimal("0.00"):
            raise CantidadInvalidaError("El precio no puede ser negativo.")
        unidades_validas = {c[0] for c in Producto.UnidadMedida.choices}
        if unidad_medida not in unidades_validas:
            raise CantidadInvalidaError("Unidad de medida inválida.")

        with transaction.atomic():
            producto = Producto.objects.create(
                nombre=nombre.strip(),
                precio=precio,
                stock_actual=stock_actual,
                stock_minimo=stock_minimo,
                descripcion=descripcion.strip() if descripcion else None,
                activo=activo,
                unidad_medida=unidad_medida,
                **extra_fields,
            )

            # Registrar automáticamente el movimiento de alta en el historial
            MovimientoStock.objects.create(
                producto=producto,
                tipo_movimiento=MovimientoStock.TipoMovimiento.ALTA_PRODUCTO,
                cantidad=stock_actual,
                stock_previo=0,
                stock_posterior=stock_actual,
                motivo=f"Producto añadido al catálogo con stock inicial de {stock_actual} {producto.unidad_abreviatura}.",
                usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
            )

        return producto

    @staticmethod
    def obtener_producto_por_id(
        producto_id: int,
        solo_activos: bool = False,
    ) -> Optional[Producto]:
        """
        Busca un producto por su ID primario.

        Args:
            producto_id: Clave primaria del producto.
            solo_activos: Si es True, solo retorna el producto si está activo.

        Returns:
            Instancia de Producto o None si no existe.
        """
        try:
            queryset = Producto.objects.all()
            if solo_activos:
                queryset = queryset.filter(activo=True)
            return queryset.get(pk=producto_id)
        except Producto.DoesNotExist:
            return None

    @staticmethod
    def listar_productos(
        solo_activos: bool = True,
        bajo_stock_only: bool = False,
        busqueda: Optional[str] = None,
    ) -> QuerySet[Producto]:
        """
        Retorna el listado de productos aplicando filtros y búsqueda inteligente por nombre.

        Args:
            solo_activos: Si filtra únicamente productos activos.
            bajo_stock_only: Si filtra solo productos en alerta de stock mínimo.
            busqueda: Término de búsqueda por nombre o descripción.

        Returns:
            QuerySet de productos ordenados alfabéticamente.
        """
        queryset = Producto.objects.all()

        if solo_activos:
            queryset = queryset.filter(activo=True)

        if bajo_stock_only:
            queryset = queryset.filter(stock_actual__lte=F("stock_minimo"))

        if busqueda:
            busqueda = busqueda.strip()
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda)
            )

        return queryset.order_by("nombre")

    @staticmethod
    def actualizar_producto(
        producto: Producto,
        usuario: Optional[Any] = None,
        **campos: Any,
    ) -> Producto:
        """
        Actualiza las propiedades configurables de un producto existente (nombre, descripción, precio y stock mínimo).

        Args:
            producto: Instancia del modelo Producto a actualizar.
            **campos: Diccionario de campos a actualizar.

        Returns:
            Instancia de Producto actualizada.
        """
        campos_permitidos = [
            "nombre",
            "descripcion",
            "precio",
            "unidad_medida",
            "stock_minimo",
            "stockMinimo",
            "stock_actual",
            "stockActual",
            "activo",
        ]
        update_fields: list[str] = ["actualizado_en"]

        for campo, valor in campos.items():
            if campo not in campos_permitidos or valor is None:
                continue

            if campo in ("stock_minimo", "stockMinimo"):
                val_int = int(valor)
                if val_int < 0:
                    raise CantidadInvalidaError("El stock mínimo no puede ser negativo.")
                if producto.stock_minimo != val_int:
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo_movimiento=MovimientoStock.TipoMovimiento.CAMBIO_STOCK_MINIMO,
                        cantidad=0,
                        stock_previo=producto.stock_actual,
                        stock_posterior=producto.stock_actual,
                        motivo=f"Stock mínimo modificado de {producto.stock_minimo} a {val_int}",
                        usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
                    )
                    producto.stock_minimo = val_int
                    if "stock_minimo" not in update_fields:
                        update_fields.append("stock_minimo")

            elif campo in ("stock_actual", "stockActual"):
                val_int = int(valor)
                if val_int < 0:
                    raise CantidadInvalidaError("El stock actual no puede ser negativo.")
                producto.stock_actual = val_int
                if "stock_actual" not in update_fields:
                    update_fields.append("stock_actual")

            elif campo == "precio":
                val_dec = Decimal(str(valor))
                if val_dec < Decimal("0.00"):
                    raise CantidadInvalidaError("El precio no puede ser negativo.")
                if producto.precio != val_dec:
                    # Registrar cambio de precio
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo_movimiento=MovimientoStock.TipoMovimiento.CAMBIO_PRECIO,
                        cantidad=0,
                        stock_previo=producto.stock_actual,
                        stock_posterior=producto.stock_actual,
                        motivo=f"Precio modificado de ${producto.precio} a ${val_dec}",
                        usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
                    )
                    producto.precio = val_dec
                    if "precio" not in update_fields:
                        update_fields.append("precio")

            elif campo == "nombre":
                val_str = str(valor).strip()
                if producto.nombre != val_str:
                    # Registrar cambio de nombre
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo_movimiento=MovimientoStock.TipoMovimiento.CAMBIO_NOMBRE,
                        cantidad=0,
                        stock_previo=producto.stock_actual,
                        stock_posterior=producto.stock_actual,
                        motivo=f"Nombre modificado de '{producto.nombre}' a '{val_str}'",
                        usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
                    )
                    producto.nombre = val_str
                    if "nombre" not in update_fields:
                        update_fields.append("nombre")

            elif campo == "descripcion":
                val_str = str(valor).strip() if valor else None
                if producto.descripcion != val_str:
                    # Registrar cambio de descripcion
                    MovimientoStock.objects.create(
                        producto=producto,
                        tipo_movimiento=MovimientoStock.TipoMovimiento.CAMBIO_DESCRIPCION,
                        cantidad=0,
                        stock_previo=producto.stock_actual,
                        stock_posterior=producto.stock_actual,
                        motivo="Descripción modificada",
                        usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
                    )
                    producto.descripcion = val_str
                    if "descripcion" not in update_fields:
                        update_fields.append("descripcion")

            elif campo == "activo":
                producto.activo = bool(valor)
                if "activo" not in update_fields:
                    update_fields.append("activo")

            elif campo == "unidad_medida":
                unidades_validas = {c[0] for c in Producto.UnidadMedida.choices}
                if valor not in unidades_validas:
                    raise CantidadInvalidaError("Unidad de medida inválida.")
                if producto.unidad_medida != valor:
                    producto.unidad_medida = valor
                    if "unidad_medida" not in update_fields:
                        update_fields.append("unidad_medida")

        producto.save(update_fields=update_fields)
        return producto

    @staticmethod
    def eliminar_producto(
        producto: Producto,
        permanente: bool = False,
        usuario: Optional[Any] = None,
    ) -> None:
        """
        Elimina o da de baja un producto y registra el movimiento de baja en el historial.

        Args:
            producto: Instancia de Producto.
            permanente: Si es False realiza baja lógica (activo=False).
                        Si es True elimina el registro de la BD.
            usuario: Usuario que realiza la operación.
        """
        with transaction.atomic():
            # Registrar movimiento de baja en el historial
            MovimientoStock.objects.create(
                producto=producto,
                tipo_movimiento=MovimientoStock.TipoMovimiento.BAJA_PRODUCTO,
                cantidad=0,
                stock_previo=producto.stock_actual,
                stock_posterior=producto.stock_actual,
                motivo="Producto eliminado / dado de baja del catálogo",
                usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
            )

            if permanente:
                producto.delete()
            else:
                producto.dar_de_baja()

    @staticmethod
    def dar_de_baja_producto(
        producto: Producto,
        usuario: Optional[Any] = None,
    ) -> None:
        """Alias para baja lógica de producto con registro de auditoría."""
        InventarioService.eliminar_producto(producto, permanente=False, usuario=usuario)

    @staticmethod
    def reactivar_producto(producto: Producto) -> None:
        """Reactiva un producto previamente dado de baja lógica."""
        producto.reactivar()

    # ── RF 7.2: Descuento Manual de Stock ──

    @classmethod
    def descontar_stock(
        cls,
        producto_o_id: Union[Producto, int],
        cantidad: int,
        motivo: Optional[str] = None,
        tipo_movimiento: str = MovimientoStock.TipoMovimiento.DESCUENTO,
        usuario: Optional[Any] = None,
    ) -> tuple[MovimientoStock, bool]:
        """
        Descuenta manualmente stock de un producto y registra el movimiento de auditoría.

        Ejecuta la operación de forma atómica y segura ante concurrencia
        mediante bloqueo de fila (select_for_update).

        Args:
            producto_o_id: Instancia de Producto o ID entero.
            cantidad: Cantidad positiva de unidades consumidas.
            motivo: Descripción del servicio o razón del consumo.
            tipo_movimiento: Categoría del movimiento (por defecto DESCUENTO).
            usuario: Usuario del sistema que realiza la acción (opcional).

        Returns:
            Tupla (movimiento_creado, alerta_stock_minimo_activa).

        Raises:
            CantidadInvalidaError: Si la cantidad <= 0.
            ProductoNoEncontradoError: Si el producto no existe.
            StockInsuficienteError: Si la existencia actual es menor a la requerida.
        """
        if cantidad <= 0:
            raise CantidadInvalidaError("La cantidad a descontar debe ser mayor a cero.")

        producto_id = producto_o_id.pk if isinstance(producto_o_id, Producto) else producto_o_id

        with transaction.atomic():
            try:
                producto = Producto.objects.select_for_update().get(pk=producto_id)
            except Producto.DoesNotExist:
                raise ProductoNoEncontradoError(f"No existe el producto con ID {producto_id}.")

            stock_previo = producto.stock_actual
            if stock_previo < cantidad:
                raise StockInsuficienteError(
                    producto_nombre=producto.nombre,
                    stock_actual=stock_previo,
                    cantidad_solicitada=cantidad,
                )

            stock_posterior = stock_previo - cantidad
            producto.stock_actual = stock_posterior
            producto.save(update_fields=["stock_actual", "actualizado_en"])

            movimiento = MovimientoStock.objects.create(
                producto=producto,
                tipo_movimiento=tipo_movimiento,
                cantidad=cantidad,
                stock_previo=stock_previo,
                stock_posterior=stock_posterior,
                motivo=motivo.strip() if motivo else "Descuento manual de stock",
                usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
            )

            alerta_stock = producto.verificar_stock_minimo()

        return movimiento, alerta_stock

    @classmethod
    def registrar_consumo_servicio(
        cls,
        producto_o_id: Union[Producto, int],
        cantidad: int,
        detalle_servicio: str,
        usuario: Optional[Any] = None,
    ) -> tuple[MovimientoStock, bool]:
        """
        RF 7.2: Registra manualmente el consumo de stock al finalizar un servicio.

        Args:
            producto_o_id: Producto o ID.
            cantidad: Unidades consumidas durante el servicio.
            detalle_servicio: Descripción del servicio, tratamiento realizado o clienta.
            usuario: Empleada/administradora que registra el consumo.

        Returns:
            Tupla (movimiento, alerta_stock_minimo).
        """
        return cls.descontar_stock(
            producto_o_id=producto_o_id,
            cantidad=cantidad,
            motivo=detalle_servicio,
            tipo_movimiento=MovimientoStock.TipoMovimiento.DESCUENTO,
            usuario=usuario,
        )

    @classmethod
    def reponer_stock(
        cls,
        producto_o_id: Union[Producto, int],
        cantidad: int,
        motivo: Optional[str] = None,
        usuario: Optional[Any] = None,
    ) -> MovimientoStock:
        """
        Registra el ingreso/reposición de stock para un producto (Agregar Stock).

        Args:
            producto_o_id: Producto o ID.
            cantidad: Unidades a ingresar (> 0).
            motivo: Detalle de la compra, proveedor o remito.
            usuario: Usuario que realiza el ingreso.

        Returns:
            Instancia de MovimientoStock registrada.
        """
        if cantidad <= 0:
            raise CantidadInvalidaError("La cantidad a reponer debe ser mayor a cero.")

        producto_id = producto_o_id.pk if isinstance(producto_o_id, Producto) else producto_o_id

        with transaction.atomic():
            try:
                producto = Producto.objects.select_for_update().get(pk=producto_id)
            except Producto.DoesNotExist:
                raise ProductoNoEncontradoError(f"No existe el producto con ID {producto_id}.")

            stock_previo = producto.stock_actual
            stock_posterior = stock_previo + cantidad
            producto.stock_actual = stock_posterior
            producto.save(update_fields=["stock_actual", "actualizado_en"])

            movimiento = MovimientoStock.objects.create(
                producto=producto,
                tipo_movimiento=MovimientoStock.TipoMovimiento.REPOSICION,
                cantidad=cantidad,
                stock_previo=stock_previo,
                stock_posterior=stock_posterior,
                motivo=motivo.strip() if motivo else "Reposición de Stock",
                usuario=usuario if (usuario and getattr(usuario, "is_authenticated", False)) else None,
            )

        return movimiento

    # ── RF 7.3: Alertas de Stock Mínimo ──

    @staticmethod
    def obtener_productos_bajo_stock() -> QuerySet[Producto]:
        """
        RF 7.3: Retorna todos los productos activos que alcanzaron o están por
        debajo de su stock mínimo configurado (stock_actual <= stock_minimo).

        Returns:
            QuerySet de productos en nivel crítico ordenados por stock actual ascendente.
        """
        return Producto.objects.filter(
            activo=True,
            stock_actual__lte=F("stock_minimo"),
        ).order_by("stock_actual", "nombre")

    @classmethod
    def contar_alertas_stock(cls) -> int:
        """Retorna el número de productos en alerta crítica de stock."""
        return cls.obtener_productos_bajo_stock().count()

    # ── Auditoría e Historial con Buscador Inteligente ──

    @staticmethod
    def obtener_historial_movimientos(
        producto_id: Optional[int] = None,
        tipo_movimiento: Optional[str] = None,
        busqueda: Optional[str] = None,
    ) -> QuerySet[MovimientoStock]:
        """
        Consulta el historial cronológico de movimientos de inventario con soporte
        para búsqueda inteligente por nombre de producto o detalle/motivo.

        Args:
            producto_id: Filtro opcional por producto específico.
            tipo_movimiento: Filtro opcional por tipo de movimiento.
            busqueda: Texto de búsqueda inteligente por nombre de producto o motivo.

        Returns:
            QuerySet de MovimientoStock ordenado del más reciente al más antiguo.
        """
        queryset = MovimientoStock.objects.select_related("producto", "usuario").all()

        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)

        if tipo_movimiento:
            queryset = queryset.filter(tipo_movimiento=tipo_movimiento)

        if busqueda:
            busqueda = busqueda.strip()
            queryset = queryset.filter(producto__nombre__icontains=busqueda)

        return queryset.order_by("-fecha")
        return cls.contar_alertas_stock(*args, **kwargs)

    @classmethod
    def obtenerHistorialMovimientos(cls, *args: Any, **kwargs: Any) -> QuerySet[MovimientoStock]:
        """Alias camelCase para obtener_historial_movimientos."""
        return cls.obtener_historial_movimientos(*args, **kwargs)
