"""dlt pipeline for MoviGo staging in PostgreSQL (standardized English table and column names)."""

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
    Quadrant,
    UrbanZone,
    User,
    Driver,
    Trip,
    DriverTelemetry,
    IncentiveCampaign,
    QuadrantWeather,
)
from movigo_sim.generator import load_movigo_quadrants

logger = logging.getLogger(__name__)


@dlt.source(name="movigo_ride_hailing")
def movigo_source(
    quadrants_data: list[dict[str, Any]],
    zones_data: list[dict[str, Any]],
    users_data: list[dict[str, Any]],
    drivers_data: list[dict[str, Any]],
    trips_data: list[dict[str, Any]],
    telemetry_data: list[dict[str, Any]],
    campaigns_data: list[dict[str, Any]],
    weather_data: list[dict[str, Any]],
):
    """dlt source bundling the 8 MoviGo relational tables with standardized English names."""

    @dlt.resource(name="quadrants", write_disposition="replace", primary_key="quadrant_id")
    def quadrants():
        yield quadrants_data

    @dlt.resource(name="urban_zones", write_disposition="replace", primary_key="zone_id")
    def urban_zones():
        yield zones_data

    @dlt.resource(name="users", write_disposition="replace", primary_key="user_id")
    def users():
        yield users_data

    @dlt.resource(name="drivers", write_disposition="replace", primary_key="driver_id")
    def drivers():
        yield drivers_data

    @dlt.resource(name="incentive_campaigns", write_disposition="replace", primary_key="campaign_id")
    def incentive_campaigns():
        yield campaigns_data

    @dlt.resource(name="quadrant_weather", write_disposition="replace", primary_key="weather_id")
    def quadrant_weather():
        yield weather_data

    @dlt.resource(name="trips", write_disposition="replace", primary_key="trip_id")
    def trips():
        yield trips_data

    @dlt.resource(name="driver_telemetry", write_disposition="replace", primary_key="telemetry_id")
    def driver_telemetry():
        yield telemetry_data

    return (
        urban_zones,
        quadrants,
        users,
        drivers,
        incentive_campaigns,
        quadrant_weather,
        trips,
        driver_telemetry,
    )


def load_movigo_to_postgres(
    zones: list[UrbanZone],
    users: list[User],
    drivers: list[Driver],
    trips: list[Trip],
    telemetry: list[DriverTelemetry],
    campaigns: list[IncentiveCampaign],
    weather: list[QuadrantWeather],
    schema_name: str = POSTGRES_SCHEMA,
    connection_url: str | None = None,
    quadrants: list[Quadrant] | None = None,
) -> Any:
    """Execute dlt pipeline loading all MoviGo tables into PostgreSQL."""
    if quadrants is None:
        quadrants = load_movigo_quadrants()
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
        quadrants_data=[q.model_dump() for q in quadrants],
        zones_data=[z.model_dump() for z in zones],
        users_data=[u.model_dump(mode="json") for u in users],
        drivers_data=[c.model_dump() for c in drivers],
        trips_data=[v.model_dump(mode="json") for v in trips],
        telemetry_data=[t.model_dump(mode="json") for t in telemetry],
        campaigns_data=[cmp.model_dump(mode="json") for cmp in campaigns],
        weather_data=(
            weather.to_dataframe().to_dict("records")
            if hasattr(weather, "to_dataframe")
            else [cl.model_dump(mode="json") for cl in weather]
        ),
    )

    info = pipeline.run(source)
    logger.info(f"dlt load finished successfully:\n{info}")
    return info
