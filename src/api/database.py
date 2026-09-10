"""Database connection pooling and query execution helpers."""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from src.api.config import settings

logger = logging.getLogger("api.database")

_pool: Optional[pool.ThreadedConnectionPool] = None


def get_pool() -> pool.ThreadedConnectionPool:
    """Retrieve or initialize the PostgreSQL connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = pool.ThreadedConnectionPool(
            minconn=settings.POOL_MIN_CONN,
            maxconn=settings.POOL_MAX_CONN,
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            dbname=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
        )
        logger.info("Initialized PostgreSQL connection pool to %s:%s/%s",
                    settings.POSTGRES_HOST, settings.POSTGRES_PORT, settings.POSTGRES_DB)
    return _pool


def close_pool() -> None:
    """Close all connections in the pool."""
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.closeall()
        logger.info("Closed PostgreSQL connection pool.")


@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for acquiring and returning pooled connections."""
    conn_pool = get_pool()
    conn = conn_pool.getconn()
    try:
        conn.autocommit = True
        yield conn
    finally:
        conn_pool.putconn(conn)


def check_db_health() -> Tuple[bool, Optional[str]]:
    """Verify connectivity to PostgreSQL."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return True, None
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False, str(exc)


def fetch_all(query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return all rows as dictionaries."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def fetch_one(query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Dict[str, Any]]:
    """Execute a SELECT query and return a single row or None."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            row = cur.fetchone()
            return dict(row) if row else None


def fetch_count(query: str, params: Optional[Tuple[Any, ...]] = None) -> int:
    """Execute a SELECT COUNT query and return integer count."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            res = cur.fetchone()
            return int(res[0]) if res else 0
