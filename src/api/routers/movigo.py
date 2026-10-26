"""Routers for Caso 3: MoviGo (Transporte por Aplicación y Movilidad Urbana - Managua)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from src.api.schemas import (
    CampanaIncentivoOut,
    ClimaCuadranteOut,
    ConductorOut,
    PaginatedResponse,
    TelemetriaConductorOut,
    UsuarioOut,
    ViajeOut,
    ZonaUrbanaOut,
)
from src.api.utils import execute_paginated_query, fetch_single_resource

router = APIRouter(prefix="/movigo", tags=["Caso 3: MoviGo"])
SCHEMA = "raw_staging_movigo"


@router.get(
    "/zonas",
    response_model=PaginatedResponse[ZonaUrbanaOut],
    summary="Listar cuadrantes y zonas urbanas de Managua",
    description=(
        "### Zonificación Urbana y Tarifas de Bajada de Bandera\n\n"
        "Consulta la delimitación de cuadrantes en el área metropolitana de Managua (ej. Metrocentro, "
        "Plaza España, Villa Fontana, Carretera a Masaya). Contiene estrato socioeconómico, radio de cobertura "
        "y tarifa base de arranque (bajada de bandera) en Córdobas (NIO)."
    ),
    response_description="Colección paginada de cuadrantes urbanos y tarifas base",
    responses={
        200: {"description": "Consulta exitosa de zonas urbanas."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_zonas_movigo(
    estrato: Annotated[
        str | None,
        Query(
            description="Filtrar por estrato socioeconómico del cuadrante.",
            examples=["alto", "medio", "popular", "comercial"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'nombre_zona', '-tarifa_base_bajada_bandera').",
            examples=["nombre_zona", "estrato_socioeconomico", "-tarifa_base_bajada_bandera"],
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
    """Consulta la zonificación urbana de Managua y tarifas base de bajada de bandera."""
    filters: list[tuple[str, str, Any]] = []
    if estrato:
        filters.append(("estrato_socioeconomico", "=", estrato))

    allowed = {"id_zona", "nombre_zona", "estrato_socioeconomico", "radio_cobertura_km", "tarifa_base_bajada_bandera"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="zonas_urbanas",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_zona",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/usuarios",
    response_model=PaginatedResponse[UsuarioOut],
    summary="Listar pasajeros registrados en la plataforma",
    description=(
        "### Directorio de Pasajeros y Preferencias de Pago\n\n"
        "Consulta la base de clientes usuarios del servicio de transporte en Managua. "
        "Detalla métodos de pago preferidos, calificación promedio como pasajero y fecha de registro."
    ),
    response_description="Colección paginada de usuarios pasajeros",
    responses={
        200: {"description": "Consulta exitosa de usuarios pasajeros."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_usuarios(
    metodo_pago: Annotated[
        str | None,
        Query(
            description="Filtrar por método de pago configurado.",
            examples=["efectivo", "tarjeta", "billetera_digital"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-fecha_registro', '-calificacion_promedio').",
            examples=["-fecha_registro", "-calificacion_promedio"],
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
    """Consulta los perfiles y hábitos de pago de pasajeros en la aplicación."""
    filters: list[tuple[str, str, Any]] = []
    if metodo_pago:
        filters.append(("metodo_pago_preferido", "=", metodo_pago))

    allowed = {"id_usuario", "nombre", "metodo_pago_preferido", "calificacion_promedio", "fecha_registro"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="usuarios",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="fecha_registro",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/conductores",
    response_model=PaginatedResponse[ConductorOut],
    summary="Listar flota de socios conductores",
    description=(
        "### Directorio de Conductores y Unidades Vehiculares\n\n"
        "Consulta la flota de conductores afiliados a MoviGo clasificados por categoría de servicio "
        "(`movigo_estandar`, `movigo_comfort`, `movigo_moto`), incluyendo modelo y año del vehículo, "
        "matrícula, calificación promedio de pasajeros y tasa histórica de aceptación de carreras."
    ),
    response_description="Colección paginada de conductores y vehículos",
    responses={
        200: {"description": "Consulta exitosa de conductores."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_conductores(
    tipo_servicio: Annotated[
        str | None,
        Query(
            description="Filtrar por categoría del vehículo.",
            examples=["movigo_estandar", "movigo_comfort", "movigo_moto"],
        ),
    ] = None,
    estado: Annotated[
        str | None,
        Query(
            description="Filtrar por estado operativo actual.",
            examples=["activo", "inactivo", "en_viaje", "desconectado"],
        ),
    ] = None,
    calificacion_min: Annotated[
        float | None,
        Query(
            ge=1.0,
            le=5.0,
            description="Calificación promedio mínima (escala 1.0 a 5.0).",
            examples=[4.8],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-calificacion_promedio', '-tasa_aceptacion_pct').",
            examples=["-calificacion_promedio", "-tasa_aceptacion_pct", "anio_vehiculo"],
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
    """Consulta la flota de conductores, vehículos, calificación y tasa de aceptación."""
    filters: list[tuple[str, str, Any]] = []
    if tipo_servicio:
        filters.append(("tipo_servicio", "=", tipo_servicio))
    if estado:
        filters.append(("estado", "=", estado))
    if calificacion_min is not None:
        filters.append(("calificacion_promedio", ">=", calificacion_min))

    allowed = {"id_conductor", "nombre", "tipo_servicio", "calificacion_promedio", "tasa_aceptacion_pct", "estado"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="conductores",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_conductor",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/campanas",
    response_model=PaginatedResponse[CampanaIncentivoOut],
    summary="Listar campañas de bonos e incentivos",
    description=(
        "### Programas de Bonos e Incentivos a Conductores\n\n"
        "Consulta las campañas operativas destinadas a aumentar las horas de conexión de conductores durante "
        "horas pico, aguaceros o zonas de alta demanda. Detalla presupuesto en Córdobas (NIO) y el incremento esperado de horas."
    ),
    response_description="Colección paginada de campañas de incentivos",
    responses={
        200: {"description": "Consulta exitosa de campañas de bonos."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_campanas(
    tipo_incentivo: Annotated[
        str | None,
        Query(
            description="Filtrar por mecánica del incentivo.",
            examples=["meta_viajes", "hora_pico_lluvia", "zona_alta_demanda"],
        ),
    ] = None,
    estado: Annotated[
        str | None,
        Query(description="Filtrar por vigencia del programa.", examples=["activa", "finalizada"]),
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
    """Consulta los programas de incentivos y bonos para conductores."""
    filters: list[tuple[str, str, Any]] = []
    if tipo_incentivo:
        filters.append(("tipo_incentivo", "=", tipo_incentivo))
    if estado:
        filters.append(("estado", "=", estado))

    allowed = {"id_campana", "costo_presupuesto_nio", "tipo_incentivo", "fecha_inicio", "fecha_fin", "estado"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="campanas_incentivos",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="id_campana",
        offset=offset,
        limit=limit,
    )


@router.get(
    "/clima",
    response_model=PaginatedResponse[ClimaCuadranteOut],
    summary="Clima urbano e índice de congestión vial",
    description=(
        "### Monitoreo Meteorológico y Saturación Vial en Managua\n\n"
        "Series temporales de microclima que asocian la precipitación en milímetros (mm) y la temperatura (°C) "
        "con el índice de congestión del tráfico en Managua (escala 1.00 flujo libre hasta 3.50 colapso por lluvias)."
    ),
    response_description="Serie climática e índice de congestión en Managua",
    responses={
        200: {"description": "Consulta exitosa de registros climáticos y viales."},
        422: {"description": "Error en el formato de fechas o parámetros de paginación."},
    },
)
def get_clima_movigo(
    fecha_desde: Annotated[
        date | None,
        Query(description="Fecha mínima en formato ISO (YYYY-MM-DD).", examples=["2024-01-01"]),
    ] = None,
    fecha_hasta: Annotated[
        date | None,
        Query(description="Fecha máxima en formato ISO (YYYY-MM-DD).", examples=["2024-12-31"]),
    ] = None,
    condicion_cielo: Annotated[
        str | None,
        Query(
            description="Filtrar por condición climática observada.",
            examples=["despejado", "nublado", "lluvia_ligera", "tormenta"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'fecha', '-indice_congestion', '-precipitacion_mm').",
            examples=["fecha", "-fecha", "-indice_congestion"],
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
    """Series de microclima urbano e índice de congestión vial en Managua."""
    filters: list[tuple[str, str, Any]] = []
    if fecha_desde:
        filters.append(("fecha", ">=", fecha_desde))
    if fecha_hasta:
        filters.append(("fecha", "<=", fecha_hasta))
    if condicion_cielo:
        filters.append(("condicion_cielo", "=", condicion_cielo))

    allowed = {"fecha", "precipitacion_mm", "indice_congestion", "condicion_cielo"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="clima_cuadrantes",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="fecha",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/viajes",
    response_model=PaginatedResponse[ViajeOut],
    summary="Listar viajes en la plataforma y tarifas dinámicas",
    description=(
        "### Histórico Transaccional de Viajes Urbanos\n\n"
        "Consulta los viajes solicitados y completados en la plataforma MoviGo. Incluye origen, destino, "
        "distancia recorrida en kilómetros, duración en minutos, multiplicador dinámico (*surge pricing* de 1.0x a 2.8x), "
        "tarifa final en Córdobas (NIO), propinas y calificaciones bilaterales."
    ),
    response_description="Colección paginada de viajes urbanos transaccionales",
    responses={
        200: {"description": "Consulta exitosa de viajes."},
        422: {"description": "Error en los parámetros de filtrado o formato de consulta."},
    },
)
def get_viajes(
    id_zona_origen: Annotated[
        int | None,
        Query(description="Filtrar por cuadrante de origen en Managua.", examples=[1]),
    ] = None,
    id_zona_destino: Annotated[
        int | None,
        Query(description="Filtrar por cuadrante de destino en Managua.", examples=[4]),
    ] = None,
    id_conductor: Annotated[
        int | None,
        Query(description="Filtrar por conductor asignado.", examples=[205]),
    ] = None,
    id_usuario: Annotated[
        int | None,
        Query(description="Filtrar por usuario pasajero.", examples=[501]),
    ] = None,
    estado_viaje: Annotated[
        str | None,
        Query(
            description="Filtrar por estado del servicio.",
            examples=["completado", "cancelado_usuario", "cancelado_conductor", "no_asignado"],
        ),
    ] = None,
    metodo_pago: Annotated[
        str | None,
        Query(
            description="Filtrar por método de pago empleado.",
            examples=["efectivo", "tarjeta", "billetera_digital"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-fecha_hora_solicitud', '-tarifa_final', '-multiplicador_dinamico').",
            examples=["-fecha_hora_solicitud", "-tarifa_final", "duracion_minutos"],
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
    """Histórico transaccional de viajes urbanos, tarifas dinámicas y distancias."""
    filters: list[tuple[str, str, Any]] = []
    if id_zona_origen:
        filters.append(("id_zona_origen", "=", id_zona_origen))
    if id_zona_destino:
        filters.append(("id_zona_destino", "=", id_zona_destino))
    if id_conductor:
        filters.append(("id_conductor", "=", id_conductor))
    if id_usuario:
        filters.append(("id_usuario", "=", id_usuario))
    if estado_viaje:
        filters.append(("estado_viaje", "=", estado_viaje))
    if metodo_pago:
        filters.append(("metodo_pago", "=", metodo_pago))

    allowed = {
        "id_viaje",
        "fecha_hora_solicitud",
        "tiempo_espera_minutos",
        "distancia_km",
        "duracion_minutos",
        "tarifa_bajada_bandera",
        "cargo_distancia",
        "cargo_tiempo",
        "tarifa_base",
        "multiplicador_dinamico",
        "tarifa_final",
        "solicitudes_activas_origen",
        "conductores_disponibles_origen",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="viajes",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-fecha_hora_solicitud",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/viajes/{id_viaje}",
    response_model=ViajeOut,
    summary="Obtener detalle de viaje por ID",
    description=(
        "### Información Detallada de un Viaje en Particular\n\n"
        "Recupera la ficha de un viaje individual por su identificador único transaccional."
    ),
    response_description="Datos completos del viaje consultado",
    responses={
        200: {"description": "Viaje encontrado exitosamente."},
        404: {"description": "Viaje no encontrado. Verifique que el ID solicitado exista."},
        422: {"description": "El ID proporcionado no es un entero válido."},
    },
)
def get_viaje_by_id(
    id_viaje: Annotated[
        int,
        Path(ge=1, description="Identificador único numérico del viaje a consultar.", examples=[1]),
    ],
):
    """Consulta la información detallada de un viaje particular."""
    return fetch_single_resource(SCHEMA, "viajes", "id_viaje", id_viaje)


@router.get(
    "/telemetria",
    response_model=PaginatedResponse[TelemetriaConductorOut],
    summary="Listar registros de telemetría GPS vehicular",
    description=(
        "### Pings Telemétricos de Posición GPS y Velocidad\n\n"
        "Consulta la serie de datos telemétricos captados desde los teléfonos de los conductores en ruta. "
        "Registra latitud, longitud, velocidad instantánea en km/h y estado de disponibilidad en tiempo real."
    ),
    response_description="Colección paginada de registros telemétricos GPS",
    responses={
        200: {"description": "Consulta exitosa de registros de telemetría."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_telemetria(
    id_conductor: Annotated[
        int | None,
        Query(description="Filtrar por identificador de conductor monitoreado.", examples=[205]),
    ] = None,
    id_viaje: Annotated[
        int | None,
        Query(description="Filtrar por identificador de viaje asociado al recorrido GPS.", examples=[10042]),
    ] = None,
    id_zona: Annotated[
        int | None,
        Query(description="Filtrar por cuadrante urbano donde se emitió la señal.", examples=[1]),
    ] = None,
    estado_disponibilidad: Annotated[
        str | None,
        Query(
            description="Filtrar por estado del conductor en ese instante.",
            examples=["disponible", "ocupado", "en_camino_recogida"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-fecha_hora', '-velocidad_kmh').",
            examples=["-fecha_hora", "-velocidad_kmh"],
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
    """Datos telemétricos de conducción (velocidad, coordenadas, estado de disponibilidad)."""
    filters: list[tuple[str, str, Any]] = []
    if id_conductor:
        filters.append(("id_conductor", "=", id_conductor))
    if id_viaje:
        filters.append(("id_viaje", "=", id_viaje))
    if id_zona:
        filters.append(("id_zona", "=", id_zona))
    if estado_disponibilidad:
        filters.append(("estado_disponibilidad", "=", estado_disponibilidad))

    allowed = {"id_telemetria", "id_viaje", "fecha_hora", "velocidad_kmh"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="telemetria_conductores",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-fecha_hora",
        sort=sort,
        offset=offset,
        limit=limit,
    )
