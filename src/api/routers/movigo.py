"""Routers for Caso 3: MoviGo (Transporte por Aplicación y Movilidad Urbana - Managua)."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

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


@router.get("/zonas", response_model=PaginatedResponse[ZonaUrbanaOut], summary="Listar cuadrantes y zonas urbanas")
def get_zonas_movigo(
    estrato: Annotated[str | None, Query(description="Filtrar por estrato socioeconómico (alto, medio, popular, comercial)")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por nombre_zona, estrato_socioeconomico, etc.")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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


@router.get("/usuarios", response_model=PaginatedResponse[UsuarioOut], summary="Listar pasajeros registrados")
def get_usuarios(
    metodo_pago: Annotated[str | None, Query(description="efectivo, tarjeta, billetera_digital")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha_registro o calificacion_promedio")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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


@router.get("/conductores", response_model=PaginatedResponse[ConductorOut], summary="Listar flota de conductores")
def get_conductores(
    tipo_servicio: Annotated[str | None, Query(description="movigo_estandar, movigo_comfort, movigo_moto")] = None,
    estado: Annotated[str | None, Query(description="activo, inactivo, en_viaje, desconectado")] = None,
    calificacion_min: Annotated[float | None, Query(description="Calificación mínima")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por calificacion_promedio o tasa_aceptacion_pct")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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


@router.get("/campanas", response_model=PaginatedResponse[CampanaIncentivoOut], summary="Listar campañas de incentivos")
def get_campanas(
    tipo_incentivo: Annotated[str | None, Query(description="meta_viajes, hora_pico_lluvia, zona_alta_demanda")] = None,
    estado: Annotated[str | None, Query(description="activa, finalizada")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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


@router.get("/clima", response_model=PaginatedResponse[ClimaCuadranteOut], summary="Clima y congestión urbana")
def get_clima_movigo(
    fecha_desde: Annotated[date | None, Query(description="Fecha mínima YYYY-MM-DD")] = None,
    fecha_hasta: Annotated[date | None, Query(description="Fecha máxima YYYY-MM-DD")] = None,
    condicion_cielo: Annotated[str | None, Query(description="despejado, nublado, lluvia_ligera, tormenta")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha o indice_congestion")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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


@router.get("/viajes", response_model=PaginatedResponse[ViajeOut], summary="Listar viajes en plataforma")
def get_viajes(
    id_zona_origen: Annotated[int | None, Query(description="Zona de partida")] = None,
    id_zona_destino: Annotated[int | None, Query(description="Zona de destino")] = None,
    id_conductor: Annotated[int | None, Query(description="Conductor asignado")] = None,
    id_usuario: Annotated[int | None, Query(description="Usuario pasajero")] = None,
    estado_viaje: Annotated[str | None, Query(description="completado, cancelado_usuario, cancelado_conductor, no_asignado")] = None,
    metodo_pago: Annotated[str | None, Query(description="efectivo, tarjeta, billetera_digital")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha_hora_solicitud, tarifa_final, duracion_minutos")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
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

    allowed = {"id_viaje", "fecha_hora_solicitud", "distancia_km", "duracion_minutos", "multiplicador_dinamico", "tarifa_final"}
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


@router.get("/viajes/{id_viaje}", response_model=ViajeOut, summary="Obtener viaje por ID")
def get_viaje_by_id(id_viaje: int):
    """Consulta la información detallada de un viaje particular."""
    return fetch_single_resource(SCHEMA, "viajes", "id_viaje", id_viaje)


@router.get("/telemetria", response_model=PaginatedResponse[TelemetriaConductorOut], summary="Listar registros de telemetría")
def get_telemetria(
    id_conductor: Annotated[int | None, Query(description="Filtrar por conductor")] = None,
    id_zona: Annotated[int | None, Query(description="Filtrar por zona")] = None,
    estado_disponibilidad: Annotated[str | None, Query(description="disponible, ocupado, en_camino_recogida")] = None,
    sort: Annotated[str | None, Query(description="Ordenar por fecha_hora o velocidad_kmh")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Datos telemétricos de conducción (velocidad, coordenadas, estado de disponibilidad)."""
    filters: list[tuple[str, str, Any]] = []
    if id_conductor:
        filters.append(("id_conductor", "=", id_conductor))
    if id_zona:
        filters.append(("id_zona", "=", id_zona))
    if estado_disponibilidad:
        filters.append(("estado_disponibilidad", "=", estado_disponibilidad))

    allowed = {"id_telemetria", "fecha_hora", "velocidad_kmh"}
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
