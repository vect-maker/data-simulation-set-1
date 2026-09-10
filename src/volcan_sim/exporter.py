"""Exporter module for Cooperativa El Volcan.

Generates CSV files, SQL dump with academic database objects (SPs, Triggers, MVs, Roles),
and statistical/numerical summary reports.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import numpy as np

from data_sim.core.exporter import export_models_to_csv, write_json_summary, build_sql_dump
from data_sim.core.stats import compute_contingency_chi2

from volcan_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    SIMULATION_YEAR,
    START_DATE,
    END_DATE,
)
from volcan_sim.models import (
    Finca,
    VariedadCafe,
    Beneficio,
    CuadrillaCorte,
    ClimaZonasCafetaleras,
    LoteAcopio,
    ProcesamientoBeneficio,
    SubastaEspecial,
    EmbarqueExportacion,
)
from volcan_sim.analytics import (
    compute_volcan_estadistica_ii,
    compute_volcan_metodos_numericos,
    compute_volcan_optimizacion,
)

logger = logging.getLogger(__name__)


def export_volcan_to_csv(
    fincas: List[Finca],
    variedades: List[VariedadCafe],
    beneficios: List[Beneficio],
    cuadrillas: List[CuadrillaCorte],
    clima: List[ClimaZonasCafetaleras],
    lotes: List[LoteAcopio],
    procesos: List[ProcesamientoBeneficio],
    subastas: List[SubastaEspecial],
    embarques: List[EmbarqueExportacion],
    output_dir: Path = CSV_ARTIFACTS_DIR,
) -> Dict[str, Path]:
    """Export all relational tables to CSV format."""
    tables = {
        "fincas": fincas,
        "variedades_cafe": variedades,
        "beneficios": beneficios,
        "cuadrillas_corte": cuadrillas,
        "clima_zonas_cafetaleras": clima,
        "lotes_acopio": lotes,
        "procesamiento_beneficio": procesos,
        "subastas_especiales": subastas,
        "embarques_exportacion": embarques,
    }
    return export_models_to_csv(tables, output_dir)


def generate_volcan_postgresql_ddl() -> str:
    """Generate PostgreSQL DDL for Cooperativa El Volcan."""
    return """-- =========================================================
-- ESQUEMA OLTP / RAW STAGING: Cooperativa El Volcán (Nicaragua)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw_staging_volcan;
SET search_path TO raw_staging_volcan, public;

DROP TABLE IF EXISTS embarques_exportacion CASCADE;
DROP TABLE IF EXISTS subastas_especiales CASCADE;
DROP TABLE IF EXISTS procesamiento_beneficio CASCADE;
DROP TABLE IF EXISTS lotes_acopio CASCADE;
DROP TABLE IF EXISTS auditoria_lotes CASCADE;
DROP TABLE IF EXISTS clima_zonas_cafetaleras CASCADE;
DROP TABLE IF EXISTS cuadrillas_corte CASCADE;
DROP TABLE IF EXISTS beneficios CASCADE;
DROP TABLE IF EXISTS variedades_cafe CASCADE;
DROP TABLE IF EXISTS fincas CASCADE;

CREATE TABLE fincas (
    id_finca VARCHAR(10) PRIMARY KEY,
    nombre_finca VARCHAR(100) NOT NULL,
    id_productor VARCHAR(10) NOT NULL,
    nombre_productor VARCHAR(100) NOT NULL,
    region VARCHAR(50) NOT NULL CHECK (region IN ('Jinotega', 'Matagalpa', 'Nueva Segovia - Dipilto', 'Madriz')),
    municipio VARCHAR(50) NOT NULL,
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    altitud_msnm INT NOT NULL,
    area_manzanas DECIMAL(6,2) NOT NULL
);

CREATE TABLE variedades_cafe (
    id_variedad VARCHAR(10) PRIMARY KEY,
    nombre_variedad VARCHAR(50) NOT NULL,
    especie VARCHAR(30) NOT NULL DEFAULT 'Coffea Arabica',
    perfil_sensorial_base VARCHAR(100) NOT NULL,
    resistencia_roya VARCHAR(20) NOT NULL CHECK (resistencia_roya IN ('alta', 'media', 'susceptible')),
    rendimiento_promedio_qq_mz DECIMAL(5,2) NOT NULL
);

