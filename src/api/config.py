"""Configuration settings for the FastAPI application."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application and database connection settings."""
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "integrador_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")

    API_TITLE: str = "Proyecto Integrador - API de Datos Sintéticos (Nicaragua)"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = (
        "API REST pública y abierta para el consumo estudiantil de datos sintéticos y "
        "transaccionales en Nicaragua: Antojitos Express (Caso 1), Cooperativa El Volcán (Caso 2) "
        "y MoviGo (Caso 3)."
    )

    POOL_MIN_CONN: int = int(os.getenv("DB_POOL_MIN", "1"))
    POOL_MAX_CONN: int = int(os.getenv("DB_POOL_MAX", "20"))


settings = Settings()
