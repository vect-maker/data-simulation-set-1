"""Configuration settings for the FastAPI application."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application and database connection settings."""
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5433"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "integrador_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")

    API_TITLE: str = "Proyecto Integrador - API de Datos Sintéticos (Nicaragua)"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = (
        "## Portal de Datos de la API del Proyecto Integrador: De los Datos a la Decisión\n\n"
        "Esta API REST pública y abierta fue diseñada para que los estudiantes del **Proyecto Integrador** "
        "puedan consultar, explorar y consumir conjuntos de datos sintéticos realistas contextualizados en Nicaragua: "
        "**Antojitos Express** (Caso 1: Cocina fantasma y delivery), **Cooperativa El Volcán** (Caso 2: Cadena de café de altura "
        "y exportación) y **MoviGo** (Caso 3: Transporte urbano y movilidad por app).\n\n"
        "### Convenciones de Uso\n"
        "- **Acceso Libre y CORS Abierto:** No requiere autenticación. Puedes consumir los endpoints desde Jupyter Notebooks, Google Colab, Python, R o cURL.\n"
        "- **Paginación Uniforme:** Todos los listados devuelven un sobre con `items`, `count`, `total`, `offset` y `limit`. Parámetros: `?limit=50&offset=0`.\n"
        "- **Ordenamiento Dinámico:** Usa `?sort=campo` para orden ascendente o `?sort=-campo` para orden descendente.\n"
        "- **Formatos de Fecha:** Fechas en estándar ISO 8601 (`YYYY-MM-DD`) y marcas de tiempo (`YYYY-MM-DDTHH:MM:SS`)."
    )

    POOL_MIN_CONN: int = int(os.getenv("DB_POOL_MIN", "1"))
    POOL_MAX_CONN: int = int(os.getenv("DB_POOL_MAX", "20"))


settings = Settings()
