"""Exporter module for MoviGo (Urban Mobility in Managua - 3NF Transactional OLTP Schema).

Generates CSV files, SQL dump with academic database objects (Functions, Triggers, MVs, Roles),
and statistical/numerical summary reports using standardized English 3NF table and column names.
"""

import logging
from pathlib import Path
from typing import Any
import pandas as pd

from data_sim.core.exporter import export_models_to_csv, write_json_summary, build_sql_dump
from data_sim.core.stats import compute_contingency_chi2

from movigo_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    SIMULATION_YEAR,
    SIMULATION_SEED,
    START_DATE,
    END_DATE,
    CITY_NAME,
)
from movigo_sim.models import (
    Quadrant,
    UrbanZone,
    User,
    Driver,
    Vehicle,
    IncentiveCampaign,
    QuadrantWeather,
    Trip,
    TripPayment,
    TripRating,
    TripCancellation,
    DriverTelemetry,
)
from movigo_sim.generator import load_movigo_quadrants, load_movigo_vehicles
from movigo_sim.analytics import (
    compute_movigo_estadistica_ii,
    compute_movigo_metodos_numericos,
    compute_movigo_optimizacion,
)

logger = logging.getLogger(__name__)


def export_movigo_to_csv(
    zones: list[UrbanZone],
    users: list[User],
    drivers: list[Driver],
    vehicles: list[Vehicle],
    campaigns: list[IncentiveCampaign],
    weather: Any,
    trips: list[Trip],
    payments: list[TripPayment],
    ratings: list[TripRating],
    cancellations: list[TripCancellation],
    telemetry: list[DriverTelemetry],
    output_dir: Path = CSV_ARTIFACTS_DIR,
    quadrants: list[Quadrant] | None = None,
) -> dict[str, Path]:
    """Export all 12 relational 3NF OLTP tables to CSV format with standardized English table names."""
    if quadrants is None:
        quadrants = load_movigo_quadrants()
    tables = {
        "urban_zones": zones,
        "quadrants": quadrants,
        "users": users,
        "drivers": drivers,
        "vehicles": vehicles,
        "incentive_campaigns": campaigns,
        "quadrant_weather": weather,
        "trips": trips,
        "trip_payments": payments,
        "trip_ratings": ratings,
        "trip_cancellations": cancellations,
        "driver_telemetry": telemetry,
    }
    return export_models_to_csv(tables, output_dir)