CREATE TABLE beneficios (
    id_beneficio VARCHAR(10) PRIMARY KEY,
    nombre_beneficio VARCHAR(100) NOT NULL,
    tipo_beneficio VARCHAR(20) NOT NULL CHECK (tipo_beneficio IN ('humedo', 'seco')),
    municipio VARCHAR(50) NOT NULL,
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    capacidad_quintales_dia DECIMAL(10,2) NOT NULL,
    costo_procesamiento_qq DECIMAL(8,2) NOT NULL
);

CREATE TABLE cuadrillas_corte (
    id_cuadrilla VARCHAR(10) PRIMARY KEY,
    nombre_cuadrilla VARCHAR(100) NOT NULL,
    capacidad_recolectores INT NOT NULL,
    rendimiento_latas_dia DECIMAL(8,2) NOT NULL,
    costo_jornal_dia DECIMAL(8,2) NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activa', 'descanso', 'asignada'))
);

CREATE TABLE clima_zonas_cafetaleras (
    fecha DATE PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    precipitacion_mm DECIMAL(6,2) NOT NULL,
    temperatura_media_c DECIMAL(4,1) NOT NULL,
    temperatura_min_c DECIMAL(4,1) NOT NULL,
    temperatura_max_c DECIMAL(4,1) NOT NULL,
    humedad_relativa_pct DECIMAL(5,2) NOT NULL,
    condicion_clima VARCHAR(20) NOT NULL CHECK (condicion_clima IN ('soleado', 'nublado', 'llovizna', 'temporal'))
);

CREATE TABLE lotes_acopio (
    id_lote VARCHAR(20) PRIMARY KEY,
    id_finca VARCHAR(10) NOT NULL REFERENCES fincas(id_finca),
    id_variedad VARCHAR(10) NOT NULL REFERENCES variedades_cafe(id_variedad),
    id_cuadrilla VARCHAR(10) REFERENCES cuadrillas_corte(id_cuadrilla),
    fecha_corte DATE NOT NULL,
    peso_cereza_kg DECIMAL(10,2) NOT NULL CHECK (peso_cereza_kg > 0),
    humedad_porcentaje DECIMAL(5,2) NOT NULL,
    puntaje_catacion_scaa DECIMAL(4,2) NOT NULL,
    certificacion VARCHAR(50) NOT NULL,
    notas_catacion TEXT,
    costo_recoleccion_nio DECIMAL(10,2) NOT NULL,
    estado_lote VARCHAR(30) NOT NULL CHECK (estado_lote IN ('recolectado', 'en_beneficio_humedo', 'en_secado', 'listo_exportacion', 'descartado'))
);

CREATE TABLE auditoria_lotes (
    id_auditoria SERIAL PRIMARY KEY,
    id_lote VARCHAR(20) NOT NULL,
    estado_anterior VARCHAR(30),
    estado_nuevo VARCHAR(30),
    fecha_cambio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_db VARCHAR(50) NOT NULL DEFAULT CURRENT_USER
);

CREATE TABLE procesamiento_beneficio (
    id_proceso INT PRIMARY KEY,
    id_lote VARCHAR(20) NOT NULL REFERENCES lotes_acopio(id_lote),
    id_beneficio VARCHAR(10) NOT NULL REFERENCES beneficios(id_beneficio),
    etapa VARCHAR(30) NOT NULL CHECK (etapa IN ('despulpado', 'fermentacion', 'secado_patio', 'trillado', 'clasificacion')),
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP,
    temperatura_fermentacion_c DECIMAL(4,1),
    merma_porcentaje DECIMAL(5,2) NOT NULL,
    peso_salida_kg DECIMAL(10,2) NOT NULL,
    observaciones_proceso TEXT
);

CREATE TABLE subastas_especiales (
    id_subasta VARCHAR(10) PRIMARY KEY,
    id_lote VARCHAR(20) REFERENCES lotes_acopio(id_lote),
    nombre_lote_especial VARCHAR(100) NOT NULL,
    peso_quintales DECIMAL(6,2) NOT NULL,
    costo_certificacion_usd DECIMAL(8,2) NOT NULL,
    retorno_esperado_usd DECIMAL(10,2) NOT NULL,
    puntaje_taza DECIMAL(4,2) NOT NULL,
    fecha_subasta DATE NOT NULL,
    estado_subasta VARCHAR(20) NOT NULL CHECK (estado_subasta IN ('programada', 'adjudicada', 'desierta'))
);

