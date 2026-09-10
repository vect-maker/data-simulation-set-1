"""Exporter module: generates CSV artifacts, PostgreSQL DDL, and data SQL dumps."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from scipy.stats import chi2_contingency

from antojitos_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    SIMULATION_YEAR,
    START_DATE,
    END_DATE,
    CITY_NAME,
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


def export_to_csv(
    zonas: List[Zona],
    repartidores: List[Repartidor],
    categorias: List[CategoriaPlatillo],
    platillos: List[Platillo],
    promociones: List[Promocion],
    clima: List[ClimaDiario],
    ordenes: List[Orden],
    detalles: List[DetalleOrden],
    output_dir: Path = CSV_ARTIFACTS_DIR,
) -> Dict[str, Path]:
    """Export all relational tables to standard CSV format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = {}

    tables = {
        "zonas": [z.model_dump() for z in zonas],
        "repartidores": [r.model_dump() for r in repartidores],
        "categorias_platillo": [c.model_dump() for c in categorias],
        "platillos": [p.model_dump() for p in platillos],
        "promociones": [pr.model_dump() for pr in promociones],
        "clima_diario": [cd.model_dump() for cd in clima],
        "ordenes": [o.model_dump() for o in ordenes],
        "detalle_ordenes": [d.model_dump() for d in detalles],
    }

    for table_name, records in tables.items():
        csv_path = output_dir / f"{table_name}.csv"
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False, encoding="utf-8")
        exported_files[table_name] = csv_path
        logger.info(f"Exported {len(df)} rows to {csv_path}")

    return exported_files


def generate_postgresql_ddl() -> str:
    """Generate PostgreSQL DDL matching the updated DBML schema."""
    return """-- =========================================================
-- ESQUEMA OLTP / RAW STAGING: Antojitos Express (Managua, Nicaragua)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw_staging;
SET search_path TO raw_staging, public;

DROP TABLE IF EXISTS detalle_ordenes CASCADE;
DROP TABLE IF EXISTS ordenes CASCADE;
DROP TABLE IF EXISTS clima_diario CASCADE;
DROP TABLE IF EXISTS promociones CASCADE;
DROP TABLE IF EXISTS platillos CASCADE;
DROP TABLE IF EXISTS categorias_platillo CASCADE;
DROP TABLE IF EXISTS repartidores CASCADE;
DROP TABLE IF EXISTS zonas CASCADE;

CREATE TABLE zonas (
    id_zona VARCHAR(10) PRIMARY KEY,
    nombre_zona VARCHAR(100) NOT NULL,
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    distancia_km DECIMAL(5,2) NOT NULL,
    tiempo_base_minutos INT NOT NULL,
    tarifa_envio_base DECIMAL(8,2) NOT NULL
);

CREATE TABLE repartidores (
    id_repartidor VARCHAR(10) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tipo_vehiculo VARCHAR(20) NOT NULL CHECK (tipo_vehiculo IN ('moto', 'bicicleta', 'auto')),
    calificacion_promedio DECIMAL(3,2) NOT NULL,
    capacidad_maxima_ordenes INT NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activo', 'inactivo', 'descanso'))
);

CREATE TABLE categorias_platillo (
    id_categoria VARCHAR(10) PRIMARY KEY,
    nombre_categoria VARCHAR(50) NOT NULL,
    margen_contribucion_pct DECIMAL(4,2) NOT NULL
);

CREATE TABLE platillos (
    id_platillo VARCHAR(10) PRIMARY KEY,
    id_categoria VARCHAR(10) NOT NULL REFERENCES categorias_platillo(id_categoria),
    nombre_platillo VARCHAR(100) NOT NULL,
    precio_unitario DECIMAL(8,2) NOT NULL,
    costo_ingredientes DECIMAL(8,2) NOT NULL,
    tiempo_preparacion_minutos DECIMAL(5,2) NOT NULL,
    requiere_horno BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE promociones (
    id_promocion VARCHAR(10) PRIMARY KEY,
    nombre_campana VARCHAR(100) NOT NULL,
    costo_campana DECIMAL(10,2) NOT NULL,
    retorno_esperado DECIMAL(10,2) NOT NULL,
    descuento_pct DECIMAL(4,2) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL
);

CREATE TABLE clima_diario (
    fecha DATE PRIMARY KEY,
    precipitacion_mm DECIMAL(5,2) NOT NULL,
    temperatura_c DECIMAL(4,2) NOT NULL,
    condicion_cielo VARCHAR(30) NOT NULL CHECK (condicion_cielo IN ('despejado', 'lluvia_ligera', 'tormenta', 'nublado'))
);

CREATE TABLE ordenes (
    id_orden VARCHAR(20) PRIMARY KEY,
    id_zona VARCHAR(10) NOT NULL REFERENCES zonas(id_zona),
    id_repartidor VARCHAR(10) REFERENCES repartidores(id_repartidor),
    id_promocion VARCHAR(10) REFERENCES promociones(id_promocion),
    fecha_hora_creacion TIMESTAMP NOT NULL,
    fecha_hora_entrega TIMESTAMP,
    metodo_pago VARCHAR(30) NOT NULL CHECK (metodo_pago IN ('efectivo', 'tarjeta', 'billetera_digital')),
    estado_orden VARCHAR(20) NOT NULL CHECK (estado_orden IN ('entregada', 'cancelada', 'en_camino', 'preparando')),
    total_orden DECIMAL(10,2) NOT NULL,
    costo_envio DECIMAL(8,2) NOT NULL,
    propina DECIMAL(8,2) DEFAULT 0.0,
    notas_entrega TEXT,
    comentario_cliente TEXT,
    motivo_cancelacion TEXT
);

CREATE TABLE detalle_ordenes (
    id_detalle BIGINT PRIMARY KEY,
    id_orden VARCHAR(20) NOT NULL REFERENCES ordenes(id_orden),
    id_platillo VARCHAR(10) NOT NULL REFERENCES platillos(id_platillo),
    cantidad INT NOT NULL,
    precio_unitario DECIMAL(8,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL
);

-- Indices for analytical queries
CREATE INDEX idx_ordenes_fecha ON ordenes(fecha_hora_creacion);
CREATE INDEX idx_ordenes_zona ON ordenes(id_zona);
CREATE INDEX idx_ordenes_repartidor ON ordenes(id_repartidor);
CREATE INDEX idx_detalle_ordenes_orden ON detalle_ordenes(id_orden);
CREATE INDEX idx_detalle_ordenes_platillo ON detalle_ordenes(id_platillo);
"""


