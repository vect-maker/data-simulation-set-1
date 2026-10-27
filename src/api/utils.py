"""Query building, filtering, sorting, and serialization utilities."""

import datetime
import re
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from src.api.database import fetch_all, fetch_count, fetch_one

IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_identifier(name: str) -> str:
    """Ensure schema, table, and column names are safe SQL identifiers."""
    if not IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


def sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert Postgres-specific data types (Decimals, time objects) to JSON primitives."""
    clean: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            clean[k] = float(v)
        elif isinstance(v, datetime.time):
            clean[k] = v.isoformat()
        elif isinstance(v, datetime.timedelta):
            clean[k] = str(v)
        else:
            clean[k] = v
    return clean


def execute_paginated_query(
    schema: str,
    table: str,
    filters: list[tuple[str, str, Any]] | None = None,
    sort: str | None = None,
    allowed_sort_columns: set[str] | None = None,
    default_sort: str | None = None,
    offset: int = 0,
    limit: int = 50,
    max_limit: int = 1000,
) -> dict[str, Any]:
    """Execute a parameterized, paginated query returning a standard envelope."""
    validate_identifier(schema)
    validate_identifier(table)

    where_clauses: list[str] = []
    params: list[Any] = []

    if filters:
        for col, op, val in filters:
            if val is not None:
                validate_identifier(col)
                if op in ("=", ">=", "<=", ">", "<", "LIKE", "ILIKE"):
                    where_clauses.append(f"{col} {op} %s")
                    params.append(val)
                elif op == "IN" and isinstance(val, (list, tuple)) and len(val) > 0:
                    placeholders = ", ".join(["%s"] * len(val))
                    where_clauses.append(f"{col} IN ({placeholders})")
                    params.extend(val)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Count query
    count_sql = f"SELECT COUNT(*) FROM {schema}.{table}{where_sql};"
    total = fetch_count(count_sql, tuple(params))

    # Sorting
    sort_clause = ""
    effective_sort = sort or default_sort
    if effective_sort and allowed_sort_columns:
        desc = effective_sort.startswith("-")
        col_candidate = effective_sort.lstrip("+-")
        if col_candidate in allowed_sort_columns:
            direction = "DESC" if desc else "ASC"
            sort_clause = f" ORDER BY {col_candidate} {direction}"

    # Paginated data query
    clamped_limit = max(1, min(limit, max_limit))
    clamped_offset = max(0, offset)

    data_sql = (
        f"SELECT * FROM {schema}.{table}{where_sql}{sort_clause} LIMIT %s OFFSET %s;"
    )
    query_params = tuple(params + [clamped_limit, clamped_offset])
    raw_rows = fetch_all(data_sql, query_params)
    items = [sanitize_row(r) for r in raw_rows]

    return {
        "items": items,
        "count": len(items),
        "total": total,
        "offset": clamped_offset,
        "limit": clamped_limit,
    }


def execute_aggregated_weather_query(
    schema: str,
    table: str,
    granularity: str,
    filters: list[tuple[str, str, Any]] | None = None,
    quadrant_id: int | None = None,
    by_quadrant: bool = True,
    sort: str | None = None,
    offset: int = 0,
    limit: int = 1000,
    max_limit: int = 10000,
) -> dict[str, Any]:
    """Execute temporal aggregation over meteorological & hydrological quadrant records."""
    validate_identifier(schema)
    validate_identifier(table)

    if granularity == "day":
        trunc_expr = "DATE_TRUNC('day', recorded_at)::date"
        period_end_expr = "DATE_TRUNC('day', recorded_at)::date"
    elif granularity == "week":
        trunc_expr = "DATE_TRUNC('week', recorded_at)::date"
        period_end_expr = "(DATE_TRUNC('week', recorded_at) + interval '6 days')::date"
    elif granularity == "month":
        trunc_expr = "DATE_TRUNC('month', recorded_at)::date"
        period_end_expr = "(DATE_TRUNC('month', recorded_at) + interval '1 month' - interval '1 day')::date"
    else:
        raise ValueError(f"Granularidad no admitida: '{granularity}'. Opciones: 'hour', 'day', 'week', 'month'.")

    where_clauses: list[str] = []
    params: list[Any] = []

    if filters:
        for col, op, val in filters:
            if val is not None:
                validate_identifier(col)
                if op in ("=", ">=", "<=", ">", "<", "LIKE", "ILIKE"):
                    where_clauses.append(f"{col} {op} %s")
                    params.append(val)
                elif op == "IN" and isinstance(val, (list, tuple)) and len(val) > 0:
                    placeholders = ", ".join(["%s"] * len(val))
                    where_clauses.append(f"{col} IN ({placeholders})")
                    params.extend(val)

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    if quadrant_id is not None:
        quadrant_select = "quadrant_id,"
        group_by_cols = f"{trunc_expr}, quadrant_id"
        default_order = "period_start ASC, quadrant_id ASC"
    elif by_quadrant:
        quadrant_select = "quadrant_id,"
        group_by_cols = f"{trunc_expr}, quadrant_id"
        default_order = "period_start ASC, quadrant_id ASC"
    else:
        quadrant_select = "NULL::int AS quadrant_id,"
        group_by_cols = f"{trunc_expr}"
        default_order = "period_start ASC"

    # Count distinct groups
    count_sql = f"SELECT COUNT(*) FROM (SELECT 1 FROM {schema}.{table}{where_sql} GROUP BY {group_by_cols}) AS subq;"
    total = fetch_count(count_sql, tuple(params))

    clamped_limit = max(1, min(limit, max_limit))
    clamped_offset = max(0, offset)

    order_by = sort or default_order
    if order_by and order_by.startswith("-"):
        order_clause = f" ORDER BY {order_by.lstrip('-')} DESC"
    elif order_by:
        order_clause = f" ORDER BY {order_by}"
    else:
        order_clause = f" ORDER BY {default_order}"

    data_sql = f"""
    SELECT
        {trunc_expr} AS period_start,
        {period_end_expr} AS period_end,
        {quadrant_select}
        '{granularity}' AS granularity,
        ROUND(AVG(temperature_c)::numeric, 2)::float AS avg_temperature_c,
        ROUND(MIN(temperature_c)::numeric, 2)::float AS min_temperature_c,
        ROUND(MAX(temperature_c)::numeric, 2)::float AS max_temperature_c,
        ROUND(SUM(precipitation_mm)::numeric, 2)::float AS total_precipitation_mm,
        ROUND(MAX(precipitation_mm)::numeric, 2)::float AS max_precipitation_mm,
        ROUND(AVG(channel_runoff_mm)::numeric, 2)::float AS avg_channel_runoff_mm,
        ROUND(MAX(channel_runoff_mm)::numeric, 2)::float AS max_channel_runoff_mm,
        ROUND(AVG(congestion_index)::numeric, 2)::float AS avg_congestion_index,
        COUNT(*) FILTER (WHERE flooded_roads = TRUE)::int AS flooded_hours_count,
        COUNT(*)::int AS records_count,
        MODE() WITHIN GROUP (ORDER BY sky_condition) AS dominant_sky_condition
    FROM {schema}.{table}
    {where_sql}
    GROUP BY {group_by_cols}
    {order_clause}
    LIMIT %s OFFSET %s;
    """
    raw_rows = fetch_all(data_sql, tuple(params + [clamped_limit, clamped_offset]))
    items = [sanitize_row(r) for r in raw_rows]

    return {
        "items": items,
        "count": len(items),
        "total": total,
        "offset": clamped_offset,
        "limit": clamped_limit,
    }


def fetch_single_resource(
    schema: str,
    table: str,
    id_column: str,
    id_value: Any,
) -> dict[str, Any]:
    """Fetch a single record by its primary key or raise 404."""
    validate_identifier(schema)
    validate_identifier(table)
    validate_identifier(id_column)

    sql = f"SELECT * FROM {schema}.{table} WHERE {id_column} = %s LIMIT 1;"
    row = fetch_one(sql, (id_value,))
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"{table.rstrip('s').capitalize()} with ID '{id_value}' not found in {schema}.",
        )
    return sanitize_row(row)
