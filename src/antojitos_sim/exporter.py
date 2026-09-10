"""Exporter module for Antojitos Express.

Generates CSV artifacts, PostgreSQL DDL, and data SQL dumps.
"""

import logging
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np

from data_sim.core.exporter import export_models_to_csv, write_json_summary, build_sql_dump
from data_sim.core.stats import compute_contingency_chi2

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
    zonas: list[Zona],
    repartidores: list[Repartidor],
    categorias: list[CategoriaPlatillo],
    platillos: list[Platillo],
    promociones: list[Promocion],
    clima: list[ClimaDiario],
    ordenes: list[Orden],
    detalles: list[DetalleOrden],
    output_dir: Path = CSV_ARTIFACTS_DIR,
) -> dict[str, Path]:
    """Export all relational tables to standard CSV format."""
    tables = {
        "zonas": zonas,
        "repartidores": repartidores,
        "categorias_platillo": categorias,
        "platillos": platillos,
        "promociones": promociones,
        "clima_diario": clima,
        "ordenes": ordenes,
        "detalle_ordenes": detalles,
    }
    return export_models_to_csv(tables, output_dir)


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
    id_zona INT PRIMARY KEY,
    nombre_zona VARCHAR(100) NOT NULL,
    latitud DECIMAL(9,6) NOT NULL,
    longitud DECIMAL(9,6) NOT NULL,
    distancia_km DECIMAL(5,2) NOT NULL,
    tiempo_base_minutos INT NOT NULL,
    tarifa_envio_base DECIMAL(8,2) NOT NULL
);

CREATE TABLE repartidores (
    id_repartidor INT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tipo_vehiculo VARCHAR(20) NOT NULL CHECK (tipo_vehiculo IN ('moto', 'bicicleta', 'auto')),
    calificacion_promedio DECIMAL(3,2) NOT NULL,
    capacidad_maxima_ordenes INT NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('activo', 'inactivo', 'descanso'))
);

CREATE TABLE categorias_platillo (
    id_categoria INT PRIMARY KEY,
    nombre_categoria VARCHAR(50) NOT NULL,
    margen_contribucion_pct DECIMAL(4,2) NOT NULL
);

CREATE TABLE platillos (
    id_platillo INT PRIMARY KEY,
    id_categoria INT NOT NULL REFERENCES categorias_platillo(id_categoria),
    nombre_platillo VARCHAR(100) NOT NULL,
    precio_unitario DECIMAL(8,2) NOT NULL CHECK (precio_unitario > 0),
    costo_ingredientes DECIMAL(8,2) NOT NULL CHECK (costo_ingredientes > 0),
    tiempo_preparacion_minutos DECIMAL(4,1) NOT NULL,
    requiere_horno BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE promociones (
    id_promocion INT PRIMARY KEY,
    nombre_campana VARCHAR(100) NOT NULL,
    costo_campana DECIMAL(10,2) NOT NULL,
    retorno_esperado DECIMAL(10,2) NOT NULL,
    descuento_pct DECIMAL(4,2) NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL
);

CREATE TABLE clima_diario (
    fecha DATE PRIMARY KEY,
    precipitacion_mm DECIMAL(6,2) NOT NULL,
    temperatura_c DECIMAL(4,1) NOT NULL,
    condicion_cielo VARCHAR(20) NOT NULL CHECK (condicion_cielo IN ('despejado', 'lluvia_ligera', 'tormenta', 'nublado'))
);

CREATE TABLE ordenes (
    id_orden INT PRIMARY KEY,
    id_zona INT NOT NULL REFERENCES zonas(id_zona),
    id_repartidor INT REFERENCES repartidores(id_repartidor),
    id_promocion INT REFERENCES promociones(id_promocion),
    fecha_hora_creacion TIMESTAMP NOT NULL,
    fecha_hora_entrega TIMESTAMP,
    metodo_pago VARCHAR(20) NOT NULL CHECK (metodo_pago IN ('efectivo', 'tarjeta', 'billetera_digital')),
    estado_orden VARCHAR(20) NOT NULL CHECK (estado_orden IN ('entregada', 'cancelada', 'en_camino', 'preparando')),
    total_orden DECIMAL(10,2) NOT NULL CHECK (total_orden >= 0),
    costo_envio DECIMAL(8,2) NOT NULL CHECK (costo_envio >= 0),
    propina DECIMAL(8,2) NOT NULL DEFAULT 0.0 CHECK (propina >= 0),
    notas_entrega TEXT,
    comentario_cliente TEXT,
    motivo_cancelacion TEXT
);

CREATE TABLE detalle_ordenes (
    id_detalle INT PRIMARY KEY,
    id_orden INT NOT NULL REFERENCES ordenes(id_orden) ON DELETE CASCADE,
    id_platillo INT NOT NULL REFERENCES platillos(id_platillo),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    precio_unitario DECIMAL(8,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL
);

-- Tabla de Auditoria de Estados
CREATE TABLE auditoria_ordenes (
    id_auditoria SERIAL PRIMARY KEY,
    id_orden INT NOT NULL,
    estado_anterior VARCHAR(20),
    estado_nuevo VARCHAR(20),
    fecha_cambio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_db VARCHAR(50) NOT NULL DEFAULT CURRENT_USER
);

-- Trigger de Auditoria
CREATE OR REPLACE FUNCTION fn_trg_auditar_ordenes()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.estado_orden IS DISTINCT FROM NEW.estado_orden) THEN
        INSERT INTO raw_staging.auditoria_ordenes(id_orden, estado_anterior, estado_nuevo, fecha_cambio, usuario_db)
        VALUES (NEW.id_orden, OLD.estado_orden, NEW.estado_orden, CURRENT_TIMESTAMP, CURRENT_USER);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditar_ordenes
AFTER UPDATE ON ordenes
FOR EACH ROW
EXECUTE FUNCTION fn_trg_auditar_ordenes();

-- Trigger de Negocio: Validar coherencia temporal
CREATE OR REPLACE FUNCTION fn_trg_validar_cronologia_orden()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.fecha_hora_entrega IS NOT NULL AND NEW.fecha_hora_entrega < NEW.fecha_hora_creacion THEN
        RAISE EXCEPTION 'Inconsistencia temporal: la fecha de entrega (%) no puede ser anterior a la creacion (%)',
            NEW.fecha_hora_entrega, NEW.fecha_hora_creacion;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_cronologia_orden
BEFORE INSERT OR UPDATE ON ordenes
FOR EACH ROW
EXECUTE FUNCTION fn_trg_validar_cronologia_orden();

-- Procedimiento / Funcion Almacenada: Calculo de Total de Orden
CREATE OR REPLACE FUNCTION fn_calcular_total_orden(p_id_orden INT)
RETURNS DECIMAL(10,2) AS $$
DECLARE
    v_subtotal DECIMAL(10,2);
    v_envio DECIMAL(8,2);
    v_propina DECIMAL(8,2);
    v_total DECIMAL(10,2);
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

-- Configuracion de Roles y Seguridad
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
    csv_paths: dict[str, Path],
    output_file: Path = SQL_ARTIFACTS_DIR / "schema_and_data.sql",
) -> Path:
    """Generate consolidated SQL file with DDL, COPY statements, and analytical objects."""
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
    return build_sql_dump(
        output_file=output_file,
        schema_name="raw_staging",
        ddl_content=generate_postgresql_ddl(),
        copy_order=copy_order,
        csv_paths=csv_paths,
        post_load_ddl=generate_post_load_objects_ddl(),
    )


