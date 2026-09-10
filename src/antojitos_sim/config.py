"""Configuration constants and paths for Antojitos Express simulation."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src" / "antojitos_sim"
SEEDS_DIR = SRC_DIR / "seeds"
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw" / "antojitos"
ARTIFACTS_DIR = BASE_DIR / "artifacts" / "antojitos"
CSV_ARTIFACTS_DIR = ARTIFACTS_DIR / "csv"
SQL_ARTIFACTS_DIR = ARTIFACTS_DIR / "sql"

# Geographic anchors: Managua, Nicaragua
# Ghost Kitchen centered in Los Robles / Altamira
KITCHEN_LATITUDE = 12.1285
KITCHEN_LONGITUDE = -86.2550
CITY_NAME = "Managua, Nicaragua"

# Time Horizon: Full Year 2024 (Leap year, 366 days)
SIMULATION_YEAR = 2024
START_DATE = "2024-01-01"
END_DATE = "2024-12-31"
TIMEZONE = "America/Managua"

# Weather API (Open-Meteo Historical Archive)
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_LATITUDE = 12.1364
OPEN_METEO_LONGITUDE = -86.2514

# Mathematical & Statistical Parameters
# Baseline daily order parameters: lambda_t = 110 + 7.8 * P_t - 0.08 * P_t^2 + weekend_adj + eps
DEMAND_BETA_0 = 110.0
DEMAND_BETA_1 = 7.8
DEMAND_BETA_2 = -0.08
DEMAND_NOISE_STD = 8.0

# Day of week adjustments (0=Monday, ..., 6=Sunday)
DAY_OF_WEEK_BOOST = {
    0: -10.0, # Lunes más lento
    1: -5.0,  # Martes
    2: 0.0,   # Miércoles
    3: 5.0,   # Jueves
    4: 25.0,  # Viernes de fritanga
    5: 35.0,  # Sábado pico
    6: 30.0   # Domingo familiar (sopas y nacatamales)
}

# Delivery Transit Time Formula parameters:
# T_entrega = T_prep + T_base_zona + RAIN_DELAY_FACTOR * P_t + lognormal(0, LOGNORMAL_SIGMA)
RAIN_DELAY_FACTOR = 0.65
LOGNORMAL_SIGMA = 0.20

# Basket size geometric distribution: K ~ Geometric(p=0.45)
BASKET_SIZE_P = 0.45
MAX_BASKET_SIZE = 6

# Payment methods distribution
PAYMENT_METHOD_WEIGHTS = {
    "efectivo": 0.45,
    "tarjeta": 0.35,
    "billetera_digital": 0.20
}

# PostgreSQL Database Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "integrador_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA", "raw_staging")

# Gemini LLM settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# Mock API settings
MOCK_API_HOST = os.getenv("MOCK_API_HOST", "0.0.0.0")
MOCK_API_PORT = int(os.getenv("MOCK_API_PORT", "8000"))
