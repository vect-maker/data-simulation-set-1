"""Weather driver module: Open-Meteo API ingestion and Mock API server for Shell Scripting."""

import json
import logging
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs
import requests
import pandas as pd
import numpy as np

from antojitos_sim.config import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_LATITUDE,
    OPEN_METEO_LONGITUDE,
    TIMEZONE,
    START_DATE,
    END_DATE,
    RAW_DATA_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST
)
from antojitos_sim.models import ClimaDiario

logger = logging.getLogger(__name__)


def map_weather_condition(weather_code: int, precip_mm: float) -> str:
    """Map WMO weather interpretation code to business sky condition."""
    if precip_mm >= 15.0 or weather_code in [65, 81, 82, 95, 96, 99]:
        return "tormenta"
    elif precip_mm > 0.5 or weather_code in [51, 53, 55, 61, 63, 80]:
        return "lluvia_ligera"
    elif weather_code in [1, 2, 3]:
        return "nublado"
    else:
        return "despejado"


def fetch_open_meteo_archive(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    cache_path: Path = None,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """Fetch daily historical weather for Managua from Open-Meteo Archive API or local cache."""
    if cache_path is None:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = RAW_DATA_DIR / "clima_managua_2024.json"

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
        "timezone": TIMEZONE
    }

    logger.info(f"Querying Open-Meteo Archive for Managua ({start_date} to {end_date})...")
    try:
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Weather successfully fetched and cached at {cache_path}")
        return data
    except Exception as e:
        logger.warning(f"Could not reach Open-Meteo API ({e}). Generating realistic synthetic fallback...")
        fallback_data = generate_synthetic_weather_fallback(start_date, end_date)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(fallback_data, f, indent=2)
        return fallback_data


def generate_synthetic_weather_fallback(start_date: str, end_date: str) -> Dict[str, Any]:
    """Generate realistic tropical weather for Managua if network fails."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    num_days = (end - start).days + 1

    dates = [(start + timedelta(days=i)).isoformat() for i in range(num_days)]
    precip = []
    temps = []
    codes = []

    np.random.seed(42)
    for d_str in dates:
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        month = dt.month

        # Managua seasons: Dry (Dec-Apr), Wet/Rainy (May-Nov)
        if month in [1, 2, 3, 4, 12]:
            rain_prob = 0.08
            temp = float(np.random.normal(30.5, 1.8))
        else:
            rain_prob = 0.55
            temp = float(np.random.normal(28.0, 1.5))

        if np.random.rand() < rain_prob:
            p_val = float(np.random.exponential(scale=12.0))
            if p_val > 25.0:
                code = 95 # Tormenta eléctrica
            elif p_val > 5.0:
                code = 63 # Lluvia moderada
            else:
                code = 51 # Llovizna
        else:
            p_val = 0.0
            code = 0 if np.random.rand() > 0.4 else 2

        precip.append(round(p_val, 2))
        temps.append(round(temp, 2))
        codes.append(code)

    return {
        "latitude": OPEN_METEO_LATITUDE,
        "longitude": OPEN_METEO_LONGITUDE,
        "timezone": TIMEZONE,
        "daily": {
            "time": dates,
            "precipitation_sum": precip,
            "temperature_2m_mean": temps,
            "weather_code": codes
        }
    }


def parse_weather_dataframe(raw_json: Dict[str, Any]) -> pd.DataFrame:
    """Parse Open-Meteo response into a structured DataFrame matching clima_diario schema."""
    daily = raw_json["daily"]
    df = pd.DataFrame({
        "fecha": pd.to_datetime(daily["time"]).date,
        "precipitacion_mm": [float(p) if p is not None else 0.0 for p in daily["precipitation_sum"]],
        "temperatura_c": [float(t) if t is not None else 28.0 for t in daily["temperature_2m_mean"]],
        "weather_code": [int(c) if c is not None else 0 for c in daily["weather_code"]]
    })

    df["condicion_cielo"] = [
        map_weather_condition(code, p)
        for code, p in zip(df["weather_code"], df["precipitacion_mm"])
    ]

    return df[["fecha", "precipitacion_mm", "temperatura_c", "condicion_cielo"]]


def get_daily_weather_series() -> Tuple[pd.DataFrame, List[ClimaDiario]]:
    """Retrieve full 2024 weather DataFrame and Pydantic records."""
    raw = fetch_open_meteo_archive()
    df = parse_weather_dataframe(raw)
    records = [
        ClimaDiario(
            fecha=row["fecha"],
            precipitacion_mm=row["precipitacion_mm"],
            temperatura_c=row["temperatura_c"],
            condicion_cielo=row["condicion_cielo"]
        )
        for _, row in df.iterrows()
    ]
    return df, records


class MockOpenMeteoHandler(BaseHTTPRequestHandler):
    """HTTP handler mimicking Open-Meteo Archive API for student shell scripts."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/v1/archive", "/archive"]:
            raw_data = fetch_open_meteo_archive()
            body = json.dumps(raw_data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/health":
            body = b'{"status": "ok", "service": "antojitos-mock-open-meteo"}'
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


def start_mock_api_server(host: str = MOCK_API_HOST, port: int = MOCK_API_PORT):
    """Start standalone HTTP server serving Open-Meteo weather endpoint."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, MockOpenMeteoHandler)
    print(f"\n[Mock API] Serving Open-Meteo weather for Managua on http://{host}:{port}/v1/archive")
    print(f"[Mock API] Students can ingest with: curl -s 'http://{host}:{port}/v1/archive' | jq .\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Mock API] Shutting down mock weather server.")
        httpd.server_close()