def compute_simulation_summary(
    ordenes: list[Orden],
    detalles: list[DetalleOrden],
    clima: list[ClimaDiario],
    platillos: list[Platillo],
    zonas: list[Zona],
    repartidores: list[Repartidor] | None = None,
) -> dict[str, Any]:
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

    df_orders["fecha"] = pd.to_datetime(df_orders["fecha_hora_creacion"]).dt.date
    daily_order_counts = df_orders.groupby("fecha").size().values

    # Correlation weather vs daily orders
    daily_orders_series = df_orders.groupby("fecha").size().reset_index(name="order_count")
    merged_weather = pd.merge(df_clima, daily_orders_series, on="fecha", how="left").fillna(0)
    corr_rain = float(merged_weather["precipitacion_mm"].corr(merged_weather["order_count"]))

    # Chi-Square Test: Zone vs Category
    df_merged = df_orders[["id_orden", "id_zona"]].merge(
        df_details[["id_orden", "id_platillo"]], on="id_orden"
    ).merge(
        df_platillos[["id_platillo", "id_categoria"]], on="id_platillo"
    )
    chi2_results = compute_contingency_chi2(df_merged, "id_zona", "id_categoria")

    # Multi-pillar mathematical evaluations
    est_results = compute_estadistica_ii_models(
        df_orders, df_clima, df_details, df_platillos, df_zonas, df_repartidores
    )
    num_results = compute_metodos_numericos_models(df_orders)
    opt_results = compute_optimizacion_models()

    summary = {
        "case": "antojitos_express",
        "city": CITY_NAME,
        "year": SIMULATION_YEAR,
        "date_range": [START_DATE, END_DATE],
        "total_orders": total_orders,
        "total_line_items": len(df_details),
        "total_revenue_nio": round(total_revenue, 2),
        "delivered_orders": delivered_orders,
        "canceled_orders": canceled_orders,
        "cancellation_rate_pct": cancellation_pct,
        "daily_orders_mean": round(float(np.mean(daily_order_counts)), 1) if len(daily_order_counts) else 0,
        "daily_orders_min": int(np.min(daily_order_counts)) if len(daily_order_counts) else 0,
        "daily_orders_max": int(np.max(daily_order_counts)) if len(daily_order_counts) else 0,
        "weather_order_correlation": round(corr_rain, 4),
        "chi_square_test_zone_vs_category": chi2_results,
        "estadistica_ii": est_results,
        "metodos_numericos": num_results,
        "optimizacion": opt_results,
    }

    write_json_summary(summary, ARTIFACTS_DIR / "simulation_summary.json")
    return summary
