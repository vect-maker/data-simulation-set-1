"""dlt data pipeline for Antojitos Express staging and loading into PostgreSQL."""

import logging
from typing import List, Dict, Any, Optional
import dlt

from antojitos_sim.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SCHEMA,
)
from antojitos_sim.models import (
    Zona,
    Repartidor,
    CategoriaPlatillo,
    Platillo,
    Promocion,
    ClimaDiario,
    Orden,
    DetalleOrden,
)

logger = logging.getLogger(__name__)


@dlt.source(name="antojitos_express")
def antojitos_source(
    zonas_data: List[Dict[str, Any]],
    repartidores_data: List[Dict[str, Any]],
    categorias_data: List[Dict[str, Any]],
    platillos_data: List[Dict[str, Any]],
    promociones_data: List[Dict[str, Any]],
    clima_data: List[Dict[str, Any]],
    ordenes_data: List[Dict[str, Any]],
    detalles_data: List[Dict[str, Any]],
):
    """dlt source bundling the 8 relational entities with primary keys."""

    @dlt.resource(name="zonas", write_disposition="replace", primary_key="id_zona")
    def zonas():
        yield zonas_data

    @dlt.resource(name="repartidores", write_disposition="replace", primary_key="id_repartidor")
    def repartidores():
        yield repartidores_data

    @dlt.resource(name="categorias_platillo", write_disposition="replace", primary_key="id_categoria")
    def categorias_platillo():
        yield categorias_data

    @dlt.resource(name="platillos", write_disposition="replace", primary_key="id_platillo")
    def platillos():
        yield platillos_data

    @dlt.resource(name="promociones", write_disposition="replace", primary_key="id_promocion")
    def promociones():
        yield promociones_data

    @dlt.resource(name="clima_diario", write_disposition="replace", primary_key="fecha")
    def clima_diario():
        yield clima_data

    @dlt.resource(name="ordenes", write_disposition="replace", primary_key="id_orden")
    def ordenes():
        yield ordenes_data

    @dlt.resource(name="detalle_ordenes", write_disposition="replace", primary_key="id_detalle")
    def detalle_ordenes():
        yield detalles_data

    return (
        zonas,
        repartidores,
        categorias_platillo,
        platillos,
        promociones,
        clima_diario,
        ordenes,
        detalle_ordenes,
    )


def load_simulation_to_postgres(
    zonas: List[Zona],
    repartidores: List[Repartidor],
    categorias: List[CategoriaPlatillo],
    platillos: List[Platillo],
    promociones: List[Promocion],
    clima: List[ClimaDiario],
    ordenes: List[Orden],
    detalles: List[DetalleOrden],
    schema_name: str = POSTGRES_SCHEMA,
    connection_url: Optional[str] = None,
) -> Any:
    """Execute dlt pipeline loading all simulation tables into PostgreSQL."""
    if connection_url is None:
        connection_url = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )

    logger.info(f"Connecting dlt pipeline to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB} (schema: {schema_name})...")

    pipeline = dlt.pipeline(
        pipeline_name="antojitos_express_load",
        destination=dlt.destinations.postgres(connection_url),
        dataset_name=schema_name,
    )

    source = antojitos_source(
        zonas_data=[z.model_dump() for z in zonas],
        repartidores_data=[r.model_dump() for r in repartidores],
        categorias_data=[c.model_dump() for c in categorias],
        platillos_data=[p.model_dump() for p in platillos],
        promociones_data=[pr.model_dump(mode="json") for pr in promociones],
        clima_data=[cd.model_dump(mode="json") for cd in clima],
        ordenes_data=[o.model_dump(mode="json") for o in ordenes],
        detalles_data=[d.model_dump() for d in detalles],
    )

    info = pipeline.run(source)
    logger.info(f"dlt load finished successfully:\n{info}")
    return info
