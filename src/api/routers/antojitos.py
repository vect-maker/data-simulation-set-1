"""Routers for Caso 1: Antojitos Express (Cocina Fantasma / Delivery en Managua)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from src.api.database import fetch_all
from src.api.schemas import (
    CategoriaPlatilloOut,
    ClimaDiarioOut,
    DetalleOrdenOut,
    OrdenDetailOut,
    OrdenOut,
    PaginatedResponse,
    PlatilloOut,
    PromocionOut,
    RepartidorOut,
    ZonaOut,
)
from src.api.utils import execute_paginated_query, fetch_single_resource, sanitize_row

router = APIRouter(prefix="/antojitos", tags=["Caso 1: Antojitos Express"])
SCHEMA = "raw_staging"


@router.get(
    "/zonas",
    response_model=PaginatedResponse[ZonaOut],
    summary="Listar zonas de cobertura urbana en Managua",
    description=(
        "### Catálogo de Zonas Urbanas y Tarifas Base\n\n"
        "Retorna la división territorial de Managua atendida por la cocina central de Antojitos Express. "
        "Para cada cuadrante o barrio, se detalla la distancia radial en kilómetros, el tiempo estimado de viaje "
        "y la tarifa base de envío en Córdobas (NIO)."
    ),
    response_description="Colección paginada de zonas urbanas con sus coordenadas y tarifas",
    responses={
        200: {"description": "Consulta exitosa de zonas urbanas."},
        422: {"description": "Error en los parámetros de paginación o formato de consulta."},
    },
)
def get_zonas(
    sort: Annotated[
        str | None,
        Query(
            description="Campo por el cual ordenar los resultados. Usa prefijo '-' para orden descendente (ej. '-distancia_km').",
            examples=["distancia_km", "-tarifa_envio_base"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Número de registros a omitir desde el inicio (desplazamiento para paginación).",
            examples=[0],
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=200,
            description="Cantidad máxima de registros a retornar por página (máximo permitido: 200).",
            examples=[50],
        ),
    ] = 50,
):
    """Retorna las zonas de cobertura urbana en Managua con distancias y tarifas base."""
    allowed = {
        "id_zona",
        "nombre_zona",
        "distancia_km",
        "tiempo_base_minutos",
        "tarifa_envio_base",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="zonas",
        allowed_sort_columns=allowed,
        default_sort="id_zona",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/repartidores",
    response_model=PaginatedResponse[RepartidorOut],
    summary="Listar flota de repartidores y disponibilidad",
    description=(
        "### Directorio de Repartidores de la Flota\n\n"
        "Consulta el equipo de repartidores disponibles para la entrega de pedidos en Managua. "
        "Permite evaluar el tipo de vehículo utilizado ('moto', 'bicicleta', 'auto'), capacidad de carga "
        "y calificación histórica otorgada por los comensales."
    ),
    response_description="Colección paginada de repartidores con estado y calificaciones",
    responses={
        200: {"description": "Consulta exitosa de repartidores."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_repartidores(
    tipo_vehiculo: Annotated[
        str | None,
        Query(
            description="Filtrar por tipo de transporte utilizado.",
            examples=["moto", "bicicleta", "auto"],
        ),
    ] = None,
    estado: Annotated[
        str | None,
        Query(
            description="Filtrar por estado operativo del repartidor.",
            examples=["activo", "inactivo", "descanso"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-calificacion_promedio' para los mejor calificados).",
            examples=["calificacion_promedio", "-calificacion_promedio"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Límite de registros por página.", examples=[50]),
    ] = 50,
):
    """Consulta la flota de repartidores disponibles, vehículos y calificaciones."""
    filters: list[tuple[str, str, Any]] = []
    if tipo_vehiculo:
        filters.append(("tipo_vehiculo", "=", tipo_vehiculo))
    if estado:
        filters.append(("estado", "=", estado))

    allowed = {
        "id_repartidor",
        "nombre",
        "tipo_vehiculo",
        "calificacion_promedio",
        "estado",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="repartidores",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_repartidor",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/categorias",
    response_model=PaginatedResponse[CategoriaPlatilloOut],
    summary="Listar categorías del menú y márgenes de contribución",
    description=(
        "### Categorías Gastronómicas del Menú\n\n"
        "Consulta las familias de productos culinarios ofertados por Antojitos Express "
        "(ej. Tacos, Hamburguesas, Bebidas, Postres) y su margen de contribución bruto porcentual."
    ),
    response_description="Colección paginada de categorías gastronómicas",
    responses={
        200: {"description": "Consulta exitosa de categorías de platillos."},
        422: {"description": "Error en los parámetros de paginación."},
    },
)
def get_categorias(
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-margen_contribucion_pct', 'nombre_categoria').",
            examples=["id_categoria", "-margen_contribucion_pct"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Cantidad máxima de registros por página.", examples=[50]),
    ] = 50,
):
    """Consulta las categorías gastronómicas y márgenes de contribución."""
    allowed = {"id_categoria", "nombre_categoria", "margen_contribucion_pct"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="categorias_platillo",
        allowed_sort_columns=allowed,
        default_sort="id_categoria",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/platillos",
    response_model=PaginatedResponse[PlatilloOut],
    summary="Listar catálogo de platillos del menú",
    description=(
        "### Catálogo de Platillos, Precios y Costos de Elaboración\n\n"
        "Consulta el menú completo de comidas preparadas con sus precios de venta en Córdobas (NIO), "
        "costo de insumos, tiempo estándar de cocción y requerimiento de horno industrial."
    ),
    response_description="Colección paginada de platillos con costos y tiempos de preparación",
    responses={
        200: {"description": "Consulta exitosa del menú de platillos."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_platillos(
    id_categoria: Annotated[
        int | None,
        Query(
            description="Filtrar platillos por identificador de categoría (ej. 1 para tacos).",
            examples=[1],
        ),
    ] = None,
    requiere_horno: Annotated[
        bool | None,
        Query(
            description="Filtrar por platillos que requieren uso de horno industrial.",
            examples=[True, False],
        ),
    ] = None,
    activo: Annotated[
        bool | None,
        Query(
            description="Filtrar únicamente platillos activos en la carta digital.",
            examples=[True],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-precio_unitario' para los más costosos).",
            examples=["precio_unitario", "-precio_unitario", "tiempo_preparacion_minutos"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Cantidad máxima de registros por página.", examples=[50]),
    ] = 50,
):
    """Consulta el catálogo de platillos del menú con costos de ingredientes y tiempos de preparación."""
    filters: list[tuple[str, str, Any]] = []
    if id_categoria:
        filters.append(("id_categoria", "=", id_categoria))
    if requiere_horno is not None:
        filters.append(("requiere_horno", "=", requiere_horno))
    if activo is not None:
        filters.append(("activo", "=", activo))

    allowed = {
        "id_platillo",
        "id_categoria",
        "nombre_platillo",
        "precio_unitario",
        "costo_ingredientes",
        "tiempo_preparacion_minutos",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="platillos",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_platillo",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/promociones",
    response_model=PaginatedResponse[PromocionOut],
    summary="Listar campañas de promociones y descuentos",
    description=(
        "### Campañas de Promociones y Presupuesto Publicitario\n\n"
        "Consulta las campañas de marketing diseñadas para impulsar las ventas, detallando el costo asignado, "
        "el retorno esperado en Córdobas (NIO), el porcentaje de descuento y las fechas de vigencia."
    ),
    response_description="Colección paginada de promociones comerciales",
    responses={
        200: {"description": "Consulta exitosa de promociones."},
        422: {"description": "Error en los parámetros de paginación."},
    },
)
def get_promociones(
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-retorno_esperado', 'costo_campana', '-descuento_pct').",
            examples=["id_promocion", "-retorno_esperado", "costo_campana"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Cantidad máxima de registros por página.", examples=[50]),
    ] = 50,
):
    """Campañas de promociones, presupuesto de marketing y descuentos aplicados."""
    allowed = {
        "id_promocion",
        "costo_campana",
        "retorno_esperado",
        "descuento_pct",
        "fecha_inicio",
        "fecha_fin",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="promociones",
        allowed_sort_columns=allowed,
        default_sort="id_promocion",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/clima",
    response_model=PaginatedResponse[ClimaDiarioOut],
    summary="Registro meteorológico diario en Managua",
    description=(
        "### Histórico Meteorológico de Managua\n\n"
        "Serie temporal diaria con precipitación en milímetros (mm), temperatura ambiente (°C) y condición del cielo. "
        "Registra las variables climáticas exógenas observadas en el área urbana de Managua."
    ),
    response_description="Serie meteorológica diaria en Managua",
    responses={
        200: {"description": "Consulta exitosa de registros climáticos."},
        422: {"description": "Error en el formato de fechas o parámetros de paginación."},
    },
)
def get_clima(
    fecha_desde: Annotated[
        date | None,
        Query(description="Fecha mínima de consulta en formato ISO (YYYY-MM-DD).", examples=["2024-01-01"]),
    ] = None,
    fecha_hasta: Annotated[
        date | None,
        Query(description="Fecha máxima de consulta en formato ISO (YYYY-MM-DD).", examples=["2024-12-31"]),
    ] = None,
    condicion_cielo: Annotated[
        str | None,
        Query(
            description="Filtrar por condición climática observada.",
            examples=["despejado", "lluvia_ligera", "tormenta", "nublado"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-precipitacion_mm' para días más lluviosos).",
            examples=["fecha", "-fecha", "-precipitacion_mm"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Cantidad máxima de registros por página.", examples=[50]),
    ] = 50,
):
    """Condiciones climáticas diarias en Managua (precipitación en mm y temperatura)."""
    filters: list[tuple[str, str, Any]] = []
    if fecha_desde:
        filters.append(("fecha", ">=", fecha_desde))
    if fecha_hasta:
        filters.append(("fecha", "<=", fecha_hasta))
    if condicion_cielo:
        filters.append(("condicion_cielo", "=", condicion_cielo))

    allowed = {"fecha", "precipitacion_mm", "temperatura_c", "condicion_cielo"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="clima_diario",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="fecha",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/ordenes",
    response_model=PaginatedResponse[OrdenOut],
    summary="Listar órdenes transaccionales de delivery",
    description=(
        "### Histórico Transaccional de Órdenes de Entrega\n\n"
        "Consulta los pedidos realizados en la plataforma gastronómica. Permite filtrar por zona de entrega, "
        "repartidor asignado, método de pago, estado del pedido y monto mínimo."
    ),
    response_description="Colección paginada de órdenes de delivery",
    responses={
        200: {"description": "Consulta exitosa de órdenes."},
        422: {"description": "Error en los parámetros de filtrado o formato de consulta."},
    },
)
def get_ordenes(
    id_zona: Annotated[
        int | None,
        Query(description="Filtrar por identificador de zona de entrega en Managua.", examples=[1]),
    ] = None,
    id_repartidor: Annotated[
        int | None,
        Query(description="Filtrar por identificador de repartidor asignado.", examples=[10]),
    ] = None,
    metodo_pago: Annotated[
        str | None,
        Query(
            description="Filtrar por método de pago empleado.",
            examples=["efectivo", "tarjeta", "billetera_digital"],
        ),
    ] = None,
    estado_orden: Annotated[
        str | None,
        Query(
            description="Filtrar por estado de la orden.",
            examples=["entregada", "cancelada", "en_camino", "preparando"],
        ),
    ] = None,
    total_min: Annotated[
        float | None,
        Query(
            ge=0,
            description="Filtrar órdenes con un importe total mayor o igual a este valor en Córdobas (NIO).",
            examples=[200.0],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-fecha_hora_creacion' para las más recientes).",
            examples=["-fecha_hora_creacion", "-total_orden", "costo_envio"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Cantidad máxima de registros por página.", examples=[50]),
    ] = 50,
):
    """Consulta el histórico transaccional de órdenes de comida rápida y delivery."""
    filters: list[tuple[str, str, Any]] = []
    if id_zona:
        filters.append(("id_zona", "=", id_zona))
    if id_repartidor:
        filters.append(("id_repartidor", "=", id_repartidor))
    if metodo_pago:
        filters.append(("metodo_pago", "=", metodo_pago))
    if estado_orden:
        filters.append(("estado_orden", "=", estado_orden))
    if total_min is not None:
        filters.append(("total_orden", ">=", total_min))

    allowed = {
        "id_orden",
        "fecha_hora_creacion",
        "total_orden",
        "costo_envio",
        "estado_orden",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="ordenes",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-fecha_hora_creacion",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/ordenes/{id_orden}",
    response_model=OrdenDetailOut,
    summary="Obtener orden por ID con detalle de platillos",
    description=(
        "### Ficha Detallada de una Orden con sus Platillos\n\n"
        "Recupera una orden específica por su clave primaria e incluye la lista anidada de ítems "
        "solicitados (`items`), con cantidades, precios unitarios y subtotales calculados."
    ),
    response_description="Detalle completo de la orden solicitada y sus platillos anidados",
    responses={
        200: {"description": "Orden encontrada exitosamente."},
        404: {"description": "La orden con el ID especificado no fue encontrada."},
        422: {"description": "El ID proporcionado no es un entero válido."},
    },
)
def get_orden_by_id(
    id_orden: Annotated[
        int,
        Path(
            ge=1,
            description="Identificador único numérico de la orden a consultar.",
            examples=[1],
        ),
    ],
):
    """Consulta una orden específica e incluye los ítems y platillos asociados."""
    orden = fetch_single_resource(SCHEMA, "ordenes", "id_orden", id_orden)
    items_sql = f"SELECT * FROM {SCHEMA}.detalle_ordenes WHERE id_orden = %s ORDER BY id_detalle ASC;"
    items_raw = fetch_all(items_sql, (id_orden,))
    orden["items"] = [sanitize_row(i) for i in items_raw]
    return orden


@router.get(
    "/detalles",
    response_model=PaginatedResponse[DetalleOrdenOut],
    summary="Listar líneas de detalle de platillos ordenados",
    description=(
        "### Líneas de Detalle de Canasta de Comida\n\n"
        "Consulta la tabla desagregada de platillos contenidos en las órdenes de compra. "
        "Permite filtrar por orden específica o por platillo particular."
    ),
    response_description="Colección paginada de líneas de detalle de pedidos",
    responses={
        200: {"description": "Consulta exitosa de líneas de detalle."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_detalles_orden(
    id_orden: Annotated[
        int | None,
        Query(description="Filtrar líneas de una orden específica.", examples=[1]),
    ] = None,
    id_platillo: Annotated[
        int | None,
        Query(description="Filtrar líneas que contengan un platillo específico.", examples=[101]),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'id_detalle', '-subtotal', '-cantidad').",
            examples=["id_detalle", "-subtotal", "-cantidad"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="Cantidad máxima de registros por página.", examples=[50]),
    ] = 50,
):
    """Consulta las líneas de detalle de platillos ordenados."""
    filters: list[tuple[str, str, Any]] = []
    if id_orden is not None:
        filters.append(("id_orden", "=", id_orden))
    if id_platillo is not None:
        filters.append(("id_platillo", "=", id_platillo))

    allowed = {"id_detalle", "id_orden", "id_platillo", "cantidad", "precio_unitario", "subtotal"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="detalle_ordenes",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_detalle",
        sort=sort,
        offset=offset,
        limit=limit,
    )
