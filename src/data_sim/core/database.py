"""Core Database & Staging Engine.

Provides unified database operations:
- Connection verification and healthchecks
- SQL script execution (local psql / Podman or Docker container exec fallback)
- Table verification and row count inspection
"""

import os
import subprocess
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
DEFAULT_POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
DEFAULT_POSTGRES_DB = os.getenv("POSTGRES_DB", "integrador_db")
DEFAULT_POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
DEFAULT_POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")


def get_connection_url(
    host: str = DEFAULT_POSTGRES_HOST,
    port: int = DEFAULT_POSTGRES_PORT,
    db: str = DEFAULT_POSTGRES_DB,
    user: str = DEFAULT_POSTGRES_USER,
    password: str = DEFAULT_POSTGRES_PASSWORD,
) -> str:
    """Construct PostgreSQL standard connection string."""
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def is_postgres_available(
    host: str = DEFAULT_POSTGRES_HOST,
    port: int = DEFAULT_POSTGRES_PORT,
    db: str = DEFAULT_POSTGRES_DB,
    user: str = DEFAULT_POSTGRES_USER,
    password: str = DEFAULT_POSTGRES_PASSWORD,
) -> bool:
    """Test PostgreSQL connectivity via psycopg2 or socket."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=db,
            user=user,
            password=password,
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


def load_sql_script(
    sql_file: Path,
    working_dir: Path,
    db_name: str = DEFAULT_POSTGRES_DB,
    user: str = DEFAULT_POSTGRES_USER,
    password: str = DEFAULT_POSTGRES_PASSWORD,
    host: str = DEFAULT_POSTGRES_HOST,
    port: int = DEFAULT_POSTGRES_PORT,
) -> bool:
    """Execute SQL dump containing \\copy statements via Podman compose exec."""
    if not sql_file.exists():
        logger.error(f"SQL file not found: {sql_file}")
        return False

    logger.info(f"Executing {sql_file.name} via Podman compose container...")
    rel_working = os.path.relpath(working_dir, Path.cwd())
    rel_sql = os.path.relpath(sql_file, working_dir)
    container_workdir = f"/workspace/{rel_working}"

    cmd = [
        "podman", "compose", "exec",
        "-w", container_workdir,
        "-T", "postgres",
        "psql",
        "-U", user,
        "-d", db_name,
        "-f", rel_sql,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            logger.info(f"Successfully loaded schema via Podman compose psql: {res.stdout[-200:] if len(res.stdout) > 200 else res.stdout}")
            return True
        else:
            logger.error(f"Podman compose psql failed: {res.stderr}")
            return False
    except Exception as e:
        logger.error(f"Failed Podman compose exec: {e}")
        return False
