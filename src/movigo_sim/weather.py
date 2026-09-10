"""Weather and urban traffic congestion driver module for MoviGo (Managua)."""

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

from movigo_sim.config import (
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
from movigo_sim.models import ClimaCuadrantes

logger = logging.getLogger(__name__)


def map_sky_condition(precip_mm: float, weather_code: int) -> str:
    """Map meteorological readings to sky condition."""
    if precip_mm >= 15.0 or weather_code in [65, 81, 82, 95, 96, 99]:
        return "tormenta"
    elif precip_mm > 0.5 or weather_code in [51, 53, 55, 61, 63, 80]:
        return "lluvia_ligera"
    elif weather_code in [1, 2, 3]:
        return "nublado"
    else:
        return "despejado"


def fetch_movigo_weather_archive(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    cache_path: Path = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Fetch daily historical weather for Managua from Open-Meteo or local cache."""
    if cache_path is None:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = RAW_DATA_DIR / "clima_managua_movigo_2024.json"

    if cache_path.exists() and not force_refresh:
        logger.info(f"Loading weather from cache: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    params = {
        "latitude": OPEN_METEO_LATITUDE,
        "longitude": OPEN_METEO_LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "precipitation_sum,temperature_2m_mean,weather_code",
        "timezone": TIMEZONE,
    }

    logger.info(f"Fetching Open-Meteo weather for MoviGo Managua ({start_date} to {end_date})...")
    try:
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Weather successfully cached at {cache_path}")
        return data
    except Exception as e:
        logger.warning(f"Could not reach Open-Meteo API ({e}). Generating fallback...")
        fallback = generate_synthetic_weather_fallback(start_date, end_date)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(fallback, f, indent=2)
        return fallback


def generate_synthetic_weather_fallback(start_date: str, end_date: str) -> Dict[str, Any]:
    """Synthetic weather generator if network is unreachable."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    num_days = (end - start).days + 1
    dates = [(start + timedelta(days=i)).isoformat() for i in range(num_days)]
    precip = []
    temps = []
    codes = []
    np.random.seed(42)
    for d_str in dates:
        month = datetime.strptime(d_str, "%Y-%m-%d").month
        if month in [1, 2, 3, 4, 12]:
            p = float(np.random.exponential(scale=1.0)) if np.random.rand() < 0.10 else 0.0
            t = float(np.random.normal(30.0, 1.5))
        else:
            p = float(np.random.exponential(scale=12.0)) if np.random.rand() < 0.55 else 0.0
            t = float(np.random.normal(28.0, 1.2))
        precip.append(round(p, 2))
        temps.append(round(t, 2))
        codes.append(95 if p > 20.0 else (61 if p > 1.0 else 0))

    return {
        "latitude": OPEN_METEO_LATITUDE,
        "longitude": OPEN_METEO_LONGITUDE,
        "timezone": TIMEZONE,
        "daily": {
            "time": dates,
            "precipitation_sum": precip,
            "temperature_2m_mean": temps,
            "weather_code": codes,
        },
    }


def parse_movigo_weather_dataframe(raw_json: Dict[str, Any]) -> pd.DataFrame:
    """Parse weather and derive daily traffic congestion index."""
    daily = raw_json["daily"]
    dates = pd.to_datetime(daily["time"]).date

    precip = [float(p) if p is not None else 0.0 for p in daily["precipitation_sum"]]
    temps = [float(t) if t is not None else 28.5 for t in daily["temperature_2m_mean"]]
    codes = [int(c) if c is not None else 0 for c in daily["weather_code"]]

    # Traffic congestion index: 1.00 (fluid) to 3.50 (severe downpour chaos)
    # Managua traffic collapses when rainwater floods major avenues / rotaries
    congestion_indices = []
    sky_conditions = []
    for d, p, c in zip(dates, precip, codes):
        dow = d.weekday() # Friday is naturally heavier
        base_cong = 1.20 + (0.35 if dow == 4 else (0.15 if dow in [0, 1, 2, 3] else -0.10))
        # Rain multiplier: heavy downpour adds up to +1.8 to congestion index
        rain_bump = min(1.80, p * 0.075)
        cong = round(float(np.clip(base_cong + rain_bump + np.random.normal(0, 0.08), 1.00, 3.50)), 2)
        congestion_indices.append(cong)
        sky_conditions.append(map_sky_condition(p, c))

    df = pd.DataFrame({
        "fecha": dates,
        "precipitacion_mm": precip,
        "temperatura_c": temps,
        "indice_congestion": congestion_indices,
        "condicion_cielo": sky_conditions,
    })
    return df


def get_movigo_weather_series() -> Tuple[pd.DataFrame, List[ClimaCuadrantes]]:
    """Retrieve full 2024 weather DataFrame and Pydantic records."""
    raw = fetch_movigo_weather_archive()
    df = parse_movigo_weather_dataframe(raw)
    records = [
        ClimaCuadrantes(
            fecha=row["fecha"],
            precipitacion_mm=row["precipitacion_mm"],
            temperatura_c=row["temperatura_c"],
            indice_congestion=row["indice_congestion"],
            condicion_cielo=row["condicion_cielo"],
        )
        for _, row in df.iterrows()
    ]
    return df, records


class MockMoviGoWeatherHandler(BaseHTTPRequestHandler):
    """HTTP handler mimicking Open-Meteo for student shell scripts."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/v1/archive", "/archive"]:
            raw_data = fetch_movigo_weather_archive()
            body = json.dumps(raw_data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/health":
            body = b'{"status": "ok", "service": "movigo-mock-weather"}'
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


def start_movigo_mock_api_server(host: str = MOCK_API_HOST, port: int = MOCK_API_PORT):
    """Start standalone HTTP server serving Managua urban weather & traffic endpoint."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, MockMoviGoWeatherHandler)
    print(f"\n[Mock API - MoviGo] Serving Urban Weather & Traffic on http://{host}:{port}/v1/archive")
    print(f"[Mock API - MoviGo] Test command: curl -s 'http://{host}:{port}/v1/archive' | jq .\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Mock API - MoviGo] Shutting down mock weather server.")
        httpd.server_close()
