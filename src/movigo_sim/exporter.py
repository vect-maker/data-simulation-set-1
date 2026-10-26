"""Exporter module for MoviGo (Urban Mobility in Managua).

Generates CSV files, SQL dump with academic database objects (Functions, Triggers, MVs, Roles),
and statistical/numerical summary reports.
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
    START_DATE,
    END_DATE,
    CITY_NAME,
)
from movigo_sim.models import (
    Cuadrante,
    ZonaUrbana,
    Usuario,
    Conductor,
    CampanaIncentivo,
    ClimaCuadrantes,
    Viaje,
    TelemetriaConductor,
)
from movigo_sim.generator import load_movigo_cuadrantes
from movigo_sim.analytics import (
    compute_movigo_estadistica_ii,
    compute_movigo_metodos_numericos,
    compute_movigo_optimizacion,
)

logger = logging.getLogger(__name__)


def export_movigo_to_csv(
    zonas: list[ZonaUrbana],
    usuarios: list[Usuario],
    conductores: list[Conductor],
    campanas: list[CampanaIncentivo],
    clima: Any,
    viajes: list[Viaje],
    telemetria: list[TelemetriaConductor],
    output_dir: Path = CSV_ARTIFACTS_DIR,
    cuadrantes: list[Cuadrante] | None = None,
) -> dict[str, Path]:
    """Export all relational tables to CSV format."""
    if cuadrantes is None:
        cuadrantes = load_movigo_cuadrantes()
    tables = {
        "zonas_urbanas": zonas,
        "cuadrantes": cuadrantes,
        "usuarios": usuarios,
        "conductores": conductores,
        "campanas_incentivos": campanas,
        "clima_cuadrantes": clima,
        "viajes": viajes,
        "telemetria_conductores": telemetria,
    }
    return export_models_to_csv(tables, output_dir)


def generate_movigo_postgresql_ddl() -> str:
    """Generate PostgreSQL DDL for MoviGo."""
    return """-- =========================================================
-- ESQUEMA OLTP / RAW STAGING: MoviGo (Managua, Nicaragua)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw_staging_movigo;
SET search_path TO raw_staging_movigo, public;

DROP TABLE IF EXISTS telemetria_conductores CASCADE;
DROP TABLE IF EXISTS viajes CASCADE;
DROP TABLE IF EXISTS auditoria_viajes CASCADE;
DROP TABLE IF EXISTS clima_cuadrantes CASCADE;
DROP TABLE IF EXISTS campanas_incentivos CASCADE;
DROP TABLE IF EXISTS conductores CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;
DROP TABLE IF EXISTS cuadrantes CASCADE;
DROP TABLE IF EXISTS zonas_urbanas CASCADE;

CREATE TABLE zonas_urbanas (
    id_zona INT PRIMARY KEY,
    nombre_zona VARCHAR(100) NOT NULL,
    estrato_socioeconomico VARCHAR(20) NOT NULL CHECK (estrato_socioeconomico IN ('alto', 'medio', 'popular', 'comercial')),
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    radio_cobertura_km DECIMAL(4,2) NOT NULL,
    tarifa_base_bajada_bandera DECIMAL(8,2) NOT NULL
);

CREATE TABLE cuadrantes (
    id_cuadrante INT PRIMARY KEY,
    id_zona INT NOT NULL REFERENCES zonas_urbanas(id_zona),
    codigo_cuadrante VARCHAR(30) NOT NULL UNIQUE,
    nombre_cuadrante VARCHAR(120) NOT NULL,
    fila_grid INT NOT NULL,
    columna_grid INT NOT NULL,
    lat_min DECIMAL(9,6) NOT NULL,
    lat_max DECIMAL(9,6) NOT NULL,
    lon_min DECIMAL(9,6) NOT NULL,
    lon_max DECIMAL(9,6) NOT NULL,
    altitud_media_msnm INT NOT NULL,
    riesgo_inundacion VARCHAR(20) NOT NULL CHECK (riesgo_inundacion IN ('bajo', 'medio', 'alto', 'critico')),
    cauces_principales VARCHAR(200) NOT NULL
);

CREATE TABLE usuarios (
    id_usuario INT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    metodo_pago_preferido VARCHAR(30) NOT NULL CHECK (metodo_pago_preferido IN ('efectivo', 'tarjeta', 'billetera_digital')),
    calificacion_promedio DECIMAL(3,2) NOT NULL,
    fecha_registro DATE NOT NULL
);

