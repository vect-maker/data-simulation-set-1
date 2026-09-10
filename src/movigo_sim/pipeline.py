"""dlt pipeline for MoviGo staging in PostgreSQL."""

import logging
from typing import Any
import dlt

from movigo_sim.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SCHEMA,
)
from movigo_sim.models import (
    ZonaUrbana,
    Usuario,
    Conductor,
    Viaje,
    TelemetriaConductor,
    CampanaIncentivo,
    ClimaCuadrantes,
)

logger = logging.getLogger(__name__)


@dlt.source(name="movigo_ride_hailing")
def movigo_source(
    zonas_data: list[dict[str, Any]],
    usuarios_data: list[dict[str, Any]],
    conductores_data: list[dict[str, Any]],
    viajes_data: list[dict[str, Any]],
    telemetria_data: list[dict[str, Any]],
    campanas_data: list[dict[str, Any]],
    clima_data: list[dict[str, Any]],
):
    """dlt source bundling the 7 MoviGo relational tables."""

    @dlt.resource(name="zonas_urbanas", write_disposition="replace", primary_key="id_zona")
    def zonas_urbanas():
        yield zonas_data

    @dlt.resource(name="usuarios", write_disposition="replace", primary_key="id_usuario")
    def usuarios():
        yield usuarios_data

    @dlt.resource(name="conductores", write_disposition="replace", primary_key="id_conductor")
    def conductores():
        yield conductores_data

    @dlt.resource(name="campanas_incentivos", write_disposition="replace", primary_key="id_campana")
    def campanas_incentivos():
        yield campanas_data

    @dlt.resource(name="clima_cuadrantes", write_disposition="replace", primary_key="fecha")
    def clima_cuadrantes():
        yield clima_data

    @dlt.resource(name="viajes", write_disposition="replace", primary_key="id_viaje")
    def viajes():
        yield viajes_data

    @dlt.resource(name="telemetria_conductores", write_disposition="replace", primary_key="id_telemetria")
    def telemetria_conductores():
        yield telemetria_data

    return (
        zonas_urbanas,
        usuarios,
        conductores,
        campanas_incentivos,
        clima_cuadrantes,
        viajes,
        telemetria_conductores,
    )


def load_movigo_to_postgres(
    zonas: list[ZonaUrbana],
    usuarios: list[Usuario],
    conductores: list[Conductor],
    viajes: list[Viaje],
    telemetria: list[TelemetriaConductor],
    campanas: list[CampanaIncentivo],
    clima: list[ClimaCuadrantes],
    schema_name: str = POSTGRES_SCHEMA,
    connection_url: str | None = None,
) -> Any:
    """Execute dlt pipeline loading all MoviGo tables into PostgreSQL."""
    if connection_url is None:
        connection_url = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )

    logger.info(f"Connecting dlt pipeline to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB} (schema: {schema_name})...")

    pipeline = dlt.pipeline(
        pipeline_name="movigo_rides_load",
        destination=dlt.destinations.postgres(connection_url),
        dataset_name=schema_name,
    )

    source = movigo_source(
        zonas_data=[z.model_dump() for z in zonas],
        usuarios_data=[u.model_dump(mode="json") for u in usuarios],
        conductores_data=[c.model_dump() for c in conductores],
        viajes_data=[v.model_dump(mode="json") for v in viajes],
        telemetria_data=[t.model_dump(mode="json") for t in telemetria],
        campanas_data=[cmp.model_dump(mode="json") for cmp in campanas],
        clima_data=[cl.model_dump(mode="json") for cl in clima],
    )

    info = pipeline.run(source)
    logger.info(f"dlt load finished successfully:\n{info}")
    return info
