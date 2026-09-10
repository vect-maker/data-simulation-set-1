"""Routers for Caso 2: Cooperativa El Volcán (Café de Exportación de Altura - Jinotega / Matagalpa)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from src.api.schemas import (
    BeneficioOut,
    ClimaCafetaleroOut,
    CuadrillaCorteOut,
    EmbarqueExportacionOut,
    FincaOut,
    LoteAcopioOut,
    PaginatedResponse,
    ProcesamientoBeneficioOut,
    SubastaEspecialOut,
    VariedadCafeOut,
)
from src.api.utils import execute_paginated_query, fetch_single_resource

router = APIRouter(prefix="/volcan", tags=["Caso 2: Cooperativa El Volcán"])
SCHEMA = "raw_staging_volcan"


@router.get("/fincas", response_model=PaginatedResponse[FincaOut], summary="Listar fincas productoras de café")
def get_fincas(
    region: Annotated[str | None, Query(description="Filtrar por Jinotega, Matagalpa, Nueva Segovia - Dipilto, Madriz")] = None,
    municipio: Annotated[str | None, Query(description="Filtrar por municipio")] = None,
    altitud_min: Annotated[int | None, Query(description="Altitud mínima en msnm")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por altitud_msnm o area_manzanas")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta el registro de fincas cafetaleras asociadas a la cooperativa."""
    filters: list[tuple[str, str, Any]] = []
    if region:
        filters.append(("region", "=", region))
    if municipio:
        filters.append(("municipio", "=", municipio))
    if altitud_min is not None:
        filters.append(("altitud_msnm", ">=", altitud_min))

    allowed = {"id_finca", "nombre_finca", "region", "altitud_msnm", "area_manzanas"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="fincas",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="altitud_msnm",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/variedades", response_model=PaginatedResponse[VariedadCafeOut], summary="Listar variedades botánicas de café")
def get_variedades(
    resistencia_roya: Annotated[str | None, Query(description="alta, media, susceptible")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta el catálogo de variedades botánicas de café cultivadas."""
    filters: list[tuple[str, str, Any]] = []
    if resistencia_roya:
        filters.append(("resistencia_roya", "=", resistencia_roya))

    allowed = {"id_variedad", "nombre_variedad", "resistencia_roya", "rendimiento_promedio_qq_mz"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="variedades_cafe",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_variedad",
        offset=offset,
        limit=limit,
    )


@router.get("/beneficios", response_model=PaginatedResponse[BeneficioOut], summary="Listar beneficios húmedos y secos")
def get_beneficios(
    tipo_beneficio: Annotated[str | None, Query(description="humedo, seco")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta la infraestructura de procesamiento de beneficio de café."""
    filters: list[tuple[str, str, Any]] = []
    if tipo_beneficio:
        filters.append(("tipo_beneficio", "=", tipo_beneficio))

    allowed = {"id_beneficio", "nombre_beneficio", "tipo_beneficio", "capacidad_quintales_dia"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="beneficios",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_beneficio",
        offset=offset,
        limit=limit,
    )


@router.get("/cuadrillas", response_model=PaginatedResponse[CuadrillaCorteOut], summary="Listar cuadrillas de recolección")
def get_cuadrillas(
    estado: Annotated[str | None, Query(description="activa, descanso, asignada")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta las cuadrillas de recolectores para la cosecha de café."""
    filters: list[tuple[str, str, Any]] = []
    if estado:
        filters.append(("estado", "=", estado))

    allowed = {"id_cuadrilla", "capacidad_recolectores", "rendimiento_latas_dia", "costo_jornal_dia", "estado"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="cuadrillas_corte",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_cuadrilla",
        offset=offset,
        limit=limit,
    )


@router.get("/clima", response_model=PaginatedResponse[ClimaCafetaleroOut], summary="Clima en zonas cafetaleras")
def get_clima_volcan(
    fecha_desde: Annotated[date | None, Query(description="Fecha inicio YYYY-MM-DD")] = None,
    fecha_hasta: Annotated[date | None, Query(description="Fecha fin YYYY-MM-DD")] = None,
    region: Annotated[str | None, Query(description="Filtrar por región")] = None,
    condicion_clima: Annotated[str | None, Query(description="soleado, nublado, llovizna, temporal")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha o precipitación")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Series meteorológicas agropecuarias en las cordilleras cafetaleras de Jinotega."""
    filters: list[tuple[str, str, Any]] = []
    if fecha_desde:
        filters.append(("fecha", ">=", fecha_desde))
    if fecha_hasta:
        filters.append(("fecha", "<=", fecha_hasta))
    if region:
        filters.append(("region", "=", region))
    if condicion_clima:
        filters.append(("condicion_clima", "=", condicion_clima))

    allowed = {"fecha", "precipitacion_mm", "temperatura_media_c", "humedad_relativa_pct"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="clima_zonas_cafetaleras",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="fecha",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/lotes", response_model=PaginatedResponse[LoteAcopioOut], summary="Listar lotes de café cosechados")
def get_lotes(
    fecha_desde: Annotated[date | None, Query(description="Fecha mínima de corte")] = None,
    fecha_hasta: Annotated[date | None, Query(description="Fecha máxima de corte")] = None,
    id_finca: Annotated[int | None, Query(description="Filtrar por finca de origen")] = None,
    id_variedad: Annotated[int | None, Query(description="Filtrar por variedad")] = None,
    certificacion: Annotated[str | None, Query(description="Convencional, Fairtrade, Orgánico, Rainforest Alliance, SHG")] = None,
    estado_lote: Annotated[str | None, Query(description="recolectado, en_beneficio_humedo, en_secado, listo_exportacion, descartado")] = None,
    scaa_min: Annotated[float | None, Query(description="Puntaje de catación SCAA mínimo")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha_corte, -peso_cereza_kg, -puntaje_catacion_scaa")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta los lotes cosechados y entregados en centros de acopio."""
    filters: list[tuple[str, str, Any]] = []
    if fecha_desde:
        filters.append(("fecha_corte", ">=", fecha_desde))
    if fecha_hasta:
        filters.append(("fecha_corte", "<=", fecha_hasta))
    if id_finca:
        filters.append(("id_finca", "=", id_finca))
    if id_variedad:
        filters.append(("id_variedad", "=", id_variedad))
    if certificacion:
        filters.append(("certificacion", "=", certificacion))
    if estado_lote:
        filters.append(("estado_lote", "=", estado_lote))
    if scaa_min is not None:
        filters.append(("puntaje_catacion_scaa", ">=", scaa_min))

    allowed = {"id_lote", "fecha_corte", "peso_cereza_kg", "humedad_porcentaje", "puntaje_catacion_scaa", "costo_recoleccion_nio"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="lotes_acopio",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-fecha_corte",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/lotes/{id_lote}", response_model=LoteAcopioOut, summary="Obtener lote de café por ID")
def get_lote_by_id(id_lote: int):
    """Consulta la ficha técnica completa de un lote específico."""
    return fetch_single_resource(SCHEMA, "lotes_acopio", "id_lote", id_lote)


@router.get("/procesamiento", response_model=PaginatedResponse[ProcesamientoBeneficioOut], summary="Procesamiento en beneficios")
def get_procesamiento(
    id_lote: Annotated[int | None, Query(description="Filtrar por lote")] = None,
    id_beneficio: Annotated[int | None, Query(description="Filtrar por beneficio")] = None,
    etapa: Annotated[str | None, Query(description="despulpado, fermentacion, secado_patio, trillado, clasificacion")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha_inicio o merma_porcentaje")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Registro de transformaciones, secado y evaluación del café en beneficios."""
    filters: list[tuple[str, str, Any]] = []
    if id_lote:
        filters.append(("id_lote", "=", id_lote))
    if id_beneficio:
        filters.append(("id_beneficio", "=", id_beneficio))
    if etapa:
        filters.append(("etapa", "=", etapa))

    allowed = {"id_proceso", "etapa", "merma_porcentaje", "peso_salida_kg", "fecha_inicio"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="procesamiento_beneficio",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-fecha_inicio",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/subastas", response_model=PaginatedResponse[SubastaEspecialOut], summary="Subastas de microlotes especiales")
def get_subastas(
    estado_subasta: Annotated[str | None, Query(description="programada, adjudicada, desierta")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta de subastas internacionales de café de especialidad."""
    filters: list[tuple[str, str, Any]] = []
    if estado_subasta:
        filters.append(("estado_subasta", "=", estado_subasta))

    allowed = {"id_subasta", "nombre_lote_especial", "peso_quintales", "puntaje_taza", "fecha_subasta"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="subastas_especiales",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-fecha_subasta",
        offset=offset,
        limit=limit,
    )


@router.get("/embarques", response_model=PaginatedResponse[EmbarqueExportacionOut], summary="Embarques marítimos de exportación")
def get_embarques(
    pais_destino: Annotated[str | None, Query(description="País comprador")] = None,
    puerto_salida: Annotated[str | None, Query(description="Puerto de salida")] = None,
    fecha_desde: Annotated[date | None, Query(description="Fecha mínima de embarque")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha_embarque o -total_usd")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Consulta de exportaciones y despachos marítimos hacia mercados internacionales."""
    filters: list[tuple[str, str, Any]] = []
    if pais_destino:
        filters.append(("pais_destino", "=", pais_destino))
    if puerto_salida:
        filters.append(("puerto_salida", "=", puerto_salida))
    if fecha_desde:
        filters.append(("fecha_embarque", ">=", fecha_desde))

    allowed = {"id_embarque", "pais_destino", "peso_oro_quintales", "total_usd", "fecha_embarque"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="embarques_exportacion",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-fecha_embarque",
        sort=sort,
        offset=offset,
        limit=limit,
    )
