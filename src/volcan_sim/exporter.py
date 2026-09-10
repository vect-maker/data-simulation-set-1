"""Exporter module for Cooperativa El Volcán: CSV generation, PostgreSQL DDL, and statistical verification."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from scipy.stats import chi2_contingency

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
    LoteAcopio,
    ProcesamientoBeneficio,
    SubastaEspecial,
    EmbarqueExportacion,
    ClimaZonasCafetaleras,
)

logger = logging.getLogger(__name__)


def export_volcan_to_csv(
    fincas: List[Finca],
    variedades: List[VariedadCafe],
    beneficios: List[Beneficio],
    cuadrillas: List[CuadrillaCorte],
    lotes: List[LoteAcopio],
    procesos: List[ProcesamientoBeneficio],
    subastas: List[SubastaEspecial],
    embarques: List[EmbarqueExportacion],
    clima: List[ClimaZonasCafetaleras],
    output_dir: Path = CSV_ARTIFACTS_DIR,
) -> Dict[str, Path]:
    """Export all coffee supply chain tables to CSV format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = {}

    tables = {
        "fincas": [f.model_dump() for f in fincas],
        "variedades_cafe": [v.model_dump() for v in variedades],
        "beneficios": [b.model_dump() for b in beneficios],
        "cuadrillas_corte": [c.model_dump() for c in cuadrillas],
        "lotes_acopio": [l.model_dump() for l in lotes],
        "procesamiento_beneficio": [p.model_dump() for p in procesos],
        "subastas_especiales": [s.model_dump() for s in subastas],
        "embarques_exportacion": [e.model_dump() for e in embarques],
        "clima_zonas_cafetaleras": [cl.model_dump() for cl in clima],
    }

    for table_name, records in tables.items():
        csv_path = output_dir / f"{table_name}.csv"
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False, encoding="utf-8")
        exported[table_name] = csv_path
        logger.info(f"Exported {len(df)} rows to {csv_path}")

    return exported


def generate_volcan_postgresql_ddl() -> str:
    """Generate PostgreSQL DDL for Cooperativa El Volcán."""
    return """-- =========================================================
-- ESQUEMA OLTP / RAW STAGING: Cooperativa El Volcán (Nicaragua)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw_staging_volcan;
SET search_path TO raw_staging_volcan, public;

DROP TABLE IF EXISTS embarques_exportacion CASCADE;
DROP TABLE IF EXISTS subastas_especiales CASCADE;
DROP TABLE IF EXISTS procesamiento_beneficio CASCADE;
DROP TABLE IF EXISTS lotes_acopio CASCADE;
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
    region VARCHAR(50) NOT NULL,
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
    perfil_sensorial_base VARCHAR(150) NOT NULL,
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

CREATE TABLE lotes_acopio (
    id_lote VARCHAR(20) PRIMARY KEY,
    id_finca VARCHAR(10) NOT NULL REFERENCES fincas(id_finca),
    id_variedad VARCHAR(10) NOT NULL REFERENCES variedades_cafe(id_variedad),
    id_cuadrilla VARCHAR(10) REFERENCES cuadrillas_corte(id_cuadrilla),
    fecha_corte DATE NOT NULL,
    peso_cereza_kg DECIMAL(10,2) NOT NULL,
    humedad_porcentaje DECIMAL(4,2) NOT NULL,
    puntaje_catacion_scaa DECIMAL(4,2) NOT NULL,
    certificacion VARCHAR(50) NOT NULL,
    notas_catacion TEXT,
    costo_recoleccion_nio DECIMAL(10,2) NOT NULL,
    estado_lote VARCHAR(25) NOT NULL CHECK (estado_lote IN ('recolectado', 'en_beneficio_humedo', 'en_secado', 'listo_exportacion', 'descartado'))
);

CREATE TABLE procesamiento_beneficio (
    id_proceso BIGINT PRIMARY KEY,
    id_lote VARCHAR(20) NOT NULL REFERENCES lotes_acopio(id_lote),
    id_beneficio VARCHAR(10) NOT NULL REFERENCES beneficios(id_beneficio),
    etapa VARCHAR(30) NOT NULL CHECK (etapa IN ('despulpado', 'fermentacion', 'secado_patio', 'trillado', 'clasificacion')),
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP,
    temperatura_fermentacion_c DECIMAL(4,2),
    merma_porcentaje DECIMAL(4,2) NOT NULL,
    peso_salida_kg DECIMAL(10,2) NOT NULL,
    observaciones_proceso TEXT
);

CREATE TABLE subastas_especiales (
    id_subasta VARCHAR(10) PRIMARY KEY,
    id_lote VARCHAR(20) NOT NULL REFERENCES lotes_acopio(id_lote),
    nombre_lote_especial VARCHAR(100) NOT NULL,
    peso_quintales DECIMAL(8,2) NOT NULL,
    costo_certificacion_usd DECIMAL(10,2) NOT NULL,
    retorno_esperado_usd DECIMAL(10,2) NOT NULL,
    puntaje_taza DECIMAL(4,2) NOT NULL,
    fecha_subasta DATE NOT NULL,
    estado_subasta VARCHAR(20) NOT NULL CHECK (estado_subasta IN ('programada', 'adjudicada', 'desierta'))
);

CREATE TABLE embarques_exportacion (
    id_embarque VARCHAR(20) PRIMARY KEY,
    id_lote VARCHAR(20) NOT NULL REFERENCES lotes_acopio(id_lote),
    numero_contenedor VARCHAR(20) NOT NULL,
    puerto_salida VARCHAR(50) NOT NULL DEFAULT 'Puerto Corinto, Nicaragua',
    pais_destino VARCHAR(50) NOT NULL CHECK (pais_destino IN ('Alemania', 'Estados Unidos', 'Japón', 'Bélgica', 'Taiwán', 'Italia')),
    cliente_comprador VARCHAR(100) NOT NULL,
    fecha_embarque DATE NOT NULL,
    peso_oro_quintales DECIMAL(8,2) NOT NULL,
    precio_quintal_usd DECIMAL(8,2) NOT NULL,
    flete_transporte_usd DECIMAL(8,2) NOT NULL,
    total_usd DECIMAL(12,2) NOT NULL
);

CREATE TABLE clima_zonas_cafetaleras (
    fecha DATE PRIMARY KEY,
    region VARCHAR(50) NOT NULL DEFAULT 'Jinotega',
    precipitacion_mm DECIMAL(5,2) NOT NULL,
    temperatura_media_c DECIMAL(4,2) NOT NULL,
    temperatura_min_c DECIMAL(4,2) NOT NULL,
    temperatura_max_c DECIMAL(4,2) NOT NULL,
    humedad_relativa_pct DECIMAL(4,2) NOT NULL,
    condicion_clima VARCHAR(30) NOT NULL CHECK (condicion_clima IN ('soleado', 'nublado', 'llovizna', 'temporal'))
);

-- Indices for analytical queries
CREATE INDEX idx_lotes_finca ON lotes_acopio(id_finca);
CREATE INDEX idx_lotes_variedad ON lotes_acopio(id_variedad);
CREATE INDEX idx_lotes_fecha ON lotes_acopio(fecha_corte);
CREATE INDEX idx_lotes_scaa ON lotes_acopio(puntaje_catacion_scaa);
CREATE INDEX idx_embarques_fecha ON embarques_exportacion(fecha_embarque);
CREATE INDEX idx_embarques_destino ON embarques_exportacion(pais_destino);
"""


