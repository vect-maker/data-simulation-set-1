"""Routers for Caso 3: MoviGo (Transporte por Aplicación y Movilidad Urbana - Managua)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from src.api.schemas import (
    DriverOut,
    DriverTelemetryOut,
    IncentiveCampaignOut,
    PaginatedResponse,
    QuadrantOut,
    QuadrantWeatherOut,
    TripOut,
    UrbanZoneOut,
    UserOut,
)
from src.api.utils import execute_paginated_query, fetch_single_resource

router = APIRouter(prefix="/movigo", tags=["Caso 3: MoviGo"])
SCHEMA = "raw_staging_movigo"


@router.get(
    "/quadrants",
    response_model=PaginatedResponse[QuadrantOut],
    summary="Listar grilla de cuadrantes cuadrados de Managua",
    description=(
        "### Grilla Fina de Cuadrantes Cuadrados (~0.88 km × 0.88 km), Altitud y Vulnerabilidad a Cauces\n\n"
        "Consulta los 92 cuadrantes cuadrados contiguos que cubren el 100% de la red vial de Managua y se agrupan "
        "dentro de las 12 zonas urbanas (`zone_id`), con sus límites (`lat_min`, `lat_max`, `lon_min`, `lon_max`), "
        "altitud media (`mean_altitude_masl`), nivel de riesgo de inundación (`flood_risk`) y cauces pluviales principales."
    ),
    response_description="Colección paginada de cuadrantes cuadrados geográficos",
    responses={
        200: {"description": "Consulta exitosa de cuadrantes."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_quadrants_movigo(
    zone_id: Annotated[
        int | None,
        Query(ge=1, le=12, description="Filtrar por zona urbana padre (1 a 12).", examples=[11]),
    ] = None,
    flood_risk: Annotated[
        str | None,
        Query(
            description="Filtrar por nivel de vulnerabilidad a inundaciones.",
            examples=["bajo", "medio", "alto", "critico"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'quadrant_id', 'zone_id', '-mean_altitude_masl').",
            examples=["quadrant_id", "zone_id", "-mean_altitude_masl"],
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
    """Consulta la grilla de 92 cuadrantes cuadrados geográficos e hidrológicos de Managua."""
    filters: list[tuple[str, str, Any]] = []
    if zone_id is not None:
        filters.append(("zone_id", "=", zone_id))
    if flood_risk:
        filters.append(("flood_risk", "=", flood_risk))

    allowed = {
        "quadrant_id",
        "zone_id",
        "quadrant_code",
        "quadrant_name",
        "grid_row",
        "grid_col",
        "mean_altitude_masl",
        "flood_risk",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="quadrants",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="quadrant_id",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/zones",
    response_model=PaginatedResponse[UrbanZoneOut],
    summary="Listar zonas urbanas de Managua",
    description=(
        "### Zonificación Urbana y Tarifas de Bajada de Bandera\n\n"
        "Consulta las 12 zonas urbanas comerciales del área metropolitana de Managua (ej. Metrocentro, "
        "Villa Fontana, Mercado Oriental, Roberto Huembes) que agrupan los 92 cuadrantes cuadrados. "
        "Contiene estrato socioeconómico (`socioeconomic_stratum`), radio de cobertura (`coverage_radius_km`) y tarifa base de arranque en Córdobas (`base_flag_drop_fare`)."
    ),
    response_description="Colección paginada de zonas urbanas y tarifas base",
    responses={
        200: {"description": "Consulta exitosa de zonas urbanas."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_zones_movigo(
    socioeconomic_stratum: Annotated[
        str | None,
        Query(
            description="Filtrar por estrato socioeconómico de la zona urbana.",
            examples=["alto", "medio", "popular", "comercial"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'zone_name', '-base_flag_drop_fare').",
            examples=["zone_name", "socioeconomic_stratum", "-base_flag_drop_fare"],
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
    if socioeconomic_stratum:
        filters.append(("socioeconomic_stratum", "=", socioeconomic_stratum))

    allowed = {"zone_id", "zone_name", "socioeconomic_stratum", "coverage_radius_km", "base_flag_drop_fare"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="urban_zones",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="zone_id",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/users",
    response_model=PaginatedResponse[UserOut],
    summary="Listar pasajeros registrados en la plataforma",
    description=(
        "### Directorio de Pasajeros y Preferencias de Pago\n\n"
        "Consulta la base de clientes usuarios del servicio de transporte en Managua. "
        "Detalla métodos de pago preferidos (`preferred_payment_method`), calificación promedio como pasajero (`average_rating`) y fecha de registro (`registration_date`)."
    ),
    response_description="Colección paginada de usuarios pasajeros",
    responses={
        200: {"description": "Consulta exitosa de usuarios pasajeros."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_users(
    preferred_payment_method: Annotated[
        str | None,
        Query(
            description="Filtrar por método de pago configurado.",
            examples=["efectivo", "tarjeta", "billetera_digital"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-registration_date', '-average_rating').",
            examples=["-registration_date", "-average_rating"],
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
    if preferred_payment_method:
        filters.append(("preferred_payment_method", "=", preferred_payment_method))

    allowed = {"user_id", "name", "preferred_payment_method", "average_rating", "registration_date"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="users",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="registration_date",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/drivers",
    response_model=PaginatedResponse[DriverOut],
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
def get_drivers(
    service_type: Annotated[
        str | None,
        Query(
            description="Filtrar por categoría del vehículo.",
            examples=["movigo_estandar", "movigo_comfort", "movigo_moto"],
        ),
    ] = None,
    status: Annotated[
        str | None,
        Query(
            description="Filtrar por estado operativo actual.",
            examples=["activo", "inactivo", "en_viaje", "desconectado"],
        ),
    ] = None,
    min_rating: Annotated[
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
            description="Campo de ordenamiento (ej. '-average_rating', '-acceptance_rate_pct').",
            examples=["-average_rating", "-acceptance_rate_pct", "vehicle_year"],
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
    if service_type:
        filters.append(("service_type", "=", service_type))
    if status:
        filters.append(("status", "=", status))
    if min_rating is not None:
        filters.append(("average_rating", ">=", min_rating))

    allowed = {"driver_id", "name", "service_type", "vehicle_year", "average_rating", "acceptance_rate_pct", "status"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="drivers",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="driver_id",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/campaigns",
    response_model=PaginatedResponse[IncentiveCampaignOut],
    summary="Listar campañas de bonos e incentivos",
    description=(
        "### Programas de Bonos e Incentivos a Conductores\n\n"
        "Consulta las campañas operativas destinadas a aumentar las horas de conexión de conductores durante "
        "horas pico, aguaceros o zonas de alta demanda. Detalla presupuesto en Córdobas (`budget_cost_nio`) y el incremento esperado de horas (`online_hours_increase`)."
    ),
    response_description="Colección paginada de campañas de incentivos",
    responses={
        200: {"description": "Consulta exitosa de campañas de bonos."},
        422: {"description": "Error en los parámetros de consulta o paginación."},
    },
)
def get_campaigns(
    incentive_type: Annotated[
        str | None,
        Query(
            description="Filtrar por mecánica del incentivo.",
            examples=["meta_viajes", "hora_pico_lluvia", "zona_alta_demanda"],
        ),
    ] = None,
    status: Annotated[
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
    if incentive_type:
        filters.append(("incentive_type", "=", incentive_type))
    if status:
        filters.append(("status", "=", status))

    allowed = {"campaign_id", "budget_cost_nio", "incentive_type", "start_date", "end_date", "status"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="incentive_campaigns",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="campaign_id",
        offset=offset,
        limit=limit,
    )


@router.get(
    "/weather",
    response_model=PaginatedResponse[QuadrantWeatherOut],
    summary="Clima urbano e índice de congestión vial por cuadrante",
    description=(
        "### Monitoreo Meteorológico y Saturación Vial en Managua\n\n"
        "Series temporales horarias de microclima que asocian la precipitación en milímetros (`precipitation_mm`), escorrentía de cauces (`channel_runoff_mm`) "
        "y temperatura (`temperature_c`) con el índice de congestión del tráfico en Managua (`congestion_index`)."
    ),
    response_description="Serie climática e índice de congestión en Managua",
    responses={
        200: {"description": "Consulta exitosa de registros climáticos y viales."},
        422: {"description": "Error en el formato de fechas o parámetros de paginación."},
    },
)
def get_weather_movigo(
    quadrant_id: Annotated[
        int | None,
        Query(ge=1, le=92, description="Filtrar por cuadrante cuadrado geográfico (1 a 92).", examples=[53]),
    ] = None,
    date_from: Annotated[
        date | None,
        Query(description="Fecha mínima en formato ISO (YYYY-MM-DD).", examples=["2024-01-01"]),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(description="Fecha máxima en formato ISO (YYYY-MM-DD).", examples=["2024-12-31"]),
    ] = None,
    hour: Annotated[
        int | None,
        Query(ge=0, le=23, description="Filtrar por hora del día (0 a 23).", examples=[17]),
    ] = None,
    flooded_roads: Annotated[
        bool | None,
        Query(description="Filtrar registros donde las calles y cauces se encuentran anegados.", examples=[True]),
    ] = None,
    sky_condition: Annotated[
        str | None,
        Query(
            description="Filtrar por condición climática observada.",
            examples=["despejado", "nublado", "lluvia_ligera", "tormenta"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'weather_id', 'recorded_at', '-congestion_index', '-channel_runoff_mm').",
            examples=["weather_id", "recorded_at", "-congestion_index", "-channel_runoff_mm"],
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
    """Series horarias de microclima urbano, escorrentía de cauces e índice de congestión vial por cuadrante en Managua."""
    filters: list[tuple[str, str, Any]] = []
    if quadrant_id is not None:
        filters.append(("quadrant_id", "=", quadrant_id))
    if date_from:
        filters.append(("date", ">=", date_from))
    if date_to:
        filters.append(("date", "<=", date_to))
    if hour is not None:
        filters.append(("hour", "=", hour))
    if flooded_roads is not None:
        filters.append(("flooded_roads", "=", flooded_roads))
    if sky_condition:
        filters.append(("sky_condition", "=", sky_condition))

    allowed = {
        "weather_id",
        "quadrant_id",
        "recorded_at",
        "date",
        "hour",
        "precipitation_mm",
        "channel_runoff_mm",
        "congestion_index",
        "flooded_roads",
        "sky_condition",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="quadrant_weather",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="weather_id",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/trips",
    response_model=PaginatedResponse[TripOut],
    summary="Listar viajes en la plataforma y tarifas dinámicas",
    description=(
        "### Histórico Transaccional de Viajes Urbanos\n\n"
        "Consulta los viajes solicitados y completados en la plataforma MoviGo. Incluye zona y cuadrante de origen/destino, "
        "distancia recorrida en kilómetros, duración en minutos, multiplicador dinámico (`surge_multiplier`), "
        "tarifa final en Córdobas (`final_fare`), propinas y calificaciones bilaterales."
    ),
    response_description="Colección paginada de viajes urbanos transaccionales",
    responses={
        200: {"description": "Consulta exitosa de viajes."},
        422: {"description": "Error en los parámetros de filtrado o formato de consulta."},
    },
)
def get_trips(
    origin_zone_id: Annotated[
        int | None,
        Query(description="Filtrar por zona urbana de origen en Managua.", examples=[1]),
    ] = None,
    destination_zone_id: Annotated[
        int | None,
        Query(description="Filtrar por zona urbana de destino en Managua.", examples=[4]),
    ] = None,
    origin_quadrant_id: Annotated[
        int | None,
        Query(description="Filtrar por cuadrante cuadrado de origen (1 a 92).", examples=[15]),
    ] = None,
    destination_quadrant_id: Annotated[
        int | None,
        Query(description="Filtrar por cuadrante cuadrado de destino (1 a 92).", examples=[41]),
    ] = None,
    driver_id: Annotated[
        int | None,
        Query(description="Filtrar por conductor asignado.", examples=[205]),
    ] = None,
    user_id: Annotated[
        int | None,
        Query(description="Filtrar por usuario pasajero.", examples=[501]),
    ] = None,
    trip_status: Annotated[
        str | None,
        Query(
            description="Filtrar por estado del servicio.",
            examples=["completado", "cancelado_usuario", "cancelado_conductor", "no_asignado"],
        ),
    ] = None,
    payment_method: Annotated[
        str | None,
        Query(
            description="Filtrar por método de pago empleado.",
            examples=["efectivo", "tarjeta", "billetera_digital"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-requested_at', '-final_fare', '-surge_multiplier').",
            examples=["-requested_at", "-final_fare", "duration_minutes"],
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
    if origin_zone_id:
        filters.append(("origin_zone_id", "=", origin_zone_id))
    if destination_zone_id:
        filters.append(("destination_zone_id", "=", destination_zone_id))
    if origin_quadrant_id:
        filters.append(("origin_quadrant_id", "=", origin_quadrant_id))
    if destination_quadrant_id:
        filters.append(("destination_quadrant_id", "=", destination_quadrant_id))
    if driver_id:
        filters.append(("driver_id", "=", driver_id))
    if user_id:
        filters.append(("user_id", "=", user_id))
    if trip_status:
        filters.append(("trip_status", "=", trip_status))
    if payment_method:
        filters.append(("payment_method", "=", payment_method))

    allowed = {
        "trip_id",
        "requested_at",
        "wait_time_minutes",
        "distance_km",
        "duration_minutes",
        "flag_drop_fare",
        "distance_charge",
        "time_charge",
        "base_fare",
        "surge_multiplier",
        "final_fare",
        "origin_active_requests",
        "origin_available_drivers",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="trips",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-requested_at",
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/trips/{trip_id}",
    response_model=TripOut,
    summary="Obtener detalle de viaje por ID",
    description=(
        "### Información Detallada de un Viaje en Particular\n\n"
        "Recupera la ficha de un viaje individual por su identificador único transaccional (`trip_id`)."
    ),
    response_description="Datos completos del viaje consultado",
    responses={
        200: {"description": "Viaje encontrado exitosamente."},
        404: {"description": "Viaje no encontrado. Verifique que el ID solicitado exista."},
        422: {"description": "El ID proporcionado no es un entero válido."},
    },
)
def get_trip_by_id(
    trip_id: Annotated[
        int,
        Path(ge=1, description="Identificador único numérico del viaje a consultar.", examples=[1]),
    ],
):
    """Consulta la información detallada de un viaje particular."""
    return fetch_single_resource(SCHEMA, "trips", "trip_id", trip_id)


@router.get(
    "/telemetry",
    response_model=PaginatedResponse[DriverTelemetryOut],
    summary="Listar registros de telemetría GPS vehicular",
    description=(
        "### Pings Telemétricos de Posición GPS y Velocidad\n\n"
        "Consulta la serie de datos telemétricos captados desde los teléfonos de los conductores en ruta. "
        "Registra latitud, longitud, velocidad instantánea en km/h (`speed_kmh`) y estado de disponibilidad en tiempo real (`availability_status`)."
    ),
    response_description="Colección paginada de registros telemétricos GPS",
    responses={
        200: {"description": "Consulta exitosa de registros de telemetría."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_telemetry(
    driver_id: Annotated[
        int | None,
        Query(description="Filtrar por identificador de conductor monitoreado.", examples=[205]),
    ] = None,
    trip_id: Annotated[
        int | None,
        Query(description="Filtrar por identificador de viaje asociado al recorrido GPS.", examples=[10042]),
    ] = None,
    zone_id: Annotated[
        int | None,
        Query(description="Filtrar por zona urbana donde se emitió la señal.", examples=[1]),
    ] = None,
    quadrant_id: Annotated[
        int | None,
        Query(description="Filtrar por cuadrante cuadrado donde se emitió la señal (1 a 92).", examples=[15]),
    ] = None,
    availability_status: Annotated[
        str | None,
        Query(
            description="Filtrar por estado del conductor en ese instante.",
            examples=["disponible", "ocupado", "en_camino_recogida"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-recorded_at', '-speed_kmh').",
            examples=["-recorded_at", "-speed_kmh"],
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
    if driver_id:
        filters.append(("driver_id", "=", driver_id))
    if trip_id:
        filters.append(("trip_id", "=", trip_id))
    if zone_id:
        filters.append(("zone_id", "=", zone_id))
    if quadrant_id:
        filters.append(("quadrant_id", "=", quadrant_id))
    if availability_status:
        filters.append(("availability_status", "=", availability_status))

    allowed = {"telemetry_id", "trip_id", "recorded_at", "speed_kmh"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="driver_telemetry",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-recorded_at",
        sort=sort,
        offset=offset,
        limit=limit,
    )
