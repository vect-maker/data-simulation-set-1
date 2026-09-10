"""Core Database & Staging Engine.

Provides unified database operations:
- Connection verification and healthchecks
- SQL script execution (local psql / Docker container exec fallback)
- Table verification and row count inspection
"""

import os
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
DEFAULT_POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
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
    """Execute SQL dump containing \\copy statements via local psql or Docker exec."""
    if not sql_file.exists():
        logger.error(f"SQL file not found: {sql_file}")
        return False

    # 1. Try local psql
    if shutil.which("psql"):
        logger.info(f"Executing {sql_file.name} using local psql...")
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        cmd = [
            "psql",
            "-h", host,
            "-p", str(port),
            "-U", user,
            "-d", db_name,
            "-f", str(sql_file.resolve()),
        ]
        try:
            res = subprocess.run(cmd, cwd=working_dir, env=env, capture_output=True, text=True)
            if res.returncode == 0:
                logger.info(f"Successfully executed {sql_file.name} via psql.")
                return True
            else:
                logger.warning(f"Local psql returned error: {res.stderr}")
        except Exception as e:
            logger.warning(f"Failed local psql execution: {e}")

    # 2. Try Docker compose exec fallback
    if shutil.which("docker"):
        logger.info(f"Executing {sql_file.name} via Docker container...")
        # Relative path inside mounted /workspace
        rel_working = os.path.relpath(working_dir, Path.cwd())
        rel_sql = os.path.relpath(sql_file, working_dir)
        container_workdir = f"/workspace/{rel_working}"

        cmd = [
            "docker", "compose", "exec",
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
                logger.info(f"Successfully loaded schema via Docker psql: {res.stdout[-200:] if len(res.stdout) > 200 else res.stdout}")
                return True
            else:
                logger.error(f"Docker psql failed: {res.stderr}")
                return False
        except Exception as e:
            logger.error(f"Failed Docker exec: {e}")
            return False

    logger.error("Neither local psql nor Docker is available to execute the SQL script.")
    return False