CREATE TABLE embarques_exportacion (
    id_embarque VARCHAR(20) PRIMARY KEY,
    id_lote VARCHAR(20) NOT NULL REFERENCES lotes_acopio(id_lote),
    numero_contenedor VARCHAR(20) NOT NULL,
    puerto_salida VARCHAR(100) NOT NULL,
    pais_destino VARCHAR(50) NOT NULL,
    cliente_comprador VARCHAR(100) NOT NULL,
    fecha_embarque DATE NOT NULL,
    peso_oro_quintales DECIMAL(8,2) NOT NULL,
    precio_quintal_usd DECIMAL(8,2) NOT NULL,
    flete_transporte_usd DECIMAL(8,2) NOT NULL,
    total_usd DECIMAL(10,2) NOT NULL
);

-- Trigger de Auditoria para Lotes
CREATE OR REPLACE FUNCTION fn_trg_auditar_lotes()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.estado_lote IS DISTINCT FROM NEW.estado_lote) THEN
        INSERT INTO raw_staging_volcan.auditoria_lotes(id_lote, estado_anterior, estado_nuevo, fecha_cambio, usuario_db)
        VALUES (NEW.id_lote, OLD.estado_lote, NEW.estado_lote, CURRENT_TIMESTAMP, CURRENT_USER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditar_lotes
AFTER UPDATE ON lotes_acopio
FOR EACH ROW
EXECUTE FUNCTION fn_trg_auditar_lotes();

-- Procedimiento Almacenado de Cierre de Etapa
CREATE OR REPLACE PROCEDURE sp_cerrar_etapa_beneficio(
    p_id_proceso INT,
    p_merma DECIMAL(5,2),
    p_peso_salida DECIMAL(10,2)
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE raw_staging_volcan.procesamiento_beneficio
    SET merma_porcentaje = p_merma,
        peso_salida_kg = p_peso_salida,
        fecha_fin = CURRENT_TIMESTAMP
    WHERE id_proceso = p_id_proceso;
END;
$$;

-- Indices analiticos
CREATE INDEX idx_lotes_finca ON lotes_acopio(id_finca);
CREATE INDEX idx_lotes_variedad ON lotes_acopio(id_variedad);
CREATE INDEX idx_lotes_fecha ON lotes_acopio(fecha_corte);
CREATE INDEX idx_lotes_scaa ON lotes_acopio(puntaje_catacion_scaa);
CREATE INDEX idx_embarques_fecha ON embarques_exportacion(fecha_embarque);
CREATE INDEX idx_embarques_destino ON embarques_exportacion(pais_destino);
"""


def generate_volcan_post_load_ddl() -> str:
    """Generate analytical materialized view and security grants post COPY."""
    return """
-- =========================================================
-- VISTAS MATERIALIZADAS Y ROLES (Post-Carga de Datos)
-- =========================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_resumen_exportacion_pais AS
SELECT 
    e.pais_destino,
    COUNT(e.id_embarque) AS total_contenedores,
    SUM(e.peso_oro_quintales) AS total_quintales_exportados,
    AVG(e.precio_quintal_usd) AS precio_promedio_qq_usd,
    SUM(e.total_usd) AS ingresos_totales_fob_usd
FROM embarques_exportacion e
GROUP BY e.pais_destino
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_volcan_pais 
ON mv_resumen_exportacion_pais(pais_destino);

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

GRANT USAGE ON SCHEMA raw_staging_volcan TO rol_ingesta_dataops, rol_analista_datos;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA raw_staging_volcan TO rol_ingesta_dataops;
GRANT SELECT ON ALL TABLES IN SCHEMA raw_staging_volcan TO rol_analista_datos;
GRANT SELECT ON mv_resumen_exportacion_pais TO rol_analista_datos;
"""


def export_volcan_to_sql_dump(
    csv_paths: Dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL and COPY commands."""
    copy_order = [
        "fincas",
        "variedades_cafe",
        "beneficios",
        "cuadrillas_corte",
        "clima_zonas_cafetaleras",
        "lotes_acopio",
        "procesamiento_beneficio",
        "subastas_especiales",
        "embarques_exportacion",
    ]
    return build_sql_dump(
        output_file=output_file,
        schema_name="raw_staging_volcan",
        ddl_content=generate_volcan_postgresql_ddl(),
        copy_order=copy_order,
        csv_paths=csv_paths,
        post_load_ddl=generate_volcan_post_load_ddl(),
    )


def compute_volcan_simulation_summary(
    fincas: List[Finca],
    variedades: List[VariedadCafe],
    lotes: List[LoteAcopio],
    embarques: List[EmbarqueExportacion],
    subastas: List[SubastaEspecial],
) -> Dict[str, Any]:
    """Compute mathematical, inferential, and optimization properties of the dataset."""
    df_lotes = pd.DataFrame([l.model_dump() for l in lotes])
    df_fincas = pd.DataFrame([f.model_dump() for f in fincas])
    df_embarques = pd.DataFrame([e.model_dump() for e in embarques])
    df_subastas = pd.DataFrame([s.model_dump() for s in subastas])

    total_cherry_kg = float(df_lotes["peso_cereza_kg"].sum()) if not df_lotes.empty else 0.0
    total_export_qq = float(df_embarques["peso_oro_quintales"].sum()) if not df_embarques.empty else 0.0
    total_export_revenue_usd = float(df_embarques["total_usd"].sum()) if not df_embarques.empty else 0.0
    avg_scaa = round(float(df_lotes["puntaje_catacion_scaa"].mean()), 2) if not df_lotes.empty else 85.0
    max_scaa = round(float(df_lotes["puntaje_catacion_scaa"].max()), 2) if not df_lotes.empty else 90.0
    min_scaa = round(float(df_lotes["puntaje_catacion_scaa"].min()), 2) if not df_lotes.empty else 80.0

    # Correlation between Farm Altitude and SCAA Cupping Score
    merged_lotes = df_lotes.merge(
        df_fincas[["id_finca", "region", "altitud_msnm"]], on="id_finca", how="left"
    ) if not df_lotes.empty else pd.DataFrame()
    altitude_corr = float(merged_lotes["altitud_msnm"].corr(merged_lotes["puntaje_catacion_scaa"])) if len(merged_lotes) >= 3 else 0.72

    # Chi-Square test of independence: Variedad de Café vs Región de Origen
    chi2_res = compute_contingency_chi2(merged_lotes, "region", "id_variedad")

    # Multi-Pillar Analytics
    est_results = compute_volcan_estadistica_ii(df_lotes, df_fincas, df_embarques)
    num_results = compute_volcan_metodos_numericos(df_lotes)
    opt_results = compute_volcan_optimizacion()

    summary = {
        "case_name": "Cooperativa El Volcán (Café de Exportación)",
        "origin_country": "Nicaragua",
        "coffee_regions": ["Jinotega", "Matagalpa", "Nueva Segovia - Dipilto", "Madriz"],
        "export_port": "Puerto Corinto, Nicaragua",
        "year": SIMULATION_YEAR,
        "date_range": [START_DATE, END_DATE],
        "total_farms": len(df_fincas),
        "total_harvest_lots": len(df_lotes),
        "total_cherry_harvested_kg": round(total_cherry_kg, 2),
        "total_green_coffee_exported_qq": round(total_export_qq, 2),
        "total_export_revenue_usd": round(total_export_revenue_usd, 2),
        "scaa_cupping_scores": {
            "mean": avg_scaa,
            "min": min_scaa,
            "max": max_scaa,
            "correlation_with_altitude": round(altitude_corr, 4),
        },
        "chi_square_test_variety_vs_region": {
            "test_description": "Estadistica II Hypothesis Test: Independence between Variedad and Region",
            "chi2_statistic": chi2_res["chi2_statistic"],
            "degrees_of_freedom": chi2_res["degrees_of_freedom"],
            "p_value": chi2_res["p_value"],
            "guarantee_p_less_than_0_01": chi2_res["guarantee_p_less_than_0_01"],
        },
        "knapsack_auction_micro_lots": {
            "total_lots": len(df_subastas),
            "total_weight_qq": round(float(df_subastas["peso_quintales"].sum()), 2) if not df_subastas.empty else 0.0,
            "total_certification_cost_usd": round(float(df_subastas["costo_certificacion_usd"].sum()), 2) if not df_subastas.empty else 0.0,
            "total_expected_return_usd": round(float(df_subastas["retorno_esperado_usd"].sum()), 2) if not df_subastas.empty else 0.0,
        },
        "estadistica_ii": est_results,
        "metodos_numericos": num_results,
        "optimizacion": opt_results,
    }

    write_json_summary(summary, ARTIFACTS_DIR / "simulation_summary.json")
    return summary
