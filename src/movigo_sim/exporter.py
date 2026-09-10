"""Exporter module for MoviGo: CSV generation, PostgreSQL DDL, and statistical verification."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from scipy.stats import chi2_contingency

from movigo_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    SIMULATION_YEAR,
    START_DATE,
    END_DATE,
    CITY_NAME,
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


def export_movigo_to_csv(
    zonas: List[ZonaUrbana],
    usuarios: List[Usuario],
    conductores: List[Conductor],
    viajes: List[Viaje],
    telemetria: List[TelemetriaConductor],
    campanas: List[CampanaIncentivo],
    clima: List[ClimaCuadrantes],
    output_dir: Path = CSV_ARTIFACTS_DIR,
) -> Dict[str, Path]:
    """Export all ride-hailing tables to standard CSV format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = {}

    tables = {
        "zonas_urbanas": [z.model_dump() for z in zonas],
        "usuarios": [u.model_dump() for u in usuarios],
        "conductores": [c.model_dump() for c in conductores],
        "viajes": [v.model_dump() for v in viajes],
        "telemetria_conductores": [t.model_dump() for t in telemetria],
        "campanas_incentivos": [cmp.model_dump() for cmp in campanas],
        "clima_cuadrantes": [cl.model_dump() for cl in clima],
    }

    for table_name, records in tables.items():
        csv_path = output_dir / f"{table_name}.csv"
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False, encoding="utf-8")
        exported[table_name] = csv_path
        logger.info(f"Exported {len(df)} rows to {csv_path}")

    return exported


