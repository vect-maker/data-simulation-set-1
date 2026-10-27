#!/usr/bin/env python3
"""Dedicated PostgreSQL ingestion script for MoviGo Apache Parquet datasets.

Reads Snappy-compressed .parquet files from artifacts/movigo/parquet/ via streaming
PyArrow batches, creates the raw_staging_movigo 3NF relational schema, and bulk-loads
records in configurable batches using psycopg2.extras.execute_values in strict
foreign-key dependency order with real-time progress logging and throughput telemetry.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
import psycopg2
import pyarrow.parquet as pq
from psycopg2.extras import execute_values
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from movigo_sim.config import (
    PARQUET_ARTIFACTS_DIR,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_SCHEMA,
)
from movigo_sim.exporter import (
    generate_movigo_postgresql_ddl,
    generate_movigo_post_load_ddl,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("movigo_sim.loader")
console = Console()

# Tables ordered by relational foreign key dependency
TABLE_LOAD_ORDER = [
    "urban_zones",
    "quadrants",
    "drainage_channels",
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
    "vehicle_maintenance",
]


class TableLoadResult(NamedTuple):
    """Result summary of a single table ingestion."""
    row_count: int
    batch_count: int
    elapsed_seconds: float


def clean_record_value(val: Any) -> Any:
    """Clean Pandas/Numpy scalars to Python primitives for psycopg2."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(val).to_pydatetime()
    return val


def load_parquet_table(
    cursor: psycopg2.extensions.cursor,
    parquet_path: Path,
    table_name: str,
    schema: str,
    batch_size: int = 10000,
    conn: psycopg2.extensions.connection | None = None,
    table_idx: int | None = None,
    total_tables: int | None = None,
) -> TableLoadResult:
    """Read parquet table in streaming batches and bulk-insert into PostgreSQL."""
    t0 = time.perf_counter()
    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        logger.warning(f"File not found: {parquet_path}. Skipping table '{table_name}'.")
        return TableLoadResult(0, 0, 0.0)

    pf = pq.ParquetFile(parquet_path)
    total_rows = pf.metadata.num_rows

    prefix = f"[{table_idx:>2}/{total_tables}] " if table_idx and total_tables else ""

    if total_rows == 0:
        logger.info(f"{prefix}Table '{table_name}': 0 rows in parquet. Skipping.")
        console.print(f"  [dim]ℹ {prefix}{table_name:<22}: 0 filas (omitida)[/dim]")
        return TableLoadResult(0, 0, time.perf_counter() - t0)

    total_batches = (total_rows + batch_size - 1) // batch_size
    cols = pf.schema_arrow.names
    cols_sql = ", ".join(f'"{c}"' for c in cols)
    insert_sql = f'INSERT INTO "{schema}"."{table_name}" ({cols_sql}) VALUES %s ON CONFLICT DO NOTHING;'

    if total_batches > 1:
        console.print(
            f"[bold blue]{prefix}Cargando[/bold blue] [bold cyan]{table_name}[/bold cyan] "
            f"([magenta]{total_rows:,}[/magenta] filas en [yellow]{total_batches}[/yellow] lotes de {batch_size:,})..."
        )
        logger.info(
            f"{prefix}Starting streaming batch load for '{table_name}': "
            f"{total_rows:,} total rows across {total_batches} batches (batch_size={batch_size:,})"
        )

    rows_loaded = 0
    batches_loaded = 0

    for batch_num, batch in enumerate(pf.iter_batches(batch_size=batch_size), start=1):
        t_b0 = time.perf_counter()
        df_batch = batch.to_pandas()
        raw_tuples = df_batch.itertuples(index=False, name=None)
        records = [[clean_record_value(x) for x in row] for row in raw_tuples]

        execute_values(cursor, insert_sql, records, page_size=min(len(records), 2000))
        if conn is not None:
            conn.commit()

        batch_len = len(records)
        rows_loaded += batch_len
        batches_loaded += 1
        t_b_elapsed = time.perf_counter() - t_b0
        batch_rate = batch_len / max(0.0001, t_b_elapsed)

        pct = (rows_loaded / total_rows) * 100.0
        elapsed_so_far = time.perf_counter() - t0
        avg_rate = rows_loaded / max(0.0001, elapsed_so_far)
        remaining_rows = total_rows - rows_loaded
        eta_sec = remaining_rows / max(1.0, avg_rate)

        if total_batches > 1:
            eta_str = f"{eta_sec:.1f}s" if eta_sec < 60 else f"{int(eta_sec // 60)}m {int(eta_sec % 60):02d}s"
            console.print(
                f"  [dim]↳ Lote {batch_num:>3}/{total_batches}:[/dim] "
                f"[magenta]{rows_loaded:>10,}[/magenta]/[bold]{total_rows:,}[/bold] filas "
                f"([cyan]{pct:5.1f}%[/cyan]) | "
                f"[green]{t_b_elapsed:6.3f}s[/green] | "
                f"[yellow]{batch_rate:>7,.0f} filas/s[/yellow] | "
                f"[dim]ETA: {eta_str}[/dim]"
            )
            logger.info(
                f"[{table_name}] Batch {batch_num}/{total_batches}: {rows_loaded:,}/{total_rows:,} rows ({pct:.1f}%) "
                f"loaded in {t_b_elapsed:.3f}s ({batch_rate:,.0f} rows/s, ETA: {eta_str})"
            )

    elapsed_total = time.perf_counter() - t0
    final_rate = rows_loaded / max(0.0001, elapsed_total)

    if total_batches == 1:
        console.print(
            f"  [green]✓[/green] [bold]{prefix}{table_name:<22}[/bold] "
            f"[magenta]{rows_loaded:>8,}[/magenta] filas (1 lote) en "
            f"[green]{elapsed_total:6.3f}s[/green] "
            f"([yellow]{final_rate:>8,.0f} filas/s[/yellow])"
        )
        logger.info(
            f"{prefix}Table '{table_name}': loaded {rows_loaded:,} rows in {elapsed_total:.3f}s ({final_rate:,.0f} rows/s)"
        )
    else:
        console.print(
            f"  [bold green]✓[/bold green] [bold cyan]{prefix}{table_name:<22}[/bold cyan] "
            f"[bold magenta]{rows_loaded:>8,}[/bold magenta] filas completadas en "
            f"[bold green]{elapsed_total:6.2f}s[/bold green] "
            f"([bold yellow]{final_rate:>8,.0f} filas/s[/bold yellow] en {batches_loaded} lotes)\n"
        )
        logger.info(
            f"{prefix}Table '{table_name}' completed: {rows_loaded:,} rows across {batches_loaded} batches "
            f"in {elapsed_total:.2f}s ({final_rate:,.0f} rows/s)"
        )

    return TableLoadResult(rows_loaded, batches_loaded, elapsed_total)


