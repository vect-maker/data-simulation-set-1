"""Routers for Caso 3: MoviGo (Transporte por Aplicación y Movilidad Urbana - Managua, Esquema OLTP 3NF)."""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path, Query

from src.api.movigo_clock import movigo_clock
from src.api.schemas import (
    DriverOut,
    DriverTelemetryOut,
    IncentiveCampaignOut,
    PaginatedResponse,
    QuadrantOut,
    QuadrantWeatherOut,
    SimulationStatusOut,
    TripCancellationOut,
    TripOut,
    TripPaymentOut,
    TripRatingOut,
    UrbanZoneOut,
    UserOut,
    VehicleOut,
    VehicleMaintenanceOut,
    WeatherAggregatedOut,
)
from src.api.utils import execute_paginated_query, execute_aggregated_weather_query, fetch_single_resource

router = APIRouter(prefix="/movigo", tags=["Caso 3: MoviGo"])
SCHEMA = "raw_staging_movigo"


@router.get(
    "/simulation/status",
    response_model=SimulationStatusOut,
    summary="Estado del reloj de simulación y progreso horario",
    description=(
        "### Monitoreo del Reloj y Generación en Tiempo Real de MoviGo\n\n"
        "Devuelve los límites temporales actualmente listos (`earliest_datetime` y `latest_datetime`), "
        "el estado del worker (`ready`, `catching_up`, `hourly_wait`), las horas faltantes de conciliación "
        "y el acumulado de viajes generados."
    ),
    responses={
        200: {"description": "Estado del reloj de simulación obtenido exitosamente."},
    },
)
def get_simulation_status():
    """Consulta los límites de tiempo válidos y el estado del motor continuo de simulación."""
    return movigo_clock.get_status()


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
        Query(ge=1, le=1000, description="Cantidad máxima de registros por página.", examples=[100]),
    ] = 100,
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
        max_limit=1000,
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
        Query(ge=1, le=1000, description="Cantidad máxima de registros por página.", examples=[50]),
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
        max_limit=1000,
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
        Query(ge=1, le=2000, description="Cantidad máxima de registros por página.", examples=[100]),
    ] = 100,
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
        max_limit=2000,
    )