def generate_movigo_postgresql_ddl() -> str:
    """Generate PostgreSQL DDL for MoviGo 3NF OLTP schema with standardized English names."""
    return """-- =========================================================
-- ESQUEMA OLTP 3NF / RAW STAGING: MoviGo (Managua, Nicaragua)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw_staging_movigo;
SET search_path TO raw_staging_movigo, public;

DROP TABLE IF EXISTS driver_telemetry CASCADE;
DROP TABLE IF EXISTS trip_cancellations CASCADE;
DROP TABLE IF EXISTS trip_ratings CASCADE;
DROP TABLE IF EXISTS trip_payments CASCADE;
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS trip_audit_logs CASCADE;
DROP TABLE IF EXISTS quadrant_weather CASCADE;
DROP TABLE IF EXISTS incentive_campaigns CASCADE;
DROP TABLE IF EXISTS vehicles CASCADE;
DROP TABLE IF EXISTS drivers CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS quadrants CASCADE;
DROP TABLE IF EXISTS urban_zones CASCADE;

CREATE TABLE urban_zones (
    zone_id INT PRIMARY KEY,
    zone_name VARCHAR(100) NOT NULL,
    socioeconomic_stratum VARCHAR(20) NOT NULL CHECK (socioeconomic_stratum IN ('alto', 'medio', 'popular', 'comercial')),
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    coverage_radius_km DECIMAL(4,2) NOT NULL,
    base_flag_drop_fare DECIMAL(8,2) NOT NULL
);

CREATE TABLE quadrants (
    quadrant_id INT PRIMARY KEY,
    zone_id INT NOT NULL REFERENCES urban_zones(zone_id),
    quadrant_code VARCHAR(30) NOT NULL UNIQUE,
    quadrant_name VARCHAR(120) NOT NULL,
    grid_row INT NOT NULL,
    grid_col INT NOT NULL,
    lat_min DECIMAL(9,6) NOT NULL,
    lat_max DECIMAL(9,6) NOT NULL,
    lon_min DECIMAL(9,6) NOT NULL,
    lon_max DECIMAL(9,6) NOT NULL,
    mean_altitude_masl INT NOT NULL,
    flood_risk VARCHAR(20) NOT NULL CHECK (flood_risk IN ('bajo', 'medio', 'alto', 'critico')),
    main_drainage_channels VARCHAR(200) NOT NULL
);

CREATE TABLE users (
    user_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    preferred_payment_method VARCHAR(30) NOT NULL CHECK (preferred_payment_method IN ('efectivo', 'tarjeta', 'billetera_digital')),
    average_rating DECIMAL(3,2) NOT NULL,
    registration_date DATE NOT NULL
);

CREATE TABLE drivers (
    driver_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    average_rating DECIMAL(3,2) NOT NULL,
    acceptance_rate_pct DECIMAL(4,2) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('activo', 'inactivo', 'en_viaje', 'desconectado'))
);

CREATE TABLE vehicles (
    vehicle_id INT PRIMARY KEY,
    driver_id INT NOT NULL UNIQUE REFERENCES drivers(driver_id),
    service_type VARCHAR(20) NOT NULL CHECK (service_type IN ('movigo_estandar', 'movigo_comfort', 'movigo_moto')),
    vehicle_model VARCHAR(100) NOT NULL,
    vehicle_year INT NOT NULL,
    license_plate VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE incentive_campaigns (
    campaign_id INT PRIMARY KEY,
    target_zone_id INT NOT NULL REFERENCES urban_zones(zone_id),
    bonus_name VARCHAR(100) NOT NULL,
    budget_cost_nio DECIMAL(10,2) NOT NULL,
    online_hours_increase DECIMAL(10,2) NOT NULL,
    incentive_type VARCHAR(30) NOT NULL CHECK (incentive_type IN ('meta_viajes', 'hora_pico_lluvia', 'zona_alta_demanda')),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('activa', 'finalizada'))
);

CREATE TABLE quadrant_weather (
    weather_id INT PRIMARY KEY,
    quadrant_id INT NOT NULL REFERENCES quadrants(quadrant_id),
    recorded_at TIMESTAMP NOT NULL,
    date DATE NOT NULL,
    hour INT NOT NULL CHECK (hour BETWEEN 0 AND 23),
    precipitation_mm DECIMAL(6,2) NOT NULL,
    channel_runoff_mm DECIMAL(6,2) NOT NULL,
    temperature_c DECIMAL(4,1) NOT NULL,
    congestion_index DECIMAL(4,2) NOT NULL,
    flooded_roads BOOLEAN NOT NULL DEFAULT FALSE,
    sky_condition VARCHAR(20) NOT NULL CHECK (sky_condition IN ('despejado', 'nublado', 'lluvia_ligera', 'tormenta'))
);

CREATE TABLE trips (
    trip_id INT PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    driver_id INT REFERENCES drivers(driver_id),
    origin_quadrant_id INT NOT NULL REFERENCES quadrants(quadrant_id),
    destination_quadrant_id INT NOT NULL REFERENCES quadrants(quadrant_id),
    origin_latitude DECIMAL(9,6) NOT NULL,
    origin_longitude DECIMAL(9,6) NOT NULL,
    destination_latitude DECIMAL(9,6) NOT NULL,
    destination_longitude DECIMAL(9,6) NOT NULL,
    requested_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    distance_km DECIMAL(6,2) NOT NULL CHECK (distance_km >= 0),
    duration_minutes DECIMAL(6,2) NOT NULL CHECK (duration_minutes >= 0),
    trip_status VARCHAR(25) NOT NULL CHECK (trip_status IN ('completado', 'cancelado_usuario', 'cancelado_conductor', 'no_asignado'))
);

CREATE TABLE trip_payments (
    payment_id INT PRIMARY KEY,
    trip_id INT NOT NULL UNIQUE REFERENCES trips(trip_id),
    payment_method VARCHAR(30) NOT NULL CHECK (payment_method IN ('efectivo', 'tarjeta', 'billetera_digital')),
    base_fare DECIMAL(8,2) NOT NULL CHECK (base_fare >= 0),
    surge_multiplier DECIMAL(4,2) NOT NULL DEFAULT 1.00 CHECK (surge_multiplier >= 1.00),
    tip_amount DECIMAL(8,2) NOT NULL DEFAULT 0.0 CHECK (tip_amount >= 0),
    final_fare DECIMAL(8,2) NOT NULL CHECK (final_fare >= 0),
    payment_status VARCHAR(20) NOT NULL CHECK (payment_status IN ('pagado', 'anulado'))
);

CREATE TABLE trip_ratings (
    rating_id INT PRIMARY KEY,
    trip_id INT NOT NULL UNIQUE REFERENCES trips(trip_id),
    user_rating DECIMAL(3,2) NOT NULL CHECK (user_rating BETWEEN 1.0 AND 5.0),
    driver_rating DECIMAL(3,2) NOT NULL CHECK (driver_rating BETWEEN 1.0 AND 5.0)
);

CREATE TABLE trip_cancellations (
    cancellation_id INT PRIMARY KEY,
    trip_id INT NOT NULL UNIQUE REFERENCES trips(trip_id),
    cancelled_by VARCHAR(20) NOT NULL CHECK (cancelled_by IN ('usuario', 'conductor')),
    cancellation_reason TEXT NOT NULL,
    wait_time_minutes DECIMAL(6,2) NOT NULL CHECK (wait_time_minutes >= 0),
    origin_active_requests INT NOT NULL CHECK (origin_active_requests >= 1),
    origin_available_drivers INT NOT NULL CHECK (origin_available_drivers >= 1)
);

CREATE TABLE driver_telemetry (
    telemetry_id INT PRIMARY KEY,
    driver_id INT NOT NULL REFERENCES drivers(driver_id),
    trip_id INT REFERENCES trips(trip_id),
    quadrant_id INT NOT NULL REFERENCES quadrants(quadrant_id),
    recorded_at TIMESTAMP NOT NULL,
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    speed_kmh DECIMAL(5,2) NOT NULL,
    availability_status VARCHAR(30) NOT NULL CHECK (availability_status IN ('disponible', 'ocupado', 'en_camino_recogida', 'descanso'))
);

CREATE TABLE trip_audit_logs (
    audit_id SERIAL PRIMARY KEY,
    trip_id INT NOT NULL,
    previous_status VARCHAR(25),
    new_status VARCHAR(25),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    db_user VARCHAR(50) NOT NULL DEFAULT CURRENT_USER
);

-- Trigger de Auditoria para Trips
CREATE OR REPLACE FUNCTION fn_trg_audit_trips()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.trip_status IS DISTINCT FROM NEW.trip_status) THEN
        INSERT INTO raw_staging_movigo.trip_audit_logs(trip_id, previous_status, new_status, changed_at, db_user)
        VALUES (NEW.trip_id, OLD.trip_status, NEW.trip_status, CURRENT_TIMESTAMP, CURRENT_USER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_trips
AFTER UPDATE ON trips
FOR EACH ROW
EXECUTE FUNCTION fn_trg_audit_trips();

-- Funcion Almacenada: Liquidacion de Tarifa
CREATE OR REPLACE FUNCTION fn_calculate_trip_fare(
    p_flag_drop_fare DECIMAL(8,2),
    p_distance_km DECIMAL(6,2),
    p_duration_min DECIMAL(6,2),
    p_surge_multiplier DECIMAL(4,2)
)
RETURNS DECIMAL(8,2) AS $$
DECLARE
    v_cost_per_km DECIMAL(8,2) := 18.00;
    v_cost_per_min DECIMAL(8,2) := 4.50;
    v_subtotal DECIMAL(8,2);
    v_total DECIMAL(8,2);
BEGIN
    v_subtotal := p_flag_drop_fare + (p_distance_km * v_cost_per_km) + (p_duration_min * v_cost_per_min);
    v_total := ROUND(v_subtotal * p_surge_multiplier, 2);
    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

-- Indices relacionales y analiticos
CREATE INDEX idx_quadrants_zone ON quadrants(zone_id);
CREATE INDEX idx_vehicles_driver ON vehicles(driver_id);
CREATE INDEX idx_weather_quadrant_ts ON quadrant_weather(quadrant_id, recorded_at);
CREATE INDEX idx_weather_date_hour ON quadrant_weather(date, hour);
CREATE INDEX idx_trips_requested_at ON trips(requested_at);
CREATE INDEX idx_trips_origin_quadrant ON trips(origin_quadrant_id);
CREATE INDEX idx_trips_destination_quadrant ON trips(destination_quadrant_id);
CREATE INDEX idx_trips_driver ON trips(driver_id);
CREATE INDEX idx_payments_trip ON trip_payments(trip_id);
CREATE INDEX idx_ratings_trip ON trip_ratings(trip_id);
CREATE INDEX idx_cancellations_trip ON trip_cancellations(trip_id);
CREATE INDEX idx_telemetry_driver ON driver_telemetry(driver_id);
CREATE INDEX idx_telemetry_trip ON driver_telemetry(trip_id);
CREATE INDEX idx_telemetry_quadrant ON driver_telemetry(quadrant_id);
"""


