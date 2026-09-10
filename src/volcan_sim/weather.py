"""Agro-weather driver module for Cooperativa El Volcán (Jinotega, Nicaragua)."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np

from data_sim.core.weather import WeatherClient
from volcan_sim.config import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_LATITUDE,
    OPEN_METEO_LONGITUDE,
    TIMEZONE,
    START_DATE,
    END_DATE,
    RAW_DATA_DIR,
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


def generate_synthetic_jinotega_weather(start_date: str = START_DATE, end_date: str = END_DATE) -> dict[str, Any]:
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
        if month in [1, 2, 3, 4]:
            p_val = float(np.random.exponential(scale=2.0)) if np.random.rand() < 0.20 else 0.0
            t_mean = float(np.random.normal(20.5, 1.2))
        elif month in [5, 6, 7, 8, 9, 10]:
            p_val = float(np.random.exponential(scale=18.0)) if np.random.rand() < 0.65 else 0.0
            t_mean = float(np.random.normal(19.2, 1.0))
        else:
            p_val = float(np.random.exponential(scale=12.0)) if np.random.rand() < 0.45 else 0.0
            t_mean = float(np.random.normal(18.0, 1.1))

        t_min = t_mean - float(np.random.uniform(3.5, 5.5))
        t_max = t_mean + float(np.random.uniform(4.0, 6.5))

        if p_val > 25.0:
            code = 95
        elif p_val > 1.0:
            code = 61
        else:
            code = 0 if np.random.rand() > 0.5 else 2

        precip.append(round(p_val, 2))
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


def fetch_jinotega_weather_archive(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    cache_path: Path | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch daily agro-weather for Jinotega highlands from Open-Meteo or local cache."""
    if cache_path is None:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = RAW_DATA_DIR / "clima_jinotega_2024.json"

    return WeatherClient.fetch_weather_archive(
        archive_url=OPEN_METEO_ARCHIVE_URL,
        latitude=OPEN_METEO_LATITUDE,
        longitude=OPEN_METEO_LONGITUDE,
        start_date=start_date,
        end_date=end_date,
        daily_vars="precipitation_sum,temperature_2m_mean,temperature_2m_min,temperature_2m_max,weather_code",
        timezone=TIMEZONE,
        cache_path=cache_path,
        fallback_fn=lambda: generate_synthetic_jinotega_weather(start_date, end_date),
        force_refresh=force_refresh,
    )


def parse_jinotega_weather_dataframe(raw_json: dict[str, Any]) -> pd.DataFrame:
    """Transform Open-Meteo payload into ClimaZonasCafetaleras DataFrame."""
    daily = raw_json["daily"]
    df = pd.DataFrame({
        "fecha": pd.to_datetime(daily["time"]).date,
        "precipitacion_mm": [float(p) if p is not None else 0.0 for p in daily["precipitation_sum"]],
        "temperatura_media_c": [float(t) if t is not None else 19.5 for t in daily["temperature_2m_mean"]],
        "temperatura_min_c": [float(t) if t is not None else 15.0 for t in daily.get("temperature_2m_min", daily["temperature_2m_mean"])],
        "temperatura_max_c": [float(t) if t is not None else 25.0 for t in daily.get("temperature_2m_max", daily["temperature_2m_mean"])],
        "weather_code": [int(c) if c is not None else 0 for c in (daily.get("weather_code") or daily.get("weathercode", []))],
    })

    df["condicion_clima"] = [
        map_coffee_weather_condition(p, code)
        for p, code in zip(df["precipitacion_mm"], df["weather_code"], strict=True)
    ]
    df["region"] = "Jinotega"
    df["humedad_relativa_pct"] = [
        round(min(98.0, 72.0 + p * 1.2), 1)
        for p in df["precipitacion_mm"]
    ]

    return df[[
        "fecha", "region", "precipitacion_mm", "temperatura_media_c",
        "temperatura_min_c", "temperatura_max_c", "humedad_relativa_pct", "condicion_clima"
    ]]


def get_jinotega_weather_series(force_refresh: bool = False) -> tuple[pd.DataFrame, list[ClimaZonasCafetaleras]]:
    """Retrieve structured DataFrame and Pydantic records for 2024."""
    raw = fetch_jinotega_weather_archive(force_refresh=force_refresh)
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


# Alias for backward compatibility
get_coffee_weather_series = get_jinotega_weather_series

