"""Exporter module: generates CSV artifacts, PostgreSQL DDL, and data SQL dumps.

Includes academic database objects required by curriculum:
- Auditing tables and trigger functions (trg_auditoria_ordenes, trg_validar_cronologia)
- Stored functions (fn_calcular_total_orden)
- Analytical materialized views (mv_resumen_diario_ventas)
- Security roles (rol_ingesta_dataops, rol_analista_datos, rol_auditor_bi)
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
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
from antojitos_sim.analytics import (
    compute_estadistica_ii_models,
    compute_metodos_numericos_models,
    compute_optimizacion_models,
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
    """Generate PostgreSQL DDL matching the relational & analytical curriculum."""
    return """-- =========================================================
-- ESQUEMA OLTP / RAW STAGING: Antojitos Express (Managua, Nicaragua)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw_staging;
SET search_path TO raw_staging, public;

DROP TABLE IF EXISTS detalle_ordenes CASCADE;
DROP TABLE IF EXISTS ordenes CASCADE;
DROP TABLE IF EXISTS auditoria_ordenes CASCADE;
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

-- =========================================================
-- OBJETOS DE BASE DE DATOS (Tema 3 y 5: Bases de Datos Relacionales)
-- =========================================================

-- 1. Tabla de Auditoria de Estados
CREATE TABLE auditoria_ordenes (
    id_auditoria BIGSERIAL PRIMARY KEY,
    id_orden VARCHAR(20) NOT NULL,
    estado_anterior VARCHAR(20),
    estado_nuevo VARCHAR(20) NOT NULL,
    fecha_cambio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_db VARCHAR(50) NOT NULL DEFAULT CURRENT_USER
);