def load_all_movigo_parquet(
    parquet_dir: Path = PARQUET_ARTIFACTS_DIR,
    schema: str = POSTGRES_SCHEMA,
    host: str = POSTGRES_HOST,
    port: int = POSTGRES_PORT,
    db: str = POSTGRES_DB,
    user: str = POSTGRES_USER,
    password: str = POSTGRES_PASSWORD,
    batch_size: int = 10000,
) -> dict[str, Any]:
    """Execute complete ingestion pipeline from Parquet files into PostgreSQL in batches."""
    parquet_dir = Path(parquet_dir).resolve()
    if not parquet_dir.exists():
        raise FileNotFoundError(
            f"Parquet directory not found at {parquet_dir}. "
            "Please run 'movigo-sim generate' or 'just generate-movigo' first."
        )

    console.print(
        Panel.fit(
            f"[bold magenta]MoviGo Parquet to PostgreSQL Streaming Batch Ingestion[/bold magenta]\n"
            f"[cyan]Origen:       {parquet_dir}\n"
            f"Destino:      {user}@{host}:{port}/{db} (Esquema: {schema})\n"
            f"Lote Ingesta: {batch_size:,} filas/lote[/cyan]",
            border_style="magenta",
        )
    )
    logger.info(
        f"Starting MoviGo Parquet ingestion: source={parquet_dir}, target={user}@{host}:{port}/{db}, "
        f"schema={schema}, batch_size={batch_size:,}"
    )

    t_start = time.perf_counter()
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=db,
        user=user,
        password=password,
    )
    conn.autocommit = False

    load_stats: list[tuple[str, int, int, float]] = []
    total_tbls = len(TABLE_LOAD_ORDER)

    try:
        with conn.cursor() as cur:
            console.print("[bold cyan]1. Ejecutando DDL base (esquema, 14 tablas 3NF, claves primarias y foráneas)...[/bold cyan]")
            logger.info("Executing base relational DDL...")
            ddl_sql = generate_movigo_postgresql_ddl()
            cur.execute(ddl_sql)
            conn.commit()
            console.print("[green]✓ Esquema relacional inicializado correctamente.[/green]\n")

            console.print(f"[bold cyan]2. Ingestando datos Parquet en lotes de {batch_size:,} (orden de dependencias FK)...[/bold cyan]")
            logger.info(f"Bulk-loading {total_tbls} tables in foreign-key dependency order...")

            for idx, tbl in enumerate(TABLE_LOAD_ORDER, start=1):
                p_file = parquet_dir / f"{tbl}.parquet"
                if not p_file.exists():
                    console.print(f"[yellow]⚠️  Advertencia: Archivo {p_file.name} no encontrado. Omitiendo '{tbl}'.[/yellow]")
                    logger.warning(f"File {p_file.name} not found. Skipping table '{tbl}'.")
                    continue

                res = load_parquet_table(
                    cursor=cur,
                    parquet_path=p_file,
                    table_name=tbl,
                    schema=schema,
                    batch_size=batch_size,
                    conn=conn,
                    table_idx=idx,
                    total_tables=total_tbls,
                )
                load_stats.append((tbl, res.row_count, res.batch_count, res.elapsed_seconds))

            console.print("[bold cyan]3. Ejecutando DDL post-carga (vistas materializadas, analíticas y roles)...[/bold cyan]")
            logger.info("Executing post-load DDL (materialized views and analytics)...")
            post_sql = generate_movigo_post_load_ddl()
            cur.execute(post_sql)
            conn.commit()
            console.print("[green]✓ Vistas analíticas y materializadas actualizadas exitosamente.[/green]\n")

    except Exception as exc:
        conn.rollback()
        logger.error(f"Failed loading Parquet into PostgreSQL: {exc}", exc_info=True)
        console.print(f"[bold red]❌ Error durante la ingesta a PostgreSQL: {exc}[/bold red]")
        raise
    finally:
        conn.close()

    total_time = time.perf_counter() - t_start
    total_rows = sum(r for _, r, _, _ in load_stats)
    total_batches = sum(b for _, _, b, _ in load_stats)
    overall_rate = total_rows / max(0.001, total_time)

    # Render summary table
    table = Table(title="MoviGo: Resumen de Carga Parquet en Lotes -> PostgreSQL", border_style="bright_green")
    table.add_column("Tabla", style="cyan", justify="left")
    table.add_column("Filas Cargadas", style="magenta", justify="right")
    table.add_column("Lotes", style="blue", justify="right")
    table.add_column("Tiempo Ingesta", style="green", justify="right")
    table.add_column("Rendimiento", style="yellow", justify="right")

    for tbl, rows, batches, sec in load_stats:
        rate = f"{(rows / max(0.001, sec)):,.0f} filas/s" if rows > 0 else "-"
        table.add_row(tbl, f"{rows:,}", f"{batches:,}", f"{sec:.3f} s", rate)

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_rows:,}[/bold]",
        f"[bold]{total_batches:,}[/bold]",
        f"[bold]{total_time:.2f} s[/bold]",
        f"[bold]{overall_rate:,.0f} filas/s[/bold]",
    )
    console.print(table)
    console.print(
        f"[bold green]✓ Ingesta completada con éxito: {total_rows:,} filas en {total_batches:,} lotes "
        f"a través de {len(load_stats)} tablas en {total_time:.2f}s ({overall_rate:,.0f} filas/s).[/bold green]"
    )
    logger.info(
        f"Ingestion completed: {total_rows:,} rows across {total_batches:,} batches in {total_time:.2f}s ({overall_rate:,.0f} rows/s)"
    )

    return {
        "total_rows": total_rows,
        "total_batches": total_batches,
        "total_time_seconds": total_time,
        "tables": {t: {"rows": r, "batches": b, "seconds": s} for t, r, b, s in load_stats},
    }