def generate_movigo_postgresql_ddl() -> str:
    """Generate PostgreSQL DDL matching movigo.dbml."""
    return """-- =========================================================
-- ESQUEMA OLTP / RAW STAGING: MoviGo (Managua, Nicaragua)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw_staging_movigo;
SET search_path TO raw_staging_movigo, public;

DROP TABLE IF EXISTS telemetria_conductores CASCADE;
DROP TABLE IF EXISTS viajes CASCADE;
DROP TABLE IF EXISTS campanas_incentivos CASCADE;
DROP TABLE IF EXISTS clima_cuadrantes CASCADE;
DROP TABLE IF EXISTS conductores CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;
DROP TABLE IF EXISTS zonas_urbanas CASCADE;

CREATE TABLE zonas_urbanas (
    id_zona VARCHAR(10) PRIMARY KEY,
    nombre_zona VARCHAR(100) NOT NULL,
    estrato_socioeconomico VARCHAR(20) NOT NULL CHECK (estrato_socioeconomico IN ('alto', 'medio', 'popular', 'comercial')),
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    radio_cobertura_km DECIMAL(4,2) NOT NULL,
    tarifa_base_bajada_bandera DECIMAL(8,2) NOT NULL
);

CREATE TABLE usuarios (
    id_usuario VARCHAR(15) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    metodo_pago_preferido VARCHAR(30) NOT NULL CHECK (metodo_pago_preferido IN ('efectivo', 'tarjeta', 'billetera_digital')),
    calificacion_promedio DECIMAL(3,2) NOT NULL,
    fecha_registro DATE NOT NULL
);

CREATE TABLE conductores (
    id_conductor VARCHAR(15) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tipo_servicio VARCHAR(20) NOT NULL CHECK (tipo_servicio IN ('movigo_estandar', 'movigo_comfort', 'movigo_moto')),
    modelo_vehiculo VARCHAR(100) NOT NULL,
    anio_vehiculo INT NOT NULL,
    placa VARCHAR(20) NOT NULL,
    calificacion_promedio DECIMAL(3,2) NOT NULL,
    tasa_aceptacion_pct DECIMAL(4,2) NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activo', 'inactivo', 'en_viaje', 'desconectado'))
);

CREATE TABLE viajes (
    id_viaje VARCHAR(20) PRIMARY KEY,
    id_usuario VARCHAR(15) NOT NULL REFERENCES usuarios(id_usuario),
    id_conductor VARCHAR(15) REFERENCES conductores(id_conductor),
    id_zona_origen VARCHAR(10) NOT NULL REFERENCES zonas_urbanas(id_zona),
    id_zona_destino VARCHAR(10) NOT NULL REFERENCES zonas_urbanas(id_zona),
    fecha_hora_solicitud TIMESTAMP NOT NULL,
    fecha_hora_inicio TIMESTAMP,
    fecha_hora_fin TIMESTAMP,
    distancia_km DECIMAL(6,2) NOT NULL,
    duracion_minutos DECIMAL(6,2) NOT NULL,
    tarifa_base DECIMAL(8,2) NOT NULL,
    multiplicador_dinamico DECIMAL(4,2) NOT NULL,
    tarifa_final DECIMAL(8,2) NOT NULL,
    metodo_pago VARCHAR(30) NOT NULL CHECK (metodo_pago IN ('efectivo', 'tarjeta', 'billetera_digital')),
    estado_viaje VARCHAR(25) NOT NULL CHECK (estado_viaje IN ('completado', 'cancelado_usuario', 'cancelado_conductor', 'no_asignado')),
    calificacion_usuario DECIMAL(2,1),
    calificacion_conductor DECIMAL(2,1),
    propina DECIMAL(8,2) DEFAULT 0.0,
    motivo_cancelacion TEXT
);

CREATE TABLE telemetria_conductores (
    id_telemetria BIGINT PRIMARY KEY,
    id_conductor VARCHAR(15) NOT NULL REFERENCES conductores(id_conductor),
    id_zona VARCHAR(10) NOT NULL REFERENCES zonas_urbanas(id_zona),
    fecha_hora TIMESTAMP NOT NULL,
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    velocidad_kmh DECIMAL(5,2) NOT NULL,
    estado_disponibilidad VARCHAR(25) NOT NULL CHECK (estado_disponibilidad IN ('disponible', 'ocupado', 'en_camino_recogida'))
);

CREATE TABLE campanas_incentivos (
    id_campana VARCHAR(10) PRIMARY KEY,
    nombre_bono VARCHAR(100) NOT NULL,
    costo_presupuesto_nio DECIMAL(10,2) NOT NULL,
    incremento_horas_conexion DECIMAL(10,2) NOT NULL,
    tipo_incentivo VARCHAR(30) NOT NULL CHECK (tipo_incentivo IN ('meta_viajes', 'hora_pico_lluvia', 'zona_alta_demanda')),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activa', 'finalizada'))
);

CREATE TABLE clima_cuadrantes (
    fecha DATE PRIMARY KEY,
    precipitacion_mm DECIMAL(5,2) NOT NULL,
    temperatura_c DECIMAL(4,2) NOT NULL,
    indice_congestion DECIMAL(4,2) NOT NULL,
    condicion_cielo VARCHAR(30) NOT NULL CHECK (condicion_cielo IN ('despejado', 'lluvia_ligera', 'tormenta', 'nublado'))
);

-- Analytical Indices
CREATE INDEX idx_viajes_fecha ON viajes(fecha_hora_solicitud);
CREATE INDEX idx_viajes_origen ON viajes(id_zona_origen);
CREATE INDEX idx_viajes_destino ON viajes(id_zona_destino);
CREATE INDEX idx_viajes_conductor ON viajes(id_conductor);
CREATE INDEX idx_telemetria_conductor ON telemetria_conductores(id_conductor);
"""