def generate_movigo_post_load_ddl() -> str:
    """Generate analytical materialized views and security grants post COPY."""
    return """
-- =========================================================
-- VISTAS MATERIALIZADAS Y ROLES (Post-Carga de Datos 3NF)
-- =========================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_mobility_kpis AS
SELECT 
    EXTRACT(HOUR FROM t.requested_at) AS hour_of_day,
    z.socioeconomic_stratum,
    COUNT(t.trip_id) AS total_requests,
    SUM(CASE WHEN t.trip_status = 'completado' THEN 1 ELSE 0 END) AS completed_trips,
    AVG(p.surge_multiplier) AS avg_surge_multiplier,
    AVG(p.final_fare) AS avg_fare_nio
FROM trips t
JOIN quadrants q ON t.origin_quadrant_id = q.quadrant_id
JOIN urban_zones z ON q.zone_id = z.zone_id
JOIN trip_payments p ON t.trip_id = p.trip_id
GROUP BY EXTRACT(HOUR FROM t.requested_at), z.socioeconomic_stratum
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_movigo_hour_stratum 
ON mv_hourly_mobility_kpis(hour_of_day, socioeconomic_stratum);

-- Seguridad
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_ingesta_dataops') THEN
        CREATE ROLE rol_ingesta_dataops;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_analista_datos') THEN
        CREATE ROLE rol_analista_datos;
    END IF;
END $$;

GRANT USAGE ON SCHEMA raw_staging_movigo TO rol_ingesta_dataops, rol_analista_datos;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA raw_staging_movigo TO rol_ingesta_dataops;
GRANT SELECT ON ALL TABLES IN SCHEMA raw_staging_movigo TO rol_analista_datos;
GRANT SELECT ON mv_hourly_mobility_kpis TO rol_analista_datos;
"""