def main():
    parser = argparse.ArgumentParser(
        description="Load MoviGo Apache Parquet datasets into PostgreSQL in streaming batches (schema raw_staging_movigo)"
    )
    parser.add_argument(
        "--parquet-dir",
        type=str,
        default=str(PARQUET_ARTIFACTS_DIR),
        help=f"Path to Parquet artifacts directory (default: {PARQUET_ARTIFACTS_DIR})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for streaming Parquet ingestion (default: 10000)",
    )
    parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help=f"PostgreSQL target schema (default: {POSTGRES_SCHEMA})")
    parser.add_argument("--host", type=str, default=POSTGRES_HOST, help="PostgreSQL host")
    parser.add_argument("--port", type=int, default=POSTGRES_PORT, help="PostgreSQL port")
    parser.add_argument("--db", type=str, default=POSTGRES_DB, help="PostgreSQL database")
    parser.add_argument("--user", type=str, default=POSTGRES_USER, help="PostgreSQL user")
    parser.add_argument("--password", type=str, default=POSTGRES_PASSWORD, help="PostgreSQL password")

    args = parser.parse_args()
    try:
        load_all_movigo_parquet(
            parquet_dir=Path(args.parquet_dir),
            schema=args.schema,
            host=args.host,
            port=args.port,
            db=args.db,
            user=args.user,
            password=args.password,
            batch_size=args.batch_size,
        )
    except Exception as e:
        console.print(f"[bold red]Load failed: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