def export_volcan_to_sql_dump(
    csv_paths: Dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL and COPY commands."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ddl = generate_volcan_postgresql_ddl()

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

    with open(output_file, "w", encoding="utf-8") as sql_f:
        sql_f.write(ddl)
        sql_f.write("\n-- =========================================================\n")
        sql_f.write("-- DATA LOAD INSTRUCTIONS (psql COPY)\n")
        sql_f.write("-- =========================================================\n\n")

        for table in copy_order:
            csv_p = csv_paths.get(table)
            if csv_p and csv_p.exists():
                sql_f.write(
                    f"\\copy raw_staging_volcan.{table} FROM '{csv_p.name}' WITH (FORMAT csv, HEADER true);\n"
                )

    logger.info(f"Generated SQL schema and load instructions at {output_file}")
    return output_file


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

    total_cherry_kg = float(df_lotes["peso_cereza_kg"].sum())
    total_export_qq = float(df_embarques["peso_oro_quintales"].sum())
    total_export_revenue_usd = float(df_embarques["total_usd"].sum())
    avg_scaa = round(float(df_lotes["puntaje_catacion_scaa"].mean()), 2)
    max_scaa = round(float(df_lotes["puntaje_catacion_scaa"].max()), 2)
    min_scaa = round(float(df_lotes["puntaje_catacion_scaa"].min()), 2)

    # Correlation between Farm Altitude and SCAA Cupping Score
    merged_lotes = df_lotes.merge(df_fincas[["id_finca", "region", "altitud_msnm"]], on="id_finca", how="left")
    altitude_corr = float(merged_lotes["altitud_msnm"].corr(merged_lotes["puntaje_catacion_scaa"]))

    # Chi-Square test of independence: Variedad de Café vs Región de Origen
    contingency_table = pd.crosstab(merged_lotes["region"], merged_lotes["id_variedad"])
    chi2_stat, p_val, dof, _ = chi2_contingency(contingency_table)

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
            "chi2_statistic": round(float(chi2_stat), 4),
            "degrees_of_freedom": int(dof),
            "p_value": float(p_val),
            "guarantee_p_less_than_0_01": bool(p_val < 0.01),
        },
        "knapsack_auction_micro_lots": {
            "total_lots": len(df_subastas),
            "total_weight_qq": round(float(df_subastas["peso_quintales"].sum()), 2),
            "total_certification_cost_usd": round(float(df_subastas["costo_certificacion_usd"].sum()), 2),
            "total_expected_return_usd": round(float(df_subastas["retorno_esperado_usd"].sum()), 2),
        },
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Wrote summary verification to {summary_path}")
    return summary
