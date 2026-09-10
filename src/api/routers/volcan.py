"""Routers for Caso 2: Cooperativa El Volcán (Café de Exportación de Altura - Jinotega / Matagalpa)."""

from datetime import date
from typing import Optional
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
    region: Optional[str] = Query(None, description="Filtrar por Jinotega, Matagalpa, Nueva Segovia - Dipilto, Madriz"),
    municipio: Optional[str] = Query(None, description="Filtrar por municipio"),
    altitud_min: Optional[int] = Query(None, description="Altitud mínima en msnm"),
    sort: Optional[str] = Query(None, description="Ordenar por altitud_msnm o area_manzanas"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Consulta el registro de fincas cafetaleras asociadas a la cooperativa."""
    filters = []
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
    resistencia_roya: Optional[str] = Query(None, description="alta, media, susceptible"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Consulta el catálogo de variedades botánicas de café cultivadas."""
    filters = []
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
    tipo_beneficio: Optional[str] = Query(None, description="humedo, seco"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Consulta la infraestructura de procesamiento de beneficio de café."""
    filters = []
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
    estado: Optional[str] = Query(None, description="activa, descanso, asignada"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Consulta las cuadrillas de recolectores para la cosecha de café."""
    filters = []
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
    fecha_desde: Optional[date] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha fin YYYY-MM-DD"),
    sort: Optional[str] = Query(None, description="Ordenar por fecha o precipitación"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Series meteorológicas agropecuarias en las cordilleras cafetaleras de Jinotega."""
    filters = []
    if fecha_desde:
        filters.append(("fecha", ">=", fecha_desde))
    if fecha_hasta:
        filters.append(("fecha", "<=", fecha_hasta))

    allowed = {"fecha", "precipitacion_mm", "temperatura_media_c"}
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
    fecha_desde: Optional[date] = Query(None, description="Fecha mínima de corte"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha máxima de corte"),
    id_finca: Optional[str] = Query(None, description="Filtrar por finca de origen"),
    id_variedad: Optional[str] = Query(None, description="Filtrar por variedad"),
    estado_lote: Optional[str] = Query(None, description="acopiado, en_beneficio, listo_embarque, exportado"),
    sort: Optional[str] = Query(None, description="Ordenar por fecha_corte, -peso_cereza_kg"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Consulta los lotes cosechados y entregados en centros de acopio."""
    filters = []
    if fecha_desde:
        filters.append(("fecha_corte", ">=", fecha_desde))
    if fecha_hasta:
        filters.append(("fecha_corte", "<=", fecha_hasta))
    if id_finca:
        filters.append(("id_finca", "=", id_finca))
    if id_variedad:
        filters.append(("id_variedad", "=", id_variedad))
    if estado_lote:
        filters.append(("estado_lote", "=", estado_lote))

    allowed = {"id_lote", "fecha_corte", "peso_cereza_kg", "humedad_porcentaje", "puntaje_catacion_scaa", "precio_liquidado_qq_usd"}
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
def get_lote_by_id(id_lote: str):
    """Consulta la ficha técnica completa de un lote específico."""
    return fetch_single_resource(SCHEMA, "lotes_acopio", "id_lote", id_lote)


@router.get("/procesamiento", response_model=PaginatedResponse[ProcesamientoBeneficioOut], summary="Procesamiento en beneficios")
def get_procesamiento(
    id_lote: Optional[str] = Query(None, description="Filtrar por lote"),
    id_beneficio: Optional[str] = Query(None, description="Filtrar por beneficio"),
    tipo_etapa: Optional[str] = Query(None, description="despulpado, fermentacion, lavado, secado, trillado"),
    estado_proceso: Optional[str] = Query(None, description="iniciado, en_proceso, completado"),
    sort: Optional[str] = Query(None, description="Ordenar por fecha_inicio o merma_porcentaje"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Registro de transformaciones, secado y evaluación del café en beneficios."""
    filters = []
    if id_lote:
        filters.append(("id_lote", "=", id_lote))
    if id_beneficio:
        filters.append(("id_beneficio", "=", id_beneficio))
    if tipo_etapa:
        filters.append(("tipo_etapa", "=", tipo_etapa))
    if estado_proceso:
        filters.append(("estado_proceso", "=", estado_proceso))

    allowed = {"id_proceso", "tipo_etapa", "peso_entrada_qq", "merma_porcentaje", "fecha_inicio"}
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Consulta de subastas internacionales de café de especialidad."""
    allowed = {"id_subasta", "nombre_evento", "peso_quintales", "puntaje_catacion_minimo", "fecha_evento"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="subastas_especiales",
        allowed_sort_columns=allowed,
        default_sort="-fecha_evento",
        offset=offset,
        limit=limit,
    )


@router.get("/embarques", response_model=PaginatedResponse[EmbarqueExportacionOut], summary="Embarques marítimos de exportación")
def get_embarques(
    pais_destino: Optional[str] = Query(None, description="País comprador"),
    puerto_destino: Optional[str] = Query(None, description="Puerto de destino"),
    fecha_desde: Optional[date] = Query(None, description="Fecha mínima de embarque"),
    sort: Optional[str] = Query(None, description="Ordenar por fecha_embarque o -total_usd"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Consulta de exportaciones y despachos marítimos hacia mercados internacionales."""
    filters = []
    if pais_destino:
        filters.append(("pais_destino", "=", pais_destino))
    if puerto_destino:
        filters.append(("puerto_destino", "=", puerto_destino))
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
