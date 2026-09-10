"""Agro-weather driver module for Cooperativa El Volcán (Jinotega, Nicaragua)."""

import json
import logging
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
import requests
import pandas as pd
import numpy as np

from volcan_sim.config import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_LATITUDE,
    OPEN_METEO_LONGITUDE,
    TIMEZONE,
    START_DATE,
    END_DATE,
    RAW_DATA_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST,
)
from volcan_sim.models import ClimaZonasCafetaleras

logger = logging.getLogger(__name__)


def map_coffee_weather_condition(precip_mm: float, weather_code: int) -> str:
    """Map meteorological readings to coffee agricultural weather conditions."""
    if precip_mm >= 25.0 or weather_code in [65, 81, 82, 95, 96, 99]:
        return "temporal"
    elif precip_mm > 1.0 or weather_code in [51, 53, 55, 61, 63, 80]:
        return "llovizna"
    elif weather_code in [1, 2, 3]:
        return "nublado"
    else:
        return "soleado"


def fetch_jinotega_weather_archive(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    cache_path: Path = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Fetch daily agro-weather for Jinotega highlands from Open-Meteo or local cache."""
    if cache_path is None:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = RAW_DATA_DIR / "clima_jinotega_2024.json"

    if cache_path.exists() and not force_refresh:
        logger.info(f"Loading Jinotega weather from cache: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    params = {
        "latitude": OPEN_METEO_LATITUDE,
        "longitude": OPEN_METEO_LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "precipitation_sum,temperature_2m_mean,temperature_2m_min,temperature_2m_max,weather_code",
        "timezone": TIMEZONE,
    }

    logger.info(f"Fetching Open-Meteo weather for Jinotega ({start_date} to {end_date})...")
    try:
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Jinotega weather cached successfully at {cache_path}")
        return data
    except Exception as e:
        logger.warning(f"Could not reach Open-Meteo API ({e}). Generating synthetic agro-weather fallback...")
        fallback = generate_synthetic_jinotega_weather(start_date, end_date)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(fallback, f, indent=2)
        return fallback


def generate_synthetic_jinotega_weather(start_date: str, end_date: str) -> Dict[str, Any]:
    """Generate realistic coffee agro-weather if network is unavailable."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    num_days = (end - start).days + 1

    dates = [(start + timedelta(days=i)).isoformat() for i in range(num_days)]
    precip = []
    temps_mean = []
    temps_min = []
    temps_max = []
    codes = []

    np.random.seed(101)
    for d_str in dates:
        month = datetime.strptime(d_str, "%Y-%m-%d").month
        # Highland climate: cool nights (14-17 C), mild days (22-26 C)
        # Wet season: May - November. Harvest dry window: Dec - March.
        if month in [12, 1, 2, 3]:
            p = float(np.random.exponential(scale=1.5)) if np.random.rand() < 0.20 else 0.0
            t_mean = float(np.random.normal(19.5, 1.2))
        else:
            p = float(np.random.exponential(scale=14.0)) if np.random.rand() < 0.65 else 0.0
            t_mean = float(np.random.normal(21.5, 1.0))

        t_min = t_mean - float(np.random.uniform(3.5, 6.0))
        t_max = t_mean + float(np.random.uniform(3.5, 6.5))
        code = 95 if p > 25.0 else (61 if p > 1.0 else 0)

        precip.append(round(p, 2))
        temps_mean.append(round(t_mean, 2))
        temps_min.append(round(t_min, 2))
        temps_max.append(round(t_max, 2))
        codes.append(code)

    return {
        "latitude": OPEN_METEO_LATITUDE,
        "longitude": OPEN_METEO_LONGITUDE,
        "timezone": TIMEZONE,
        "daily": {
            "time": dates,
            "precipitation_sum": precip,
            "temperature_2m_mean": temps_mean,
            "temperature_2m_min": temps_min,
            "temperature_2m_max": temps_max,
            "weather_code": codes,
        },
    }


def parse_jinotega_weather_dataframe(raw_json: Dict[str, Any]) -> pd.DataFrame:
    """Parse raw JSON into DataFrame matching clima_zonas_cafetaleras schema."""
    daily = raw_json["daily"]
    dates = pd.to_datetime(daily["time"]).date

    df = pd.DataFrame({
        "fecha": dates,
        "region": "Jinotega",
        "precipitacion_mm": [float(p) if p is not None else 0.0 for p in daily["precipitation_sum"]],
        "temperatura_media_c": [float(t) if t is not None else 20.5 for t in daily["temperature_2m_mean"]],
        "temperatura_min_c": [float(t) if t is not None else 15.0 for t in daily["temperature_2m_min"]],
        "temperatura_max_c": [float(t) if t is not None else 25.0 for t in daily["temperature_2m_max"]],
    })

    # Relative humidity approximation based on rain and temperature
    rh = []
    conditions = []
    for _, row in df.iterrows():
        p = row["precipitacion_mm"]
        t_mean = row["temperatura_media_c"]
        base_rh = 75.0 + min(20.0, p * 0.8) - (t_mean - 20.0) * 1.5
        rh.append(round(min(98.0, max(50.0, base_rh)), 2))
        conditions.append(map_coffee_weather_condition(p, 0))

    df["humedad_relativa_pct"] = rh
    df["condicion_clima"] = conditions
    return df


def get_coffee_weather_series() -> Tuple[pd.DataFrame, List[ClimaZonasCafetaleras]]:
    """Retrieve full 2024 coffee weather DataFrame and Pydantic records."""
    raw = fetch_jinotega_weather_archive()
    df = parse_jinotega_weather_dataframe(raw)
    records = [
        ClimaZonasCafetaleras(
            fecha=row["fecha"],
            region=row["region"],
            precipitacion_mm=row["precipitacion_mm"],
            temperatura_media_c=row["temperatura_media_c"],
            temperatura_min_c=row["temperatura_min_c"],
            temperatura_max_c=row["temperatura_max_c"],
            humedad_relativa_pct=row["humedad_relativa_pct"],
            condicion_clima=row["condicion_clima"],
        )
        for _, row in df.iterrows()
    ]
    return df, records


class MockVolcanWeatherHandler(BaseHTTPRequestHandler):
    """HTTP handler mimicking Open-Meteo Jinotega Agro-weather for student shell scripts."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/v1/archive", "/archive"]:
            raw_data = fetch_jinotega_weather_archive()
            body = json.dumps(raw_data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/health":
            body = b'{"status": "ok", "service": "cooperativa-el-volcan-mock-weather"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not Found. Use /v1/archive"}')

    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))


def start_volcan_mock_api_server(host: str = MOCK_API_HOST, port: int = MOCK_API_PORT):
    """Start standalone HTTP server serving Jinotega agro-weather endpoint."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, MockVolcanWeatherHandler)
    print(f"\n[Mock API - Volcán] Serving Jinotega Agro-weather on http://{host}:{port}/v1/archive")
    print(f"[Mock API - Volcán] Test command: curl -s 'http://{host}:{port}/v1/archive' | jq .\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Mock API - Volcán] Shutting down mock weather server.")
        httpd.server_close()