@router.get(
    "/drivers",
    response_model=PaginatedResponse[DriverOut],
    summary="Listar socios conductores registrados",
    description=(
        "### Directorio de Socios Conductores (3NF)\n\n"
        "Consulta el perfil operativo de los conductores afiliados a MoviGo, incluyendo "
        "calificación promedio de pasajeros (`average_rating`), tasa histórica de aceptación (`acceptance_rate_pct`) y estado operativo (`status`)."
    ),
    response_description="Colección paginada de conductores",
    responses={
        200: {"description": "Consulta exitosa de conductores."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_drivers(
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
            examples=["-average_rating", "-acceptance_rate_pct"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Cantidad máxima de registros por página.", examples=[150]),
    ] = 150,
):
    """Consulta el directorio de conductores, calificación y tasa de aceptación."""
    filters: list[tuple[str, str, Any]] = []
    if status:
        filters.append(("status", "=", status))
    if min_rating is not None:
        filters.append(("average_rating", ">=", min_rating))

    allowed = {"driver_id", "name", "average_rating", "acceptance_rate_pct", "status"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="drivers",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="driver_id",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=1000,
    )


@router.get(
    "/vehicles",
    response_model=PaginatedResponse[VehicleOut],
    summary="Listar unidades vehiculares registradas",
    description=(
        "### Catálogo de Unidades Vehiculares (3NF)\n\n"
        "Consulta los vehículos registrados y asignados a cada conductor (`driver_id`), clasificados por categoría de servicio "
        "(`movigo_estandar`, `movigo_comfort`, `movigo_moto`), modelo, año de fabricación y matrícula (`license_plate`)."
    ),
    response_description="Colección paginada de unidades vehiculares",
    responses={
        200: {"description": "Consulta exitosa de vehículos."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_vehicles(
    driver_id: Annotated[
        int | None,
        Query(ge=1, description="Filtrar por identificador del socio conductor.", examples=[1]),
    ] = None,
    service_type: Annotated[
        str | None,
        Query(
            description="Filtrar por categoría de servicio vehicular.",
            examples=["movigo_estandar", "movigo_comfort", "movigo_moto"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'vehicle_id', '-vehicle_year').",
            examples=["vehicle_id", "-vehicle_year"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Cantidad máxima de registros por página.", examples=[150]),
    ] = 150,
):
    """Consulta las unidades vehiculares asociadas a los socios conductores."""
    filters: list[tuple[str, str, Any]] = []
    if driver_id is not None:
        filters.append(("driver_id", "=", driver_id))
    if service_type:
        filters.append(("service_type", "=", service_type))

    allowed = {"vehicle_id", "driver_id", "service_type", "vehicle_model", "vehicle_year", "license_plate"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="vehicles",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="vehicle_id",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=1000,
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
    target_zone_id: Annotated[
        int | None,
        Query(ge=1, le=12, description="Filtrar por zona urbana objetivo (1 a 12).", examples=[2]),
    ] = None,
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
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'campaign_id', '-online_hours_increase', '-budget_cost_nio', 'start_date').",
            examples=["campaign_id", "-online_hours_increase", "-budget_cost_nio", "start_date"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Cantidad máxima de registros por página.", examples=[50]),
    ] = 50,
):
    """Consulta los programas de incentivos y bonos para conductores."""
    filters: list[tuple[str, str, Any]] = []
    if target_zone_id is not None:
        filters.append(("target_zone_id", "=", target_zone_id))
    if incentive_type:
        filters.append(("incentive_type", "=", incentive_type))
    if status:
        filters.append(("status", "=", status))

    allowed = {
        "campaign_id",
        "target_zone_id",
        "budget_cost_nio",
        "online_hours_increase",
        "incentive_type",
        "start_date",
        "end_date",
        "status",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="incentive_campaigns",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="campaign_id",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=1000,
    )


@router.get(
    "/weather",
    response_model=PaginatedResponse[QuadrantWeatherOut | WeatherAggregatedOut],
    summary="Clima urbano e índice de congestión vial por cuadrante o métricas agregadas",
    description=(
        "### Monitoreo Meteorológico, Saturación Vial y Agregación Temporal en Managua\n\n"
        "Series temporales de microclima urbano que asocian la precipitación en milímetros (`precipitation_mm`), escorrentía de cauces (`channel_runoff_mm`) "
        "y temperatura (`temperature_c`) con el índice de congestión del tráfico en Managua (`congestion_index`).\n\n"
        "**Niveles de Granularidad (`granularity`):**\n"
        "- `hour` (por defecto): Entrega los registros normalizados 3NF de cada hora y cuadrante.\n"
        "- `day`: Agrega la serie diaria (precipitación total acumulada, temperatura promedio/mín/máx, congestión y horas de inundación).\n"
        "- `week`: Agrega la serie semanal por cuadrante o ciudad consolidada.\n"
        "- `month`: Agrega la serie mensual.\n\n"
        "**Consolidación Urbana (`by_quadrant`):** Si `by_quadrant=False` en agregaciones (`day`, `week`, `month`), consolida el promedio/total de toda la ciudad de Managua en una única fila por período."
    ),
    response_description="Serie climática e índice de congestión horaria o agregada en Managua",
    responses={
        200: {"description": "Consulta exitosa de registros climáticos y viales."},
        400: {"description": "Rango de fechas fuera de los límites de simulación."},
        422: {"description": "Error en el formato de fechas o parámetros de paginación."},
    },
)
def get_weather_movigo(
    quadrant_id: Annotated[
        int | None,
        Query(ge=1, le=92, description="Filtrar por cuadrante cuadrado geográfico (1 a 92).", examples=[53]),
    ] = None,
    start_time: Annotated[
        datetime | None,
        Query(description="Fecha y hora mínima de registro en formato ISO (YYYY-MM-DDTHH:MM:SS).", examples=["2024-01-01T08:00:00"]),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Fecha y hora máxima de registro en formato ISO (YYYY-MM-DDTHH:MM:SS).", examples=["2024-01-01T18:00:00"]),
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
        Query(ge=0, le=23, description="Filtrar por hora del día (0 a 23, aplicable a granularidad 'hour').", examples=[17]),
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
    granularity: Annotated[
        Literal["hour", "day", "week", "month"],
        Query(
            description=(
                "Nivel de granularidad temporal de las métricas climáticas:\n"
                "- 'hour': Registro 3NF original por hora y cuadrante (por defecto).\n"
                "- 'day': Resumen diario (precipitación total, temperatura promedio/mín/máx, escorrentía).\n"
                "- 'week': Resumen semanal.\n"
                "- 'month': Resumen mensual."
            ),
            examples=["hour", "day", "week", "month"],
        ),
    ] = "hour",
    by_quadrant: Annotated[
        bool,
        Query(
            description="Si es False y granularity != 'hour', calcula el consolidado general de toda Managua sin separar por cuadrante.",
            examples=[True, False],
        ),
    ] = True,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'weather_id', 'recorded_at', 'period_start', '-total_precipitation_mm').",
            examples=["weather_id", "recorded_at", "period_start", "-total_precipitation_mm"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=10000, description="Cantidad máxima de registros por página (hasta 10,000 para pipelines de descarga masiva).", examples=[1000]),
    ] = 1000,
):
    """Series horarias o agregadas de microclima urbano, escorrentía de cauces e índice de congestión vial."""
    movigo_clock.validate_time_bounds(start_time, end_time)
    filters: list[tuple[str, str, Any]] = []
    if quadrant_id is not None:
        filters.append(("quadrant_id", "=", quadrant_id))
    if start_time is not None:
        filters.append(("recorded_at", ">=", start_time))
    if end_time is not None:
        filters.append(("recorded_at", "<=", end_time))
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

    if granularity == "hour":
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
            max_limit=10000,
        )
    else:
        return execute_aggregated_weather_query(
            schema=SCHEMA,
            table="quadrant_weather",
            granularity=granularity,
            filters=filters,
            quadrant_id=quadrant_id,
            by_quadrant=by_quadrant,
            sort=sort,
            offset=offset,
            limit=limit,
            max_limit=10000,
        )


@router.get(
    "/trips",
    response_model=PaginatedResponse[TripOut],
    summary="Listar cabecera transaccional de viajes (3NF)",
    description=(
        "### Cabecera Transaccional de Viajes Urbanos (Esquema 3NF)\n\n"
        "Consulta la tabla `trips` normalizada en 3NF. Contiene los cuadrantes de origen/destino (`origin_quadrant_id`, `destination_quadrant_id`), "
        "coordenadas GPS en vía pública, marcas de tiempo (`requested_at`, `started_at`, `completed_at`), distancia (`distance_km`), duración (`duration_minutes`) y estado (`trip_status`)."
    ),
    response_description="Colección paginada de viajes urbanos transaccionales",
    responses={
        200: {"description": "Consulta exitosa de viajes."},
        422: {"description": "Error en los parámetros de filtrado o formato de consulta."},
    },
)
def get_trips(
    start_time: Annotated[
        datetime | None,
        Query(description="Fecha y hora mínima de solicitud en formato ISO (YYYY-MM-DDTHH:MM:SS inclusive).", examples=["2024-01-01T08:00:00"]),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Fecha y hora máxima de solicitud en formato ISO (YYYY-MM-DDTHH:MM:SS inclusive).", examples=["2024-01-01T18:00:00"]),
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
        Query(description="Filtrar por conductor asignado.", examples=[1]),
    ] = None,
    user_id: Annotated[
        int | None,
        Query(description="Filtrar por usuario pasajero.", examples=[1]),
    ] = None,
    trip_status: Annotated[
        str | None,
        Query(
            description="Filtrar por estado del servicio.",
            examples=["completado", "cancelado_usuario", "cancelado_conductor", "no_asignado"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. '-requested_at', 'distance_km', 'duration_minutes').",
            examples=["-requested_at", "distance_km", "duration_minutes"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=5000, description="Cantidad máxima de registros por página (hasta 5,000).", examples=[200]),
    ] = 200,
):
    """Cabecera transaccional de viajes urbanos (3NF)."""
    movigo_clock.validate_time_bounds(start_time, end_time)
    filters: list[tuple[str, str, Any]] = []
    if start_time is not None:
        filters.append(("requested_at", ">=", start_time))
    if end_time is not None:
        filters.append(("requested_at", "<=", end_time))
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

    allowed = {
        "trip_id",
        "user_id",
        "driver_id",
        "origin_quadrant_id",
        "destination_quadrant_id",
        "requested_at",
        "distance_km",
        "duration_minutes",
        "trip_status",
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
        max_limit=5000,
    )


@router.get(
    "/trips/{trip_id}",
    response_model=TripOut,
    summary="Obtener detalle de viaje por ID",
    description=(
        "### Información Detallada de un Viaje en Particular\n\n"
        "Recupera la cabecera transaccional de un viaje individual por su identificador único (`trip_id`)."
    ),
    response_description="Datos de la cabecera del viaje consultado",
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
    "/payments",
    response_model=PaginatedResponse[TripPaymentOut],
    summary="Listar transacciones de pago y tarifas dinámicas",
    description=(
        "### Liquidación Tarifaria y Pagos de Viajes (`trip_payments`)\n\n"
        "Consulta las transacciones financieras asociadas a cada viaje (`trip_id`), incluyendo modalidad de pago (`payment_method`), "
        "tarifa base (`base_fare`), multiplicador dinámico (`surge_multiplier`), propina (`tip_amount`), monto final (`final_fare`) y estado (`payment_status`)."
    ),
    response_description="Colección paginada de transacciones de pago",
    responses={
        200: {"description": "Consulta exitosa de pagos."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_trip_payments(
    trip_id: Annotated[
        int | None,
        Query(ge=1, description="Filtrar por identificador de viaje.", examples=[1]),
    ] = None,
    payment_method: Annotated[
        str | None,
        Query(
            description="Filtrar por método de pago empleado.",
            examples=["efectivo", "tarjeta", "billetera_digital"],
        ),
    ] = None,
    payment_status: Annotated[
        str | None,
        Query(
            description="Filtrar por estado del pago.",
            examples=["pagado", "anulado"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'payment_id', '-final_fare', '-surge_multiplier').",
            examples=["payment_id", "-final_fare", "-surge_multiplier"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=5000, description="Cantidad máxima de registros por página (hasta 5,000).", examples=[200]),
    ] = 200,
):
    """Consulta las transacciones de pago y liquidación tarifaria de viajes."""
    filters: list[tuple[str, str, Any]] = []
    if trip_id is not None:
        filters.append(("trip_id", "=", trip_id))
    if payment_method:
        filters.append(("payment_method", "=", payment_method))
    if payment_status:
        filters.append(("payment_status", "=", payment_status))

    allowed = {"payment_id", "trip_id", "payment_method", "base_fare", "surge_multiplier", "tip_amount", "final_fare", "payment_status"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="trip_payments",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="payment_id",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=5000,
    )


@router.get(
    "/ratings",
    response_model=PaginatedResponse[TripRatingOut],
    summary="Listar calificaciones post-viaje",
    description=(
        "### Calificaciones Bilaterales de Viajes Completados (`trip_ratings`)\n\n"
        "Consulta las evaluaciones otorgadas al finalizar viajes completados (`user_rating` y `driver_rating`)."
    ),
    response_description="Colección paginada de calificaciones de viajes",
    responses={
        200: {"description": "Consulta exitosa de calificaciones."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_trip_ratings(
    trip_id: Annotated[
        int | None,
        Query(ge=1, description="Filtrar por identificador de viaje completado.", examples=[1]),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'rating_id', '-driver_rating').",
            examples=["rating_id", "-driver_rating"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=5000, description="Cantidad máxima de registros por página (hasta 5,000).", examples=[200]),
    ] = 200,
):
    """Consulta las calificaciones post-viaje de pasajeros y conductores."""
    filters: list[tuple[str, str, Any]] = []
    if trip_id is not None:
        filters.append(("trip_id", "=", trip_id))

    allowed = {"rating_id", "trip_id", "user_rating", "driver_rating"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="trip_ratings",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="rating_id",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=5000,
    )


@router.get(
    "/cancellations",
    response_model=PaginatedResponse[TripCancellationOut],
    summary="Listar bitácora de cancelaciones de viajes",
    description=(
        "### Bitácora de Cancelaciones y Fricción de Mercado (`trip_cancellations`)\n\n"
        "Consulta los eventos de cancelación de viajes, incluyendo quién canceló (`cancelled_by`), motivo (`cancellation_reason`), "
        "tiempo de espera transcurrido (`wait_time_minutes`) e instantánea de demanda/oferta activa (`origin_active_requests`, `origin_available_drivers`)."
    ),
    response_description="Colección paginada de cancelaciones de viajes",
    responses={
        200: {"description": "Consulta exitosa de cancelaciones."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_trip_cancellations(
    trip_id: Annotated[
        int | None,
        Query(ge=1, description="Filtrar por identificador de viaje cancelado.", examples=[5]),
    ] = None,
    cancelled_by: Annotated[
        str | None,
        Query(
            description="Filtrar por actor que originó la cancelación.",
            examples=["usuario", "conductor"],
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            description="Campo de ordenamiento (ej. 'cancellation_id', '-wait_time_minutes').",
            examples=["cancellation_id", "-wait_time_minutes"],
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=5000, description="Cantidad máxima de registros por página (hasta 5,000).", examples=[200]),
    ] = 200,
):
    """Consulta los eventos de cancelación y métricas de fricción de despacho."""
    filters: list[tuple[str, str, Any]] = []
    if trip_id is not None:
        filters.append(("trip_id", "=", trip_id))
    if cancelled_by:
        filters.append(("cancelled_by", "=", cancelled_by))

    allowed = {
        "cancellation_id",
        "trip_id",
        "cancelled_by",
        "wait_time_minutes",
        "origin_active_requests",
        "origin_available_drivers",
    }
    return execute_paginated_query(
        schema=SCHEMA,
        table="trip_cancellations",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="cancellation_id",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=5000,
    )


@router.get(
    "/telemetry",
    response_model=PaginatedResponse[DriverTelemetryOut],
    summary="Listar registros de telemetría GPS vehicular",
    description=(
        "### Pings Telemétricos de Posición GPS y Velocidad (3NF)\n\n"
        "Consulta la serie de datos telemétricos captados desde los teléfonos de los conductores en ruta (`quadrant_id`, `latitude`, `longitude`, `speed_kmh`, `availability_status`)."
    ),
    response_description="Colección paginada de registros telemétricos GPS",
    responses={
        200: {"description": "Consulta exitosa de registros de telemetría."},
        422: {"description": "Error en los parámetros de filtrado o paginación."},
    },
)
def get_telemetry(
    start_time: Annotated[
        datetime | None,
        Query(description="Fecha y hora mínima de emisión GPS en formato ISO (YYYY-MM-DDTHH:MM:SS inclusive).", examples=["2024-01-01T08:00:00"]),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Fecha y hora máxima de emisión GPS en formato ISO (YYYY-MM-DDTHH:MM:SS inclusive).", examples=["2024-01-01T18:00:00"]),
    ] = None,
    driver_id: Annotated[
        int | None,
        Query(description="Filtrar por identificador de conductor monitoreado.", examples=[1]),
    ] = None,
    trip_id: Annotated[
        int | None,
        Query(description="Filtrar por identificador de viaje asociado al recorrido GPS.", examples=[10042]),
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
        Query(ge=1, le=10000, description="Cantidad máxima de registros por página (hasta 10,000 para streaming y análisis continuo).", examples=[1000]),
    ] = 1000,
):
    """Datos telemétricos de conducción (velocidad, coordenadas, cuadrante, estado de disponibilidad)."""
    movigo_clock.validate_time_bounds(start_time, end_time)
    filters: list[tuple[str, str, Any]] = []
    if start_time is not None:
        filters.append(("recorded_at", ">=", start_time))
    if end_time is not None:
        filters.append(("recorded_at", "<=", end_time))
    if driver_id:
        filters.append(("driver_id", "=", driver_id))
    if trip_id:
        filters.append(("trip_id", "=", trip_id))
    if quadrant_id:
        filters.append(("quadrant_id", "=", quadrant_id))
    if availability_status:
        filters.append(("availability_status", "=", availability_status))

    allowed = {"telemetry_id", "driver_id", "trip_id", "quadrant_id", "recorded_at", "speed_kmh"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="driver_telemetry",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-recorded_at",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=10000,
    )


@router.get(
    "/maintenance",
    response_model=PaginatedResponse[VehicleMaintenanceOut],
    summary="Listar servicios de mantenimiento preventivo y correctivo de la flota",
    description=(
        "### Bitácora de Mantenimiento Vehicular, Kilometraje y Tiempos de Taller\n\n"
        "Consulta el historial de servicios técnicos preventivos (cada 5,000 km) y correctivos "
        "(averías mecánicas o impacto por cauces pluviales anegados) ejecutados sobre las unidades vehiculares "
        "de la flota corporativa MoviGo, con lecturas de odómetro (`odometer_km`), costos (`cost_nio`) y horas de inactividad (`downtime_hours`)."
    ),
    response_description="Colección paginada de registros de mantenimiento vehicular",
    responses={
        200: {"description": "Página de registros de mantenimiento obtenida exitosamente."},
        400: {"description": "Parámetro de ordenamiento o filtro inválido."},
        422: {"description": "Error de validación en parámetros de consulta."},
    },
)
def get_vehicle_maintenance(
    start_date: Annotated[
        date | None,
        Query(description="Fecha mínima de servicio técnico en formato ISO (YYYY-MM-DD inclusive).", examples=["2024-01-01"]),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(description="Fecha máxima de servicio técnico en formato ISO (YYYY-MM-DD inclusive).", examples=["2024-01-03"]),
    ] = None,
    vehicle_id: Annotated[
        int | None,
        Query(description="Filtrar por identificador de la unidad vehicular (1 a 150).", examples=[12]),
    ] = None,
    maintenance_type: Annotated[
        str | None,
        Query(description="Filtrar por tipo de mantenimiento ('preventivo', 'correctivo').", examples=["preventivo"]),
    ] = None,
    sort: Annotated[
        str | None,
        Query(description="Campo de ordenamiento (ej. '-service_date', '-odometer_km', 'cost_nio').", examples=["-service_date"]),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Desplazamiento para paginación.", examples=[0]),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Cantidad máxima de registros por página.", examples=[100]),
    ] = 100,
):
    """Historial de mantenimiento preventivo y correctivo de la flota automotriz MoviGo."""
    if start_date or end_date:
        st = datetime.combine(start_date, datetime.min.time()) if start_date else None
        et = datetime.combine(end_date, datetime.max.time()) if end_date else None
        movigo_clock.validate_time_bounds(st, et)

    filters: list[tuple[str, str, Any]] = []
    if start_date:
        filters.append(("service_date", ">=", start_date))
    if end_date:
        filters.append(("service_date", "<=", end_date))
    if vehicle_id:
        filters.append(("vehicle_id", "=", vehicle_id))
    if maintenance_type:
        filters.append(("maintenance_type", "=", maintenance_type))

    allowed = {"maintenance_id", "vehicle_id", "service_date", "odometer_km", "cost_nio", "downtime_hours"}
    return execute_paginated_query(
        schema=SCHEMA,
        table="vehicle_maintenance",
        filters=filters,
        allowed_sort_columns=allowed,
        default_sort="-service_date",
        sort=sort,
        offset=offset,
        limit=limit,
        max_limit=1000,
    )
