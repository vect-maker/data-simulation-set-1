#!/usr/bin/env python3
"""Dedicated PostgreSQL ingestion script for MoviGo Apache Parquet datasets.

Reads Snappy-compressed .parquet files from artifacts/movigo/parquet/ via Pandas,
creates the raw_staging_movigo 3NF relational schema, and bulk-loads records
using psycopg2.extras.execute_values in strict foreign-key dependency order.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg2
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
    chunk_size: int = 5000,
) -> tuple[int, float]:
    """Read single parquet table with Pandas and bulk-insert to PostgreSQL."""
    t0 = time.perf_counter()
    df = pd.read_parquet(parquet_path)
    if df.empty:
        return 0, time.perf_counter() - t0

    cols = list(df.columns)
    cols_sql = ", ".join(f'"{c}"' for c in cols)

    # Convert records to clean Python tuples replacing NaN with None
    raw_tuples = df.itertuples(index=False, name=None)
    records = [[clean_record_value(x) for x in row] for row in raw_tuples]

    insert_sql = f'INSERT INTO "{schema}"."{table_name}" ({cols_sql}) VALUES %s ON CONFLICT DO NOTHING;'
    execute_values(cursor, insert_sql, records, page_size=chunk_size)

    elapsed = time.perf_counter() - t0
    return len(records), elapsed


def load_all_movigo_parquet(
    parquet_dir: Path = PARQUET_ARTIFACTS_DIR,
    schema: str = POSTGRES_SCHEMA,
    host: str = POSTGRES_HOST,
    port: int = POSTGRES_PORT,
    db: str = POSTGRES_DB,
    user: str = POSTGRES_USER,
    password: str = POSTGRES_PASSWORD,
) -> dict[str, Any]:
    """Execute complete ingestion pipeline from Parquet files into PostgreSQL."""
    parquet_dir = Path(parquet_dir).resolve()
    if not parquet_dir.exists():
        raise FileNotFoundError(
            f"Parquet directory not found at {parquet_dir}. "
            "Please run 'movigo-sim generate' or 'just generate-movigo' first."
        )

    console.print(
        Panel.fit(
            f"[bold magenta]MoviGo Parquet to PostgreSQL Ingestion[/bold magenta]\n"
            f"[cyan]Source: {parquet_dir}\n"
            f"Target DB: {user}@{host}:{port}/{db} (Schema: {schema})[/cyan]",
            border_style="magenta",
        )
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

    load_stats: list[tuple[str, int, float]] = []
    try:
        with conn.cursor() as cur:
            console.print("[dim]1. Executing PostgreSQL DDL (tables, schemas, constraints)...[/dim]")
            ddl_sql = generate_movigo_postgresql_ddl()
            cur.execute(ddl_sql)

            console.print("[dim]2. Bulk-loading Parquet files in FK dependency order...[/dim]")
            for tbl in TABLE_LOAD_ORDER:
                p_file = parquet_dir / f"{tbl}.parquet"
                if not p_file.exists():
                    console.print(f"[yellow]⚠️  Warning: File {p_file.name} not found. Skipping table '{tbl}'.[/yellow]")
                    continue

                row_count, sec = load_parquet_table(cur, p_file, tbl, schema)
                load_stats.append((tbl, row_count, sec))

            console.print("[dim]3. Executing post-load DDL (materialized views, analytical views, roles)...[/dim]")
            post_sql = generate_movigo_post_load_ddl()
            cur.execute(post_sql)

        conn.commit()
    except Exception as exc:
        conn.rollback()
        console.print(f"[bold red]❌ Failed loading Parquet into PostgreSQL: {exc}[/bold red]")
        raise
    finally:
        conn.close()

    total_time = time.perf_counter() - t_start
    total_rows = sum(r for _, r, _ in load_stats)

    # Render summary table
    table = Table(title="MoviGo: Resumen de Carga Parquet -> PostgreSQL", border_style="bright_green")
    table.add_column("Tabla", style="cyan", justify="left")
    table.add_column("Registros Cargados", style="magenta", justify="right")
    table.add_column("Tiempo Ingesta", style="green", justify="right")
    table.add_column("Rendimiento", style="yellow", justify="right")

    for tbl, rows, sec in load_stats:
        rate = f"{(rows / max(0.001, sec)):,.0f} filas/s" if rows > 0 else "-"
        table.add_row(tbl, f"{rows:,}", f"{sec:.3f} s", rate)

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_rows:,}[/bold]",
        f"[bold]{total_time:.2f} s[/bold]",
        f"[bold]{(total_rows / max(0.001, total_time)):,.0f} filas/s[/bold]",
    )
    console.print(table)
    console.print(f"[bold green]✓ Ingestion complete! Loaded {total_rows:,} rows across {len(load_stats)} tables in {total_time:.2f}s.[/bold green]")

    return {
        "total_rows": total_rows,
        "total_time_seconds": total_time,
        "tables": {t: r for t, r, _ in load_stats},
    }


def main():
    parser = argparse.ArgumentParser(
        description="Load MoviGo Apache Parquet datasets into PostgreSQL (schema raw_staging_movigo)"
    )
    parser.add_argument(
        "--parquet-dir",
        type=str,
        default=str(PARQUET_ARTIFACTS_DIR),
        help=f"Path to Parquet artifacts directory (default: {PARQUET_ARTIFACTS_DIR})",
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
        )
    except Exception as e:
        console.print(f"[bold red]Load failed: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
