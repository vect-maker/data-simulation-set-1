"""Weather and urban traffic congestion driver module for MoviGo (Managua)."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np

from data_sim.core.weather import WeatherClient, start_mock_weather_server
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


def generate_synthetic_weather_fallback(start_date: str = START_DATE, end_date: str = END_DATE) -> Dict[str, Any]:
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
        month = datetime.strptime(d_str, "%Y-%m-%d").month
        if month in [1, 2, 3, 4, 12]:
            rain_prob = 0.08
            temp = float(np.random.normal(30.5, 1.8))
        else:
            rain_prob = 0.55
            temp = float(np.random.normal(28.0, 1.5))

        if np.random.rand() < rain_prob:
            p_val = float(np.random.exponential(scale=12.0))
            code = 95 if p_val > 25.0 else (63 if p_val > 5.0 else 51)
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
            "weather_code": codes,
        },
    }


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

    return WeatherClient.fetch_weather_archive(
        archive_url=OPEN_METEO_ARCHIVE_URL,
        latitude=OPEN_METEO_LATITUDE,
        longitude=OPEN_METEO_LONGITUDE,
        start_date=start_date,
        end_date=end_date,
        daily_vars="precipitation_sum,temperature_2m_mean,weather_code",
        timezone=TIMEZONE,
        cache_path=cache_path,
        fallback_fn=lambda: generate_synthetic_weather_fallback(start_date, end_date),
        force_refresh=force_refresh,
    )


fetch_open_meteo_managua_series = fetch_movigo_weather_archive


def parse_movigo_weather_dataframe(raw_json: Dict[str, Any]) -> pd.DataFrame:
    """Parse Open-Meteo payload and generate simulated congestion index based on rain."""
    daily = raw_json["daily"]
    dates = [datetime.strptime(t, "%Y-%m-%d").date() for t in daily["time"]]
    precip = [float(p) if p is not None else 0.0 for p in daily["precipitation_sum"]]
    temps = [float(t) if t is not None else 28.0 for t in daily["temperature_2m_mean"]]
    codes = [int(c) if c is not None else 0 for c in (daily.get("weather_code") or daily.get("weathercode", []))]

    congestion_indices = []
    sky_conditions = []
    for d, p, c in zip(dates, precip, codes):
        dow = d.weekday()
        base_cong = 1.20 + (0.35 if dow == 4 else (0.15 if dow in [0, 1, 2, 3] else -0.10))
        rain_bump = min(1.80, p * 0.075)
        cong = round(float(np.clip(base_cong + rain_bump + np.random.normal(0, 0.08), 1.00, 3.50)), 2)
        congestion_indices.append(cong)
        sky_conditions.append(map_sky_condition(p, c))

    return pd.DataFrame({
        "fecha": dates,
        "precipitacion_mm": precip,
        "temperatura_c": temps,
        "indice_congestion": congestion_indices,
        "condicion_cielo": sky_conditions,
    })


def get_movigo_weather_series(force_refresh: bool = False) -> Tuple[pd.DataFrame, List[ClimaCuadrantes]]:
    """Retrieve full 2024 weather DataFrame and Pydantic records."""
    raw = fetch_movigo_weather_archive(force_refresh=force_refresh)
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


def start_movigo_mock_api_server(host: str = MOCK_API_HOST, port: int = MOCK_API_PORT):
    """Start standalone HTTP server serving Managua urban weather & traffic endpoint."""
    start_mock_weather_server(
        data_provider=fetch_movigo_weather_archive,
        service_name="movigo-mock-weather",
        host=host,
        port=port,
    )


start_mock_api_server = start_movigo_mock_api_server