def export_movigo_to_sql_dump(
    csv_paths: Dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL and COPY commands."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ddl = generate_movigo_postgresql_ddl()

    copy_order = [
        "zonas_urbanas",
        "usuarios",
        "conductores",
        "campanas_incentivos",
        "clima_cuadrantes",
        "viajes",
        "telemetria_conductores",
    ]

    with open(output_file, "w", encoding="utf-8") as sql_f:
        sql_f.write(ddl)
        sql_f.write("\n-- =========================================================\n")
        sql_f.write("-- DATA LOAD INSTRUCTIONS (psql COPY)\n")
        sql_f.write("-- =========================================================\n\n")

        for table in copy_order:
            csv_p = csv_paths.get(table)
            if csv_p and csv_p.exists():
                sql_f.write(
                    f"\\copy raw_staging_movigo.{table} FROM '{csv_p.name}' WITH (FORMAT csv, HEADER true);\n"
                )

    logger.info(f"Generated SQL schema and load instructions at {output_file}")
    return output_file


def compute_movigo_simulation_summary(
    zonas: List[ZonaUrbana],
    viajes: List[Viaje],
    clima: List[ClimaCuadrantes],
    campanas: List[CampanaIncentivo],
) -> Dict[str, Any]:
    """Compute mathematical, inferential, and optimization properties of MoviGo dataset."""
    df_viajes = pd.DataFrame([v.model_dump() for v in viajes])
    df_zonas = pd.DataFrame([z.model_dump() for z in zonas])
    df_clima = pd.DataFrame([c.model_dump() for c in clima])
    df_campanas = pd.DataFrame([cmp.model_dump() for cmp in campanas])

    total_trips = len(df_viajes)
    completed_trips = int((df_viajes["estado_viaje"] == "completado").sum())
    canceled_trips = int(df_viajes["estado_viaje"].str.contains("cancelado").sum())
    cancellation_pct = round((canceled_trips / total_trips) * 100, 2) if total_trips > 0 else 0

    total_gross_revenue = float(df_viajes["tarifa_final"].sum())
    avg_fare = round(float(df_viajes["tarifa_final"].mean()), 2)
    avg_dist = round(float(df_viajes["distancia_km"].mean()), 2)
    avg_dur = round(float(df_viajes["duracion_minutos"].mean()), 2)
    avg_surge = round(float(df_viajes["multiplicador_dinamico"].mean()), 2)

    # Correlation between daily rain and daily trip demand
    df_viajes["fecha"] = pd.to_datetime(df_viajes["fecha_hora_solicitud"]).dt.date
    daily_trips = df_viajes.groupby("fecha").size().reset_index(name="num_viajes")
    merged_weather = pd.merge(df_clima, daily_trips, on="fecha", how="left").fillna(0)
    corr_rain = float(merged_weather["precipitacion_mm"].corr(merged_weather["num_viajes"]))
    corr_congestion = float(merged_weather["indice_congestion"].corr(merged_weather["num_viajes"]))

    # Chi-Square test: Método de Pago vs Estrato Socioeconómico de la Zona de Origen
    merged_trips = df_viajes.merge(
        df_zonas[["id_zona", "estrato_socioeconomico"]],
        left_on="id_zona_origen",
        right_on="id_zona",
        how="left"
    )
    contingency_table = pd.crosstab(merged_trips["estrato_socioeconomico"], merged_trips["metodo_pago"])
    chi2_stat, p_val, dof, _ = chi2_contingency(contingency_table)

    summary = {
        "case_name": "MoviGo (Transporte por Aplicación)",
        "city": CITY_NAME,
        "year": SIMULATION_YEAR,
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
            "test_description": "Estadistica II Hypothesis Test: Independence between Metodo de Pago and Estrato Socioeconomico",
            "chi2_statistic": round(float(chi2_stat), 4),
            "degrees_of_freedom": int(dof),
            "p_value": float(p_val),
            "guarantee_p_less_than_0_01": bool(p_val < 0.01),
        },
        "knapsack_incentive_campaigns": {
            "total_campaigns": len(df_campanas),
            "total_budget_cost_nio": round(float(df_campanas["costo_presupuesto_nio"].sum()), 2),
            "total_expected_driver_hours": round(float(df_campanas["incremento_horas_conexion"].sum()), 2),
        },
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Wrote summary verification to {summary_path}")
    return summary
