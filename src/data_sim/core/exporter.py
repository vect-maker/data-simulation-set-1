"""Core Exporter Engine.

Handles standard generation of:
- CSV relational artifacts
- PostgreSQL consolidated DDL and data load scripts
- Academic summary JSON metrics
"""

import json
import logging
from pathlib import Path
from typing import Any
from pydantic import BaseModel
import pandas as pd

logger = logging.getLogger(__name__)


def export_models_to_csv(
    tables: dict[str, list[BaseModel | dict[str, Any]]],
    output_dir: Path,
) -> dict[str, Path]:
    """Export list of Pydantic models or dicts to clean CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = {}

    for table_name, records in tables.items():
        csv_path = output_dir / f"{table_name}.csv"
        if isinstance(records, pd.DataFrame):
            df = records.copy()
        elif hasattr(records, "to_dataframe"):
            df = records.to_dataframe()
        elif not records:
            df = pd.DataFrame()
        elif isinstance(records[0], BaseModel):
            df = pd.DataFrame([r.model_dump() if isinstance(r, BaseModel) else r for r in records])
        else:
            df = pd.DataFrame(records)

        for col in df.columns:
            if (col.startswith("id_") or col.endswith("_id") or col == "id") and pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].astype("Int64")

        df.to_csv(csv_path, index=False, encoding="utf-8")
        exported_files[table_name] = csv_path
        logger.info(f"Exported {len(df)} rows to {csv_path}")

    return exported_files


def export_models_to_parquet(
    tables: dict[str, list[BaseModel | dict[str, Any]]],
    output_dir: Path,
    compression: str = "snappy",
) -> dict[str, Path]:
    """Export list of Pydantic models or dicts to clean Apache Parquet files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files = {}

    for table_name, records in tables.items():
        parquet_path = output_dir / f"{table_name}.parquet"
        if isinstance(records, pd.DataFrame):
            df = records.copy()
        elif hasattr(records, "to_dataframe"):
            df = records.to_dataframe()
        elif not records:
            df = pd.DataFrame()
        elif isinstance(records[0], BaseModel):
            df = pd.DataFrame([r.model_dump() if isinstance(r, BaseModel) else r for r in records])
        else:
            df = pd.DataFrame(records)

        for col in df.columns:
            if (col.startswith("id_") or col.endswith("_id") or col == "id") and pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].astype("Int64")

        df.to_parquet(parquet_path, index=False, engine="pyarrow", compression=compression)
        exported_files[table_name] = parquet_path
        logger.info(f"Exported {len(df)} rows to {parquet_path}")

    return exported_files


def write_json_summary(summary: dict[str, Any], output_path: Path) -> Path:
    """Save simulation summary metrics to formatted JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def json_converter(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        if hasattr(o, "item"):
            return o.item()
        return str(o)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=json_converter)

    logger.info(f"Summary metrics saved to {output_path}")
    return output_path


def build_sql_dump(
    output_file: Path,
    schema_name: str,
    ddl_content: str,
    copy_order: list[str],
    table_paths: dict[str, Path] | None = None,
    csv_paths: dict[str, Path] | None = None,
    post_load_ddl: str = "",
) -> Path:
    """Generate consolidated SQL file with DDL, COPY statements, and analytical views."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    paths = table_paths or csv_paths or {}

    with open(output_file, "w", encoding="utf-8") as sql_f:
        sql_f.write(ddl_content)
        sql_f.write("\n-- =========================================================\n")
        sql_f.write("-- DATA LOAD INSTRUCTIONS (psql COPY)\n")
        sql_f.write("-- =========================================================\n\n")

        for table in copy_order:
            file_p = paths.get(table)
            if file_p and file_p.exists():
                if file_p.suffix == ".parquet":
                    sql_f.write(
                        f"-- Parquet: {schema_name}.{table} -> '{file_p.name}' (Load via 'just load-movigo' or duckdb/dlt)\n"
                    )
                else:
                    sql_f.write(
                        f"\\copy {schema_name}.{table} FROM '{file_p.name}' WITH (FORMAT csv, HEADER true);\n"
                    )

        if post_load_ddl:
            sql_f.write("\n")
            sql_f.write(post_load_ddl)

    logger.info(f"Generated SQL schema and load instructions at {output_file}")
    return output_file