def export_to_sql_dump(
    csv_paths: Dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL and COPY statements."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ddl = generate_postgresql_ddl()

    copy_order = [
        "zonas",
        "repartidores",
        "categorias_platillo",
        "platillos",
        "promociones",
        "clima_diario",
        "ordenes",
        "detalle_ordenes",
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
                    f"\\copy raw_staging.{table} FROM '{csv_p.name}' WITH (FORMAT csv, HEADER true);\n"
                )

    logger.info(f"Generated SQL schema and load instructions at {output_file}")
    return output_file


def compute_simulation_summary(
    ordenes: List[Orden],
    detalles: List[DetalleOrden],
    clima: List[ClimaDiario],
    platillos: List[Platillo],
    zonas: List[Zona],
) -> Dict[str, Any]:
    """Compute mathematical & statistical properties of the generated dataset."""
    df_orders = pd.DataFrame([o.model_dump() for o in ordenes])
    df_details = pd.DataFrame([d.model_dump() for d in detalles])
    df_clima = pd.DataFrame([c.model_dump() for c in clima])
    df_platillos = pd.DataFrame([p.model_dump() for p in platillos])

    total_revenue = float(df_orders["total_orden"].sum())
    total_orders = len(df_orders)
    canceled_orders = int((df_orders["estado_orden"] == "cancelada").sum())
    delivered_orders = int((df_orders["estado_orden"] == "entregada").sum())
    cancellation_pct = round((canceled_orders / total_orders) * 100, 2) if total_orders > 0 else 0

    # Merge daily orders count with daily rain
    df_orders["fecha"] = pd.to_datetime(df_orders["fecha_hora_creacion"]).dt.date
    daily_order_counts = df_orders.groupby("fecha").size().reset_index(name="num_orders")
    merged_weather = pd.merge(df_clima, daily_order_counts, on="fecha", how="left").fillna(0)

    # Correlation between precipitation and daily order volume
    corr = float(merged_weather["precipitacion_mm"].corr(merged_weather["num_orders"]))

    # Chi-Square test between Zone and Dish Category
    # Join detail -> dish -> category, join detail -> order -> zone
    merged_items = df_details.merge(
        df_platillos[["id_platillo", "id_categoria"]], on="id_platillo", how="left"
    ).merge(
        df_orders[["id_orden", "id_zona"]], on="id_orden", how="left"
    )

    contingency_table = pd.crosstab(merged_items["id_zona"], merged_items["id_categoria"])

    # Chi-Square computation using scipy
    chi2_stat, p_val, dof, _ = chi2_contingency(contingency_table)

    summary = {
        "city": CITY_NAME,
        "year": SIMULATION_YEAR,
        "date_range": [START_DATE, END_DATE],
        "total_orders": total_orders,
        "total_line_items": len(df_details),
        "total_revenue_nio": round(total_revenue, 2),
        "delivered_orders": delivered_orders,
        "canceled_orders": canceled_orders,
        "cancellation_rate_pct": cancellation_pct,
        "daily_orders_mean": round(float(daily_order_counts["num_orders"].mean()), 2),
        "daily_orders_min": int(daily_order_counts["num_orders"].min()),
        "daily_orders_max": int(daily_order_counts["num_orders"].max()),
        "weather_order_correlation": round(corr, 4),
        "chi_square_test_zone_vs_category": {
            "test_description": "Estadistica II Hypothesis Test: Independence between Zona and Categoria",
            "chi2_statistic": round(float(chi2_stat), 4),
            "degrees_of_freedom": int(dof),
            "p_value": float(p_val),
            "guarantee_p_less_than_0_01": bool(p_val < 0.01),
        },
    }

    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Wrote summary verification report to {summary_path}")
    return summary
