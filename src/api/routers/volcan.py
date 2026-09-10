"""Routers for Caso 2: Cooperativa El Volcán (Café de Exportación de Altura - Jinotega / Matagalpa)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

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


@router.get(
    "/fincas",
    response_model=PaginatedResponse[FincaOut],
    summary="Listar fincas cafetaleras asociadas",
    description=(
        "### Catálogo de Fincas y Parcelas Productoras\n\n"
        "Consulta el registro de fincas cafetaleras vinculadas a la cooperativa en los departamentos "
        "de Jinotega, Matagalpa, Madriz y Nueva Segovia (zona Dipilto). "
        "Contiene información agronómica como altitud sobre el nivel del mar (`altitud_msnm`), "
        "extensión cultivada en manzanas y georreferenciación."
    ),
    response_description="Colección paginada de fincas cafetaleras asociadas",
    responses={
        200: {"description": "Consulta exitosa de fincas productoras."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_fincas(
    region: Annotated[
        str | None,
        Query(
            description="Filtrar por región cafetalera de Nicaragua.",
            examples=["Jinotega", "Matagalpa", "Nueva Segovia - Dipilto", "Madriz"],
        ),
    ] = None,
    municipio: Annotated[
        str | None,
        Query(description="Filtrar por municipio de ubicación.", examples=["San Rafael del Norte"]),
    ] = None,
    altitud_min: Annotated[
        int | None,
        Query(
            ge=800,
            le=2000,
            description="Altitud mínima sobre el nivel del mar en metros (msnm).",
            examples=[1200],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-altitud_msnm' para mayor altura, '-area_manzanas').",
            examples=["altitud_msnm", "-altitud_msnm", "-area_manzanas"],
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


@router.get(
    "/variedades",
    response_model=PaginatedResponse[VariedadCafeOut],
    summary="Listar variedades botánicas de café",
    description=(
        "### Catálogo de Variedades de Coffea Arabica\n\n"
        "Consulta las variedades cultivadas por los miembros de la cooperativa (Geisha, Pacamara, Bourbon, Caturra, "
        "Maragogipe, Catuaí), su resistencia fitopatológica a la roya y su rendimiento esperado en quintales por manzana (qq/mz)."
    ),
    response_description="Colección paginada de variedades botánicas de café",
    responses={
        200: {"description": "Consulta exitosa de variedades de café."},
        422: {"description": "Error en los parámetros de consulta."},
    },
)
def get_variedades(
    resistencia_roya: Annotated[
        str | None,
        Query(
            description="Filtrar por nivel de tolerancia a la roya.",
            examples=["alta", "media", "susceptible"],
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


@router.get(
    "/beneficios",
    response_model=PaginatedResponse[BeneficioOut],
    summary="Listar plantas de beneficio húmedo y seco",
    description=(
        "### Infraestructura Agroindustrial de Beneficiado\n\n"
        "Consulta las plantas de beneficio asociadas a la cooperativa para el despulpado, lavado y secado (beneficio húmedo) "
        "o trillado, pulido y ensacado de exportación (beneficio seco), con sus capacidades diarias y costos por quintal."
    ),
    response_description="Colección paginada de plantas de beneficio agroindustrial",
    responses={
        200: {"description": "Consulta exitosa de plantas de beneficio."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_beneficios(
    tipo_beneficio: Annotated[
        str | None,
        Query(
            description="Filtrar por tipo de proceso agroindustrial ('humedo' o 'seco').",
            examples=["humedo", "seco"],
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


@router.get(
    "/cuadrillas",
    response_model=PaginatedResponse[CuadrillaCorteOut],
    summary="Listar cuadrillas de recolección de café",
    description=(
        "### Cuadrillas de Corte y Recolección Manual\n\n"
        "Consulta los grupos de cortadores organizados para la cosecha del grano cereza en temporada alta. "
        "Detalla la dotación de recolectores, rendimiento promedio en latas por día y costo diario de jornales."
    ),
    response_description="Colección paginada de cuadrillas de corte",
    responses={
        200: {"description": "Consulta exitosa de cuadrillas de recolección."},
        422: {"description": "Error en los parámetros de consulta."},
    },
)
def get_cuadrillas(
    estado: Annotated[
        str | None,
        Query(
            description="Filtrar por disponibilidad operativa de la cuadrilla.",
            examples=["activa", "descanso", "asignada"],
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


@router.get(
    "/clima",
    response_model=PaginatedResponse[ClimaCafetaleroOut],
    summary="Clima y agroclimatología en zonas cafetaleras",
    description=(
        "### Monitoreo Agroclimático de Montaña (Jinotega / Matagalpa)\n\n"
        "Series meteorológicas de cordilleras cafetaleras que registran lluvia diaria en milímetros, "
        "temperaturas mínima/media/máxima (°C) y humedad relativa del aire (%). Variables biológicas fundamentales "
        "para la maduración del grano y el secado del café."
    ),
    response_description="Serie agroclimática en zonas cafetaleras del norte de Nicaragua",
    responses={
        200: {"description": "Consulta exitosa de registros agroclimáticos."},
        422: {"description": "Error en el formato de fechas o parámetros de paginación."},
    },
)
def get_clima_volcan(
    fecha_desde: Annotated[
        date | None,
        Query(description="Fecha mínima en formato ISO (YYYY-MM-DD).", examples=["2024-10-01"]),
    ] = None,
    fecha_hasta: Annotated[
        date | None,
        Query(description="Fecha máxima en formato ISO (YYYY-MM-DD).", examples=["2024-12-31"]),
    ] = None,
    region: Annotated[
        str | None,
        Query(description="Filtrar por región cafetalera.", examples=["Jinotega", "Matagalpa"]),
    ] = None,
    condicion_clima: Annotated[
        str | None,
        Query(
            description="Filtrar por condición climática observada.",
            examples=["soleado", "nublado", "llovizna", "temporal"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'fecha', '-precipitacion_mm').",
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


@router.get(
    "/lotes",
    response_model=PaginatedResponse[LoteAcopioOut],
    summary="Listar lotes de café cosechados y acopiados",
    description=(
        "### Lotes de Café en Cereza y Evaluación SCAA\n\n"
        "Consulta los lotes cosechados entregados en centros de acopio. Registra peso fresco en kilogramos, "
        "contenido de humedad, puntaje de catación según protocolo de la Specialty Coffee Association (SCAA) "
        "y sellos de certificación socioambiental (Fairtrade, Orgánico, Rainforest Alliance, SHG)."
    ),
    response_description="Colección paginada de lotes de café acopiados",
    responses={
        200: {"description": "Consulta exitosa de lotes de acopio."},
        422: {"description": "Error en los parámetros de filtrado o formato de fecha."},
    },
)
def get_lotes(
    fecha_desde: Annotated[
        date | None,
        Query(description="Fecha mínima de corte (YYYY-MM-DD).", examples=["2024-10-01"]),
    ] = None,
    fecha_hasta: Annotated[
        date | None,
        Query(description="Fecha máxima de corte (YYYY-MM-DD).", examples=["2024-12-31"]),
    ] = None,
    id_finca: Annotated[
        int | None,
        Query(description="Filtrar por identificador de la finca de origen.", examples=[1]),
    ] = None,
    id_variedad: Annotated[
        int | None,
        Query(description="Filtrar por identificador de la variedad de café.", examples=[1]),
    ] = None,
    certificacion: Annotated[
        str | None,
        Query(
            description="Filtrar por certificación del lote.",
            examples=["Convencional", "Fairtrade", "Orgánico", "Rainforest Alliance", "SHG"],
        ),
    ] = None,
    estado_lote: Annotated[
        str | None,
        Query(
            description="Filtrar por fase operativa del lote.",
            examples=["recolectado", "en_beneficio_humedo", "en_secado", "listo_exportacion", "descartado"],
        ),
    ] = None,
    scaa_min: Annotated[
        float | None,
        Query(
            ge=80.0,
            le=100.0,
            description="Puntaje mínimo de catación SCAA (ej. 85.0 para cafés de especialidad).",
            examples=[85.0],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-puntaje_catacion_scaa', '-peso_cereza_kg').",
            examples=["-fecha_corte", "-puntaje_catacion_scaa", "-peso_cereza_kg"],
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


@router.get(
    "/lotes/{id_lote}",
    response_model=LoteAcopioOut,
    summary="Obtener ficha técnica de lote de café por ID",
    description=(
        "### Ficha Técnica Completa del Lote de Café\n\n"
        "Recupera la información técnica, agronómica y de catación sensorial de un lote específico por su identificador único."
    ),
    response_description="Ficha técnica del lote de café consultado",
    responses={
        200: {"description": "Lote encontrado exitosamente."},
        404: {"description": "Lote no encontrado. Verifique que el ID solicitado exista."},
        422: {"description": "El ID proporcionado no es un entero válido."},
    },
)
def get_lote_by_id(
    id_lote: Annotated[
        int,
        Path(ge=1, description="Identificador único numérico del lote de café.", examples=[1]),
    ],
):
    """Consulta la ficha técnica completa de un lote específico."""
    return fetch_single_resource(SCHEMA, "lotes_acopio", "id_lote", id_lote)


@router.get(
    "/procesamiento",
    response_model=PaginatedResponse[ProcesamientoBeneficioOut],
    summary="Listar etapas de procesamiento en beneficios",
    description=(
        "### Transformación Agroindustrial y Control de Mermas\n\n"
        "Consulta las etapas de transformación por las que transita el café (despulpado, fermentación, "
        "secado en patio, trillado, clasificación), registrando temperaturas, fechas de inicio/fin y porcentaje de merma."
    ),
    response_description="Colección paginada de registros de procesamiento",
    responses={
        200: {"description": "Consulta exitosa de registros de procesamiento."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_procesamiento(
    id_lote: Annotated[
        int | None,
        Query(description="Filtrar por identificador del lote procesado.", examples=[1001]),
    ] = None,
    id_beneficio: Annotated[
        int | None,
        Query(description="Filtrar por identificador de la planta de beneficio.", examples=[1]),
    ] = None,
    etapa: Annotated[
        str | None,
        Query(
            description="Filtrar por etapa técnica agroindustrial.",
            examples=["despulpado", "fermentacion", "secado_patio", "trillado", "clasificacion"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-fecha_inicio', '-merma_porcentaje').",
            examples=["-fecha_inicio", "merma_porcentaje"],
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


@router.get(
    "/subastas",
    response_model=PaginatedResponse[SubastaEspecialOut],
    summary="Listar microlotes en subastas internacionales",
    description=(
        "### Subastas de Café de Especialidad (Taza de la Excelencia)\n\n"
        "Consulta los microlotes de alta puntuación en taza postulados a subastas electrónicas internacionales. "
        "Contiene el volumen en quintales oro, costo de inscripción/certificación en USD y retorno esperado."
    ),
    response_description="Colección paginada de microlotes en subastas",
    responses={
        200: {"description": "Consulta exitosa de subastas especiales."},
        422: {"description": "Error en los parámetros de paginación."},
    },
)
def get_subastas(
    estado_subasta: Annotated[
        str | None,
        Query(
            description="Filtrar por resultado de la subasta.",
            examples=["programada", "adjudicada", "desierta"],
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


@router.get(
    "/embarques",
    response_model=PaginatedResponse[EmbarqueExportacionOut],
    summary="Listar embarques marítimos de exportación",
    description=(
        "### Logística y Despachos Marítimos de Exportación\n\n"
        "Consulta las órdenes de exportación marítima zarpadas por Puerto Corinto hacia tostadores en Alemania, "
        "Estados Unidos, Japón, Bélgica, Taiwán e Italia. Detalla volumen en quintales oro, precio por quintal en USD, "
        "costo de flete y facturación total."
    ),
    response_description="Colección paginada de despachos de exportación marítima",
    responses={
        200: {"description": "Consulta exitosa de embarques de exportación."},
        422: {"description": "Error en los parámetros de filtrado o formato de fechas."},
    },
)
def get_embarques(
    pais_destino: Annotated[
        str | None,
        Query(
            description="Filtrar por país comprador de destino.",
            examples=["Alemania", "Estados Unidos", "Japón", "Bélgica", "Taiwán", "Italia"],
        ),
    ] = None,
    puerto_salida: Annotated[
        str | None,
        Query(description="Filtrar por puerto de salida nacional.", examples=["Puerto Corinto, Nicaragua"]),
    ] = None,
    fecha_desde: Annotated[
        date | None,
        Query(description="Fecha mínima de embarque en formato ISO (YYYY-MM-DD).", examples=["2024-01-01"]),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-fecha_embarque', '-total_usd', '-peso_oro_quintales').",
            examples=["-fecha_embarque", "-total_usd", "peso_oro_quintales"],
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
