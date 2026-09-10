"""Query building, filtering, sorting, and serialization utilities."""

import datetime
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException

from src.api.database import fetch_all, fetch_count, fetch_one

IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_identifier(name: str) -> str:
    """Ensure schema, table, and column names are safe SQL identifiers."""
    if not IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


def sanitize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Postgres-specific data types (Decimals, time objects) to JSON primitives."""
    clean: Dict[str, Any] = {}
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
    filters: Optional[List[Tuple[str, str, Any]]] = None,
    sort: Optional[str] = None,
    allowed_sort_columns: Optional[Set[str]] = None,
    default_sort: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> Dict[str, Any]:
    """Execute a parameterized, paginated query returning a standard envelope."""
    validate_identifier(schema)
    validate_identifier(table)

    where_clauses: List[str] = []
    params: List[Any] = []

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
    clamped_limit = max(1, min(limit, 200))
    clamped_offset = max(0, offset)

    data_sql = f"SELECT * FROM {schema}.{table}{where_sql}{sort_clause} LIMIT %s OFFSET %s;"
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


def fetch_single_resource(
    schema: str,
    table: str,
    id_column: str,
    id_value: Any,
) -> Dict[str, Any]:
    """Fetch a single record by its primary key or raise 404."""
    validate_identifier(schema)
    validate_identifier(table)
    validate_identifier(id_column)

    sql = f"SELECT * FROM {schema}.{table} WHERE {id_column} = %s LIMIT 1;"
    row = fetch_one(sql, (id_value,))
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"{table.rstrip('s').capitalize()} with ID '{id_value}' not found in {schema}."
        )
    return sanitize_row(row)