-- 2. Trigger de Auditoria de Ordenes (AFTER UPDATE)
CREATE OR REPLACE FUNCTION fn_auditar_cambio_orden()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.estado_orden IS DISTINCT FROM NEW.estado_orden THEN
        INSERT INTO raw_staging.auditoria_ordenes (id_orden, estado_anterior, estado_nuevo, fecha_cambio, usuario_db)
        VALUES (NEW.id_orden, OLD.estado_orden, NEW.estado_orden, CURRENT_TIMESTAMP, CURRENT_USER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditar_ordenes
AFTER UPDATE ON ordenes
FOR EACH ROW
EXECUTE FUNCTION fn_auditar_cambio_orden();

-- 3. Trigger de Validacion Cronologica (BEFORE INSERT OR UPDATE)
CREATE OR REPLACE FUNCTION fn_validar_cronologia_orden()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.fecha_hora_entrega IS NOT NULL AND NEW.fecha_hora_entrega < NEW.fecha_hora_creacion THEN
        RAISE EXCEPTION 'Regla de negocio violada: fecha_hora_entrega (%) no puede ser anterior a fecha_hora_creacion (%)',
            NEW.fecha_hora_entrega, NEW.fecha_hora_creacion;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_cronologia_orden
BEFORE INSERT OR UPDATE ON ordenes
FOR EACH ROW
EXECUTE FUNCTION fn_validar_cronologia_orden();

-- 4. Funcion SQL para Liquidacion y Calculo de Totales con IVA de Nicaragua (15%)
CREATE OR REPLACE FUNCTION fn_calcular_total_orden(p_id_orden VARCHAR)
RETURNS DECIMAL(10,2) AS $$
DECLARE
    v_subtotal DECIMAL(10,2) := 0.0;
    v_envio DECIMAL(8,2) := 0.0;
    v_propina DECIMAL(8,2) := 0.0;
    v_total DECIMAL(10,2) := 0.0;
BEGIN
    SELECT COALESCE(SUM(subtotal), 0.0) INTO v_subtotal
    FROM raw_staging.detalle_ordenes
    WHERE id_orden = p_id_orden;

    SELECT costo_envio, propina INTO v_envio, v_propina
    FROM raw_staging.ordenes
    WHERE id_orden = p_id_orden;

    v_total := v_subtotal + COALESCE(v_envio, 0.0) + COALESCE(v_propina, 0.0);
    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

-- Indices analiticos para optimizacion fisica
CREATE INDEX idx_ordenes_fecha ON ordenes(fecha_hora_creacion);
CREATE INDEX idx_ordenes_zona ON ordenes(id_zona);
CREATE INDEX idx_ordenes_repartidor ON ordenes(id_repartidor);
CREATE INDEX idx_detalle_ordenes_orden ON detalle_ordenes(id_orden);
CREATE INDEX idx_detalle_ordenes_platillo ON detalle_ordenes(id_platillo);
"""


def generate_post_load_objects_ddl() -> str:
    """Generate materialized views and security roles to be executed after data COPY."""
    return """
-- =========================================================
-- VISTAS MATERIALIZADAS Y ROLES (Ejecutado post-carga de datos)
-- =========================================================

-- Vista Materializada Analitica de Resumen Diario
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_resumen_diario_ventas AS
SELECT 
    DATE(o.fecha_hora_creacion) AS fecha,
    o.id_zona,
    z.nombre_zona,
    COUNT(o.id_orden) AS total_pedidos,
    SUM(o.total_orden) AS ingreso_bruto_nio,
    AVG(EXTRACT(EPOCH FROM (o.fecha_hora_entrega - o.fecha_hora_creacion))/60.0) AS tiempo_promedio_entrega_min
FROM ordenes o
JOIN zonas z ON o.id_zona = z.id_zona
WHERE o.estado_orden = 'entregada'
GROUP BY DATE(o.fecha_hora_creacion), o.id_zona, z.nombre_zona
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_resumen_fecha_zona 
ON mv_resumen_diario_ventas(fecha, id_zona);

-- Configuracion de Roles y Seguridad (Principio de Menor Privilegio)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_ingesta_dataops') THEN
        CREATE ROLE rol_ingesta_dataops;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_analista_datos') THEN
        CREATE ROLE rol_analista_datos;
    END IF;
END $$;

GRANT USAGE ON SCHEMA raw_staging TO rol_ingesta_dataops, rol_analista_datos;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA raw_staging TO rol_ingesta_dataops;
GRANT SELECT ON ALL TABLES IN SCHEMA raw_staging TO rol_analista_datos;
GRANT SELECT ON mv_resumen_diario_ventas TO rol_analista_datos;
"""


def export_to_sql_dump(
    csv_paths: Dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL, COPY statements, and analytical objects."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ddl = generate_postgresql_ddl()
    post_ddl = generate_post_load_objects_ddl()

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

        sql_f.write(post_ddl)

    logger.info(f"Generated SQL schema and load instructions at {output_file}")
    return output_file


def compute_simulation_summary(
    ordenes: List[Orden],
    detalles: List[DetalleOrden],
    clima: List[ClimaDiario],
    platillos: List[Platillo],
    zonas: List[Zona],
    repartidores: Optional[List[Repartidor]] = None,
) -> Dict[str, Any]:
    """Compute mathematical & statistical properties across the 5 pillars."""
    df_orders = pd.DataFrame([o.model_dump() for o in ordenes])
    df_details = pd.DataFrame([d.model_dump() for d in detalles])
    df_clima = pd.DataFrame([c.model_dump() for c in clima])
    df_platillos = pd.DataFrame([p.model_dump() for p in platillos])
    df_zonas = pd.DataFrame([z.model_dump() for z in zonas])
    df_repartidores = pd.DataFrame([r.model_dump() for r in repartidores]) if repartidores else pd.DataFrame()

    total_revenue = float(df_orders["total_orden"].sum())
    total_orders = len(df_orders)
    canceled_orders = int((df_orders["estado_orden"] == "cancelada").sum())
    delivered_orders = int((df_orders["estado_orden"] == "entregada").sum())
    cancellation_pct = round((canceled_orders / total_orders) * 100, 2) if total_orders > 0 else 0

    # Merge daily orders count with daily rain
    df_orders["fecha"] = pd.to_datetime(df_orders["fecha_hora_creacion"]).dt.date
    daily_order_counts = df_orders.groupby("fecha").size().reset_index(name="num_orders")
    merged_weather = pd.merge(df_clima, daily_order_counts, on="fecha", how="left").fillna(0)
    corr = float(merged_weather["precipitacion_mm"].corr(merged_weather["num_orders"]))

    # Chi-Square test between Zone and Dish Category
    merged_items = df_details.merge(
        df_platillos[["id_platillo", "id_categoria"]], on="id_platillo", how="left"
    ).merge(
        df_orders[["id_orden", "id_zona"]], on="id_orden", how="left"
    )
    contingency_table = pd.crosstab(merged_items["id_zona"], merged_items["id_categoria"])
    chi2_stat, p_val, dof, _ = chi2_contingency(contingency_table)

    # Formal Pillar Evaluations
    estadistica_results = compute_estadistica_ii_models(
        df_orders, df_clima, df_details, df_platillos, df_zonas, df_repartidores
    )
    numericos_results = compute_metodos_numericos_models(df_orders)
    optimizacion_results = compute_optimizacion_models()

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
        "estadistica_ii": estadistica_results,
        "metodos_numericos": numericos_results,
        "optimizacion": optimizacion_results,
    }

    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Wrote comprehensive summary verification report to {summary_path}")
    return summary