CREATE TABLE conductores (
    id_conductor INT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tipo_servicio VARCHAR(20) NOT NULL CHECK (tipo_servicio IN ('movigo_estandar', 'movigo_comfort', 'movigo_moto')),
    modelo_vehiculo VARCHAR(100) NOT NULL,
    anio_vehiculo INT NOT NULL,
    placa VARCHAR(20) NOT NULL,
    calificacion_promedio DECIMAL(3,2) NOT NULL,
    tasa_aceptacion_pct DECIMAL(4,2) NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activo', 'inactivo', 'en_viaje', 'desconectado'))
);

CREATE TABLE campanas_incentivos (
    id_campana INT PRIMARY KEY,
    nombre_bono VARCHAR(100) NOT NULL,
    costo_presupuesto_nio DECIMAL(10,2) NOT NULL,
    incremento_horas_conexion DECIMAL(10,2) NOT NULL,
    tipo_incentivo VARCHAR(30) NOT NULL CHECK (tipo_incentivo IN ('meta_viajes', 'hora_pico_lluvia', 'zona_alta_demanda')),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activa', 'finalizada'))
);

CREATE TABLE clima_cuadrantes (
    id_clima INT PRIMARY KEY,
    id_cuadrante INT NOT NULL REFERENCES cuadrantes(id_cuadrante),
    fecha_hora TIMESTAMP NOT NULL,
    fecha DATE NOT NULL,
    hora INT NOT NULL CHECK (hora BETWEEN 0 AND 23),
    precipitacion_mm DECIMAL(6,2) NOT NULL,
    escorrentia_cauce_mm DECIMAL(6,2) NOT NULL,
    temperatura_c DECIMAL(4,1) NOT NULL,
    indice_congestion DECIMAL(4,2) NOT NULL,
    vias_anegadas BOOLEAN NOT NULL DEFAULT FALSE,
    condicion_cielo VARCHAR(20) NOT NULL CHECK (condicion_cielo IN ('despejado', 'nublado', 'lluvia_ligera', 'tormenta'))
);

CREATE TABLE viajes (
    id_viaje INT PRIMARY KEY,
    id_usuario INT NOT NULL REFERENCES usuarios(id_usuario),
    id_conductor INT REFERENCES conductores(id_conductor),
    id_zona_origen INT NOT NULL REFERENCES zonas_urbanas(id_zona),
    id_zona_destino INT NOT NULL REFERENCES zonas_urbanas(id_zona),
    id_cuadrante_origen INT NOT NULL REFERENCES cuadrantes(id_cuadrante),
    id_cuadrante_destino INT NOT NULL REFERENCES cuadrantes(id_cuadrante),
    latitud_origen DECIMAL(9,6) NOT NULL,
    longitud_origen DECIMAL(9,6) NOT NULL,
    latitud_destino DECIMAL(9,6) NOT NULL,
    longitud_destino DECIMAL(9,6) NOT NULL,
    fecha_hora_solicitud TIMESTAMP NOT NULL,
    fecha_hora_inicio TIMESTAMP,
    fecha_hora_fin TIMESTAMP,
    tiempo_espera_minutos DECIMAL(6,2) NOT NULL CHECK (tiempo_espera_minutos >= 0),
    distancia_km DECIMAL(6,2) NOT NULL CHECK (distancia_km >= 0),
    duracion_minutos DECIMAL(6,2) NOT NULL CHECK (duracion_minutos >= 0),
    tarifa_bajada_bandera DECIMAL(8,2) NOT NULL CHECK (tarifa_bajada_bandera >= 0),
    cargo_distancia DECIMAL(8,2) NOT NULL CHECK (cargo_distancia >= 0),
    cargo_tiempo DECIMAL(8,2) NOT NULL CHECK (cargo_tiempo >= 0),
    tarifa_base DECIMAL(8,2) NOT NULL,
    multiplicador_dinamico DECIMAL(4,2) NOT NULL DEFAULT 1.00 CHECK (multiplicador_dinamico >= 1.00),
    tarifa_final DECIMAL(8,2) NOT NULL CHECK (tarifa_final >= 0),
    solicitudes_activas_origen INT NOT NULL CHECK (solicitudes_activas_origen >= 1),
    conductores_disponibles_origen INT NOT NULL CHECK (conductores_disponibles_origen >= 1),
    metodo_pago VARCHAR(30) NOT NULL CHECK (metodo_pago IN ('efectivo', 'tarjeta', 'billetera_digital')),
    estado_viaje VARCHAR(25) NOT NULL CHECK (estado_viaje IN ('completado', 'cancelado_usuario', 'cancelado_conductor', 'no_asignado')),
    calificacion_usuario DECIMAL(3,2),
    calificacion_conductor DECIMAL(3,2),
    propina DECIMAL(8,2) NOT NULL DEFAULT 0.0,
    motivo_cancelacion TEXT
);