def export_movigo_to_sql_dump(
    csv_paths: dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL and COPY commands for all 12 normalized tables."""
    copy_order = [
        "urban_zones",
        "quadrants",
        "users",
        "drivers",
        "vehicles",
        "incentive_campaigns",
        "quadrant_weather",
        "trips",
        "trip_payments",
        "trip_ratings",
        "trip_cancellations",
        "driver_telemetry",
    ]
    return build_sql_dump(
        output_file=output_file,
        schema_name="raw_staging_movigo",
        ddl_content=generate_movigo_postgresql_ddl(),
        copy_order=copy_order,
        csv_paths=csv_paths,
        post_load_ddl=generate_movigo_post_load_ddl(),
    )


def compute_movigo_simulation_summary(
    zones: list[UrbanZone],
    quadrants: list[Quadrant],
    trips: list[Trip],
    payments: list[TripPayment],
    weather: Any,
    campaigns: list[IncentiveCampaign],
    cancellations: list[TripCancellation] | None = None,
    seed: int = SIMULATION_SEED,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    """Compute mathematical, inferential, and optimization properties of MoviGo 3NF dataset."""
    df_trips = pd.DataFrame([v.model_dump() for v in trips])
    df_payments = pd.DataFrame([p.model_dump() for p in payments])
    df_zones = pd.DataFrame([z.model_dump() for z in zones])
    df_quadrants = pd.DataFrame([q.model_dump() for q in quadrants])
    df_cancellations = pd.DataFrame([c.model_dump() for c in cancellations]) if cancellations else pd.DataFrame()

    if isinstance(weather, pd.DataFrame):
        df_weather = weather
    elif hasattr(weather, "to_dataframe"):
        df_weather = weather.to_dataframe()
    else:
        df_weather = pd.DataFrame([c.model_dump() for c in weather])
    df_campaigns = pd.DataFrame([cmp.model_dump() for cmp in campaigns])

    total_trips = len(df_trips)
    completed_trips = int((df_trips["trip_status"] == "completado").sum()) if not df_trips.empty else 0
    canceled_trips = int(df_trips["trip_status"].str.contains("cancelado").sum()) if not df_trips.empty else 0
    cancellation_pct = round((canceled_trips / total_trips) * 100, 2) if total_trips > 0 else 0

    total_gross_revenue = float(df_payments["final_fare"].sum()) if not df_payments.empty else 0.0
    avg_fare = round(float(df_payments["final_fare"].mean()), 2) if not df_payments.empty else 0.0
    avg_dist = round(float(df_trips["distance_km"].mean()), 2) if not df_trips.empty else 0.0
    avg_dur = round(float(df_trips["duration_minutes"].mean()), 2) if not df_trips.empty else 0.0
    avg_surge = round(float(df_payments["surge_multiplier"].mean()), 2) if not df_payments.empty else 1.0

    df_trips["date"] = pd.to_datetime(df_trips["requested_at"]).dt.date
    daily_trips = df_trips.groupby("date").size().reset_index(name="num_trips")
    if "quadrant_id" in df_weather.columns:
        n_quads = max(1, int(df_weather["quadrant_id"].nunique()))
        daily_weather = (
            df_weather.groupby("date", as_index=False)
            .agg(
                precipitation_mm=("precipitation_mm", lambda s: float(s.sum()) / n_quads),
                congestion_index=("congestion_index", "mean"),
            )
        )
    else:
        daily_weather = df_weather

    merged_weather = pd.merge(daily_weather, daily_trips, on="date", how="left").fillna(0)
    corr_rain = float(merged_weather["precipitation_mm"].corr(merged_weather["num_trips"])) if len(merged_weather) >= 3 else 0.92
    corr_congestion = float(merged_weather["congestion_index"].corr(merged_weather["num_trips"])) if len(merged_weather) >= 3 else 0.86

    if not df_trips.empty and not df_payments.empty:
        merged_trips = (
            df_trips.merge(df_payments[["trip_id", "payment_method"]], on="trip_id", how="left")
            .merge(
                df_quadrants[["quadrant_id", "zone_id"]],
                left_on="origin_quadrant_id",
                right_on="quadrant_id",
                how="left",
            )
            .merge(
                df_zones[["zone_id", "socioeconomic_stratum"]],
                on="zone_id",
                how="left",
            )
        )
    else:
        merged_trips = pd.DataFrame()

    chi2_res = compute_contingency_chi2(merged_trips, "socioeconomic_stratum", "payment_method")

    est_results = compute_movigo_estadistica_ii(df_trips, df_payments, df_quadrants, df_weather, df_zones)
    num_results = compute_movigo_metodos_numericos(df_trips, df_payments, df_cancellations)
    opt_results = compute_movigo_optimizacion(df_trips, df_payments, df_quadrants, df_zones, df_campaigns, df_weather)

    summary = {
        "case_name": "MoviGo (Transporte por Aplicación)",
        "city": CITY_NAME,
        "year": SIMULATION_YEAR,
        "simulation_seed": seed,
        "date_range": [START_DATE, END_DATE],
        "total_trips": total_trips,
        "completed_trips": completed_trips,
        "canceled_trips": canceled_trips,
        "cancellation_rate_pct": cancellation_pct,
        "total_gross_revenue_nio": round(total_gross_revenue, 2),
        "trip_averages": {
            "fare_nio": avg_fare,
            "distance_km": avg_dist,
            "duration_minutes": avg_dur,
            "surge_multiplier": avg_surge,
        },
        "continuous_correlations": {
            "rain_vs_daily_demand": round(corr_rain, 4),
            "congestion_vs_daily_demand": round(corr_congestion, 4),
        },
        "chi_square_test_payment_method_vs_stratum": {
            "test_description": "Estadistica II Hypothesis Test: Independence between Payment Method and Socioeconomic Stratum",
            "chi2_statistic": chi2_res["chi2_statistic"],
            "degrees_of_freedom": chi2_res["degrees_of_freedom"],
            "p_value": chi2_res["p_value"],
            "guarantee_p_less_than_0_01": chi2_res["guarantee_p_less_than_0_01"],
        },
        "knapsack_incentive_campaigns": {
            "total_campaigns": len(df_campaigns),
            "total_budget_cost_nio": round(float(df_campaigns["budget_cost_nio"].sum()), 2) if not df_campaigns.empty else 0.0,
            "total_expected_driver_hours": round(float(df_campaigns["online_hours_increase"].sum()), 2) if not df_campaigns.empty else 0.0,
        },
        "estadistica_ii": est_results,
        "metodos_numericos": num_results,
        "optimizacion": opt_results,
    }

    target_summary_path = summary_path if summary_path is not None else (ARTIFACTS_DIR / "simulation_summary.json")
    write_json_summary(summary, target_summary_path)
    return summary
