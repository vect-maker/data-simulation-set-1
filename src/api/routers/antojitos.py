"""Routers for Caso 1: Antojitos Express (Cocina Fantasma / Delivery en Managua)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

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
    summary="Listar zonas de Managua",
)
def get_zonas(
    sort: Annotated[
        str | None,
        Query(description="Ordenar por campo, ej: distancia_km o -distancia_km"),
    ] = None,
    offset: Annotated[int, Query(ge=0, description="Desplazamiento / offset")] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description="Límite de registros")] = 50,
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
    summary="Listar flota de repartidores",
)
def get_repartidores(
    tipo_vehiculo: Annotated[
        str | None,
        Query(description="Filtrar por moto, bicicleta, auto"),
    ] = None,
    estado: Annotated[
        str | None,
        Query(description="Filtrar por activo, inactivo, descanso"),
    ] = None,
    sort: Annotated[
        str | None,
        Query(description="Ordenar por calificacion_promedio, etc."),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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
    summary="Listar categorías de platillos",
)
def get_categorias(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta las categorías gastronómicas y márgenes de contribución."""
    allowed = {"id_categoria", "nombre_categoria", "margen_contribucion_pct"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="categorias_platillo",
        allowed_sort_columns=allowed,
        default_sort="id_categoria",
        offset=offset,
        limit=limit,
    )


@router.get(
    "/platillos",
    response_model=PaginatedResponse[PlatilloOut],
    summary="Listar menú de platillos",
)
def get_platillos(
    id_categoria: Annotated[int | None, Query(description="Filtrar por ID de categoría")] = None,
    requiere_horno: Annotated[
        bool | None,
        Query(description="Filtrar por requerimiento de horno"),
    ] = None,
    activo: Annotated[bool | None, Query(description="Filtrar platillos activos")] = None,
    sort: Annotated[
        str | None,
        Query(description="Ordenar por precio_unitario o -precio_unitario"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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
    summary="Listar promociones y descuentos",
)
def get_promociones(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Campañas de promociones, presupuesto de marketing y descuentos aplicados."""
    allowed = {"id_promocion", "fecha_inicio", "fecha_fin", "descuento_pct"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="promociones",
        allowed_sort_columns=allowed,
        default_sort="id_promocion",
        offset=offset,
        limit=limit,
    )


@router.get(
    "/clima",
    response_model=PaginatedResponse[ClimaDiarioOut],
    summary="Registro meteorológico diario",
)
def get_clima(
    fecha_desde: Annotated[date | None, Query(description="Fecha mínima YYYY-MM-DD")] = None,
    fecha_hasta: Annotated[date | None, Query(description="Fecha máxima YYYY-MM-DD")] = None,
    condicion_cielo: Annotated[
        str | None,
        Query(description="despejado, lluvia_ligera, tormenta, nublado"),
    ] = None,
    sort: Annotated[
        str | None,
        Query(description="Ordenar por fecha o precipitación (-precipitacion_mm)"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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
    summary="Listar órdenes de delivery",
)
def get_ordenes(
    id_zona: Annotated[int | None, Query(description="Filtrar por ID de zona")] = None,
    id_repartidor: Annotated[
        int | None,
        Query(description="Filtrar por repartidor asignado"),
    ] = None,
    metodo_pago: Annotated[
        str | None,
        Query(description="efectivo, tarjeta, billetera_digital"),
    ] = None,
    estado_orden: Annotated[
        str | None,
        Query(description="entregada, cancelada, en_camino, preparando"),
    ] = None,
    total_min: Annotated[float | None, Query(description="Total mínimo de la orden")] = None,
    sort: Annotated[
        str | None,
        Query(description="Ordenar por fecha_hora_creacion, -total_orden, etc."),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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
    summary="Obtener orden por ID con sus platillos",
)
def get_orden_by_id(id_orden: int):
    """Consulta una orden específica e incluye los ítems y platillos asociados."""
    orden = fetch_single_resource(SCHEMA, "ordenes", "id_orden", id_orden)
    items_sql = f"SELECT * FROM {SCHEMA}.detalle_ordenes WHERE id_orden = %s ORDER BY id_detalle ASC;"
    items_raw = fetch_all(items_sql, (id_orden,))
    orden["items"] = [sanitize_row(i) for i in items_raw]
    return orden


@router.get(
    "/detalles",
    response_model=PaginatedResponse[DetalleOrdenOut],
    summary="Listar detalles de órdenes",
)
def get_detalles_orden(
    id_orden: Annotated[int | None, Query(description="Filtrar por orden específica")] = None,
    id_platillo: Annotated[
        int | None,
        Query(description="Filtrar por platillo específico"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta las líneas de detalle de platillos ordenados."""
    filters: list[tuple[str, str, Any]] = []
    if id_orden:
        filters.append(("id_orden", "=", id_orden))
    if id_platillo:
        filters.append(("id_platillo", "=", id_platillo))

    allowed = {"id_detalle", "id_orden", "id_platillo", "cantidad", "subtotal"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="detalle_ordenes",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_detalle",
        offset=offset,
        limit=limit,
    )
