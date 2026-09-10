"""dlt pipeline for Cooperativa El Volcán staging in PostgreSQL."""

import logging
from typing import Any
import dlt

from volcan_sim.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SCHEMA,
)
from volcan_sim.models import (
    Finca,
    VariedadCafe,
    Beneficio,
    CuadrillaCorte,
    LoteAcopio,
    ProcesamientoBeneficio,
    SubastaEspecial,
    EmbarqueExportacion,
    ClimaZonasCafetaleras,
)

logger = logging.getLogger(__name__)


@dlt.source(name="cooperativa_el_volcan")
def volcan_source(
    fincas_data: list[dict[str, Any]],
    variedades_data: list[dict[str, Any]],
    beneficios_data: list[dict[str, Any]],
    cuadrillas_data: list[dict[str, Any]],
    lotes_data: list[dict[str, Any]],
    procesos_data: list[dict[str, Any]],
    subastas_data: list[dict[str, Any]],
    embarques_data: list[dict[str, Any]],
    clima_data: list[dict[str, Any]],
):
    """dlt source bundling the 9 coffee supply chain entities with primary keys."""

    @dlt.resource(name="fincas", write_disposition="replace", primary_key="id_finca")
    def fincas():
        yield fincas_data

    @dlt.resource(name="variedades_cafe", write_disposition="replace", primary_key="id_variedad")
    def variedades_cafe():
        yield variedades_data

    @dlt.resource(name="beneficios", write_disposition="replace", primary_key="id_beneficio")
    def beneficios():
        yield beneficios_data

    @dlt.resource(name="cuadrillas_corte", write_disposition="replace", primary_key="id_cuadrilla")
    def cuadrillas_corte():
        yield cuadrillas_data

    @dlt.resource(name="clima_zonas_cafetaleras", write_disposition="replace", primary_key="fecha")
    def clima_zonas_cafetaleras():
        yield clima_data

    @dlt.resource(name="lotes_acopio", write_disposition="replace", primary_key="id_lote")
    def lotes_acopio():
        yield lotes_data

    @dlt.resource(name="procesamiento_beneficio", write_disposition="replace", primary_key="id_proceso")
    def procesamiento_beneficio():
        yield procesos_data

    @dlt.resource(name="subastas_especiales", write_disposition="replace", primary_key="id_subasta")
    def subastas_especiales():
        yield subastas_data

    @dlt.resource(name="embarques_exportacion", write_disposition="replace", primary_key="id_embarque")
    def embarques_exportacion():
        yield embarques_data

    return (
        fincas,
        variedades_cafe,
        beneficios,
        cuadrillas_corte,
        clima_zonas_cafetaleras,
        lotes_acopio,
        procesamiento_beneficio,
        subastas_especiales,
        embarques_exportacion,
    )


def load_volcan_to_postgres(
    fincas: list[Finca],
    variedades: list[VariedadCafe],
    beneficios: list[Beneficio],
    cuadrillas: list[CuadrillaCorte],
    lotes: list[LoteAcopio],
    procesos: list[ProcesamientoBeneficio],
    subastas: list[SubastaEspecial],
    embarques: list[EmbarqueExportacion],
    clima: list[ClimaZonasCafetaleras],
    schema_name: str = POSTGRES_SCHEMA,
    connection_url: str | None = None,
) -> Any:
    """Execute dlt pipeline loading all coffee tables into PostgreSQL."""
    if connection_url is None:
        connection_url = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )

    logger.info(f"Connecting dlt pipeline to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB} (schema: {schema_name})...")

    pipeline = dlt.pipeline(
        pipeline_name="volcan_coffee_load",
        destination=dlt.destinations.postgres(connection_url),
        dataset_name=schema_name,
    )

    source = volcan_source(
        fincas_data=[f.model_dump() for f in fincas],
        variedades_data=[v.model_dump() for v in variedades],
        beneficios_data=[b.model_dump() for b in beneficios],
        cuadrillas_data=[c.model_dump() for c in cuadrillas],
        lotes_data=[l.model_dump(mode="json") for l in lotes],
        procesos_data=[p.model_dump(mode="json") for p in procesos],
        subastas_data=[s.model_dump(mode="json") for s in subastas],
        embarques_data=[e.model_dump(mode="json") for e in embarques],
        clima_data=[cl.model_dump(mode="json") for cl in clima],
    )

    info = pipeline.run(source)
    logger.info(f"dlt load finished successfully:\n{info}")
    return info