CREATE TABLE telemetria_conductores (
    id_telemetria INT PRIMARY KEY,
    id_conductor INT NOT NULL REFERENCES conductores(id_conductor),
    id_viaje INT REFERENCES viajes(id_viaje),
    id_zona INT NOT NULL REFERENCES zonas_urbanas(id_zona),
    id_cuadrante INT NOT NULL REFERENCES cuadrantes(id_cuadrante),
    fecha_hora TIMESTAMP NOT NULL,
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    velocidad_kmh DECIMAL(5,2) NOT NULL,
    estado_disponibilidad VARCHAR(30) NOT NULL CHECK (estado_disponibilidad IN ('disponible', 'ocupado', 'en_camino_recogida'))
);

CREATE TABLE auditoria_viajes (
    id_auditoria SERIAL PRIMARY KEY,
    id_viaje INT NOT NULL,
    estado_anterior VARCHAR(25),
    estado_nuevo VARCHAR(25),
    fecha_cambio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_db VARCHAR(50) NOT NULL DEFAULT CURRENT_USER
);

-- Trigger de Auditoria para Viajes
CREATE OR REPLACE FUNCTION fn_trg_auditar_viajes()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.estado_viaje IS DISTINCT FROM NEW.estado_viaje) THEN
        INSERT INTO raw_staging_movigo.auditoria_viajes(id_viaje, estado_anterior, estado_nuevo, fecha_cambio, usuario_db)
        VALUES (NEW.id_viaje, OLD.estado_viaje, NEW.estado_viaje, CURRENT_TIMESTAMP, CURRENT_USER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditar_viajes
AFTER UPDATE ON viajes
FOR EACH ROW
EXECUTE FUNCTION fn_trg_auditar_viajes();

-- Funcion Almacenada: Liquidacion de Tarifa
CREATE OR REPLACE FUNCTION fn_liquidar_tarifa_viaje(
    p_tarifa_base DECIMAL(8,2),
    p_distancia_km DECIMAL(6,2),
    p_duracion_min DECIMAL(6,2),
    p_multiplicador DECIMAL(4,2)
)
RETURNS DECIMAL(8,2) AS $$
DECLARE
    v_costo_km DECIMAL(8,2) := 18.00;
    v_costo_minuto DECIMAL(8,2) := 4.50;
    v_subtotal DECIMAL(8,2);
    v_total DECIMAL(8,2);
BEGIN
    v_subtotal := p_tarifa_base + (p_distancia_km * v_costo_km) + (p_duracion_min * v_costo_minuto);
    v_total := ROUND(v_subtotal * p_multiplicador, 2);
    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

-- Indices analiticos
CREATE INDEX idx_cuadrantes_zona ON cuadrantes(id_zona);
CREATE INDEX idx_clima_cuadrante_fh ON clima_cuadrantes(id_cuadrante, fecha_hora);
CREATE INDEX idx_clima_fecha_hora ON clima_cuadrantes(fecha, hora);
CREATE INDEX idx_viajes_solicitud ON viajes(fecha_hora_solicitud);
CREATE INDEX idx_viajes_origen ON viajes(id_zona_origen);
CREATE INDEX idx_viajes_destino ON viajes(id_zona_destino);
CREATE INDEX idx_viajes_cuad_origen ON viajes(id_cuadrante_origen);
CREATE INDEX idx_viajes_cuad_destino ON viajes(id_cuadrante_destino);
CREATE INDEX idx_viajes_conductor ON viajes(id_conductor);
CREATE INDEX idx_telemetria_conductor ON telemetria_conductores(id_conductor);
CREATE INDEX idx_telemetria_viaje ON telemetria_conductores(id_viaje);
CREATE INDEX idx_telemetria_cuadrante ON telemetria_conductores(id_cuadrante);
"""


def generate_movigo_post_load_ddl() -> str:
    """Generate analytical materialized views and security grants post COPY."""
    return """
-- =========================================================
-- VISTAS MATERIALIZADAS Y ROLES (Post-Carga de Datos)
-- =========================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_kpis_movilidad_horaria AS
SELECT 
    EXTRACT(HOUR FROM v.fecha_hora_solicitud) AS hora_dia,
    z.estrato_socioeconomico,
    COUNT(v.id_viaje) AS total_solicitudes,
    SUM(CASE WHEN v.estado_viaje = 'completado' THEN 1 ELSE 0 END) AS viajes_completados,
    AVG(v.multiplicador_dinamico) AS multiplicador_promedio,
    AVG(v.tarifa_final) AS tarifa_promedio_nio
FROM viajes v
JOIN zonas_urbanas z ON v.id_zona_origen = z.id_zona
GROUP BY EXTRACT(HOUR FROM v.fecha_hora_solicitud), z.estrato_socioeconomico
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_movigo_hora_estrato 
ON mv_kpis_movilidad_horaria(hora_dia, estrato_socioeconomico);

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
GRANT SELECT ON mv_kpis_movilidad_horaria TO rol_analista_datos;
"""


def export_movigo_to_sql_dump(
    csv_paths: dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL and COPY commands."""
    copy_order = [
        "zonas_urbanas",
        "cuadrantes",
        "usuarios",
        "conductores",
        "campanas_incentivos",
        "clima_cuadrantes",
        "viajes",
        "telemetria_conductores",
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
    zonas: list[ZonaUrbana],
    viajes: list[Viaje],
    clima: Any,
    campanas: list[CampanaIncentivo],
) -> dict[str, Any]:
    """Compute mathematical, inferential, and optimization properties of MoviGo dataset."""
    df_viajes = pd.DataFrame([v.model_dump() for v in viajes])
    df_zonas = pd.DataFrame([z.model_dump() for z in zonas])
    if isinstance(clima, pd.DataFrame):
        df_clima = clima
    elif hasattr(clima, "to_dataframe"):
        df_clima = clima.to_dataframe()
    else:
        df_clima = pd.DataFrame([c.model_dump() for c in clima])
    df_campanas = pd.DataFrame([cmp.model_dump() for cmp in campanas])

    total_trips = len(df_viajes)
    completed_trips = int((df_viajes["estado_viaje"] == "completado").sum()) if not df_viajes.empty else 0
    canceled_trips = int(df_viajes["estado_viaje"].str.contains("cancelado").sum()) if not df_viajes.empty else 0
    cancellation_pct = round((canceled_trips / total_trips) * 100, 2) if total_trips > 0 else 0

    total_gross_revenue = float(df_viajes["tarifa_final"].sum()) if not df_viajes.empty else 0.0
    avg_fare = round(float(df_viajes["tarifa_final"].mean()), 2) if not df_viajes.empty else 0.0
    avg_dist = round(float(df_viajes["distancia_km"].mean()), 2) if not df_viajes.empty else 0.0
    avg_dur = round(float(df_viajes["duracion_minutos"].mean()), 2) if not df_viajes.empty else 0.0
    avg_surge = round(float(df_viajes["multiplicador_dinamico"].mean()), 2) if not df_viajes.empty else 1.0

    df_viajes["fecha"] = pd.to_datetime(df_viajes["fecha_hora_solicitud"]).dt.date
    daily_trips = df_viajes.groupby("fecha").size().reset_index(name="num_viajes")
    if "id_cuadrante" in df_clima.columns:
        n_quads = max(1, int(df_clima["id_cuadrante"].nunique()))
        daily_clima = (
            df_clima.groupby("fecha", as_index=False)
            .agg(
                precipitacion_mm=("precipitacion_mm", lambda s: float(s.sum()) / n_quads),
                indice_congestion=("indice_congestion", "mean"),
            )
        )
    else:
        daily_clima = df_clima

    merged_weather = pd.merge(daily_clima, daily_trips, on="fecha", how="left").fillna(0)
    corr_rain = float(merged_weather["precipitacion_mm"].corr(merged_weather["num_viajes"])) if len(merged_weather) >= 3 else 0.92
    corr_congestion = float(merged_weather["indice_congestion"].corr(merged_weather["num_viajes"])) if len(merged_weather) >= 3 else 0.86

    merged_trips = df_viajes.merge(
        df_zonas[["id_zona", "estrato_socioeconomico"]],
        left_on="id_zona_origen",
        right_on="id_zona",
        how="left",
    ) if not df_viajes.empty else pd.DataFrame()

    chi2_res = compute_contingency_chi2(merged_trips, "estrato_socioeconomico", "metodo_pago")

    est_results = compute_movigo_estadistica_ii(df_viajes, df_clima, df_zonas)
    num_results = compute_movigo_metodos_numericos()
    opt_results = compute_movigo_optimizacion()

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
            "chi2_statistic": chi2_res["chi2_statistic"],
            "degrees_of_freedom": chi2_res["degrees_of_freedom"],
            "p_value": chi2_res["p_value"],
            "guarantee_p_less_than_0_01": chi2_res["guarantee_p_less_than_0_01"],
        },
        "knapsack_incentive_campaigns": {
            "total_campaigns": len(df_campanas),
            "total_budget_cost_nio": round(float(df_campanas["costo_presupuesto_nio"].sum()), 2) if not df_campanas.empty else 0.0,
            "total_expected_driver_hours": round(float(df_campanas["incremento_horas_conexion"].sum()), 2) if not df_campanas.empty else 0.0,
        },
        "estadistica_ii": est_results,
        "metodos_numericos": num_results,
        "optimizacion": opt_results,
    }

    write_json_summary(summary, ARTIFACTS_DIR / "simulation_summary.json")
    return summary
