"""Configuration constants for MoviGo ride-hailing simulation in Managua."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src" / "movigo_sim"
SEEDS_DIR = SRC_DIR / "seeds"
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw" / "movigo"
ARTIFACTS_DIR = BASE_DIR / "artifacts" / "movigo"
CSV_ARTIFACTS_DIR = ARTIFACTS_DIR / "csv"
SQL_ARTIFACTS_DIR = ARTIFACTS_DIR / "sql"

# Geographic anchors: Managua, Nicaragua
CITY_NAME = "Managua, Nicaragua"
CITY_CENTER_LAT = 12.1364
CITY_CENTER_LON = -86.2514

# Time Horizon: Full Year 2024 (Leap year, 366 days)
SIMULATION_YEAR = 2024
START_DATE = "2024-01-01"
END_DATE = "2024-12-31"
TIMEZONE = "America/Managua"

# Weather API (Open-Meteo Managua)
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_LATITUDE = 12.1364
OPEN_METEO_LONGITUDE = -86.2514

# Fare and Surge parameters (Nicaraguan Córdobas NIO)
BASE_FLAG_DROP_NIO = 45.00
BASE_PER_KM_NIO = 22.00
BASE_PER_MINUTE_NIO = 3.50

# Surge pricing sensitivity to rain and peak traffic:
# Multiplier = 1.0 + 0.032 * Pt + Rush_Hour_Boost + eps
SURGE_RAIN_FACTOR = 0.032
SURGE_MAX = 2.80

# PostgreSQL Database Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "integrador_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_SCHEMA = "raw_staging_movigo"

# Mock API settings for Shell Scripting (ingesta.sh)
MOCK_API_PORT = int(os.getenv("MOCK_MOVIGO_API_PORT", "8002"))
MOCK_API_HOST = "0.0.0.0"
