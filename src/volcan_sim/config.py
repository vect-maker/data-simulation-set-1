"""Configuration constants and geographic coordinates for Cooperativa El Volcán simulation."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src" / "volcan_sim"
SEEDS_DIR = SRC_DIR / "seeds"
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw" / "volcan"
ARTIFACTS_DIR = BASE_DIR / "artifacts" / "volcan"
CSV_ARTIFACTS_DIR = ARTIFACTS_DIR / "csv"
SQL_ARTIFACTS_DIR = ARTIFACTS_DIR / "sql"

# Geographic anchors in Nicaragua
# Coffee highlands and export logistics
COORDINATES = {
    "jinotega": {"lat": 13.0924, "lon": -86.0021, "name": "Jinotega"},
    "matagalpa": {"lat": 12.9256, "lon": -85.9178, "name": "Matagalpa"},
    "dipilto": {"lat": 13.7170, "lon": -86.5120, "name": "Nueva Segovia (Dipilto)"},
    "madriz": {"lat": 13.4833, "lon": -86.3833, "name": "Madriz (San Juan del Río Coco)"},
    "sebaco_dry_mill": {"lat": 12.8530, "lon": -86.0960, "name": "Beneficio Seco Sébaco"},
    "puerto_corinto": {"lat": 12.4825, "lon": -87.1736, "name": "Puerto Corinto"},
}

# Time Horizon: Full Year 2024 (Leap year, 366 days)
SIMULATION_YEAR = 2024
START_DATE = "2024-01-01"
END_DATE = "2024-12-31"
TIMEZONE = "America/Managua"

# Weather API (Open-Meteo Jinotega Agro-weather)
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_LATITUDE = 13.0924
OPEN_METEO_LONGITUDE = -86.0021

# Agro-statistical Parameters
# SCAA Cupping formula: score = 76.2 + 0.0088 * Altitude + Variety_Bonus + eps
SCAA_BASE = 76.2
SCAA_ALTITUDE_COEFF = 0.0088
SCAA_NOISE_STD = 1.05

# Variety bonus points on cup quality
VARIETY_CUP_BONUS = {
    "VAR-001": 4.50, # Geisha (Ultra Specialty 88-92)
    "VAR-002": 3.80, # Pacamara (Exotic floral/sweet 86-90)
    "VAR-003": 2.20, # Bourbon (Sweet caramel/citrus 84-87)
    "VAR-004": 1.40, # Maragogipe (Grano elefante 83-86)
    "VAR-005": 0.80, # Caturra (Solid high altitude 82-85)
    "VAR-006": 0.50, # Catuaí Rojo (Classic balanced 81-84)
    "VAR-007": 0.60, # Catuaí Amarillo (Bright fruity 82-85)
}

# Milling conversion rates (Nicaragua coffee standards)
# 1 quintal de cafe oro (exportable green coffee = 100 lbs / 46 kg)
# requires ~ 230-260 kg of fresh cherry coffee (uva)
CHERRY_TO_ORO_RATIO = 0.185 # ~18.5% yield from fresh cherry to green export coffee
MOISTURE_TARGET_EXPORT = 11.5 # 11.5% optimal parchment moisture for export

# PostgreSQL Database Configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "antojitos_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "antojitos_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "antojitos_secure_password")
POSTGRES_SCHEMA = "raw_staging_volcan"

# Mock API settings for Shell Scripting (ingesta.sh)
MOCK_API_PORT = int(os.getenv("MOCK_VOLCAN_API_PORT", "8001"))
MOCK_API_HOST = "0.0.0.0"
