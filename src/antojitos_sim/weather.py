"""Weather driver module for Antojitos Express (Managua)."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np

from data_sim.core.weather import WeatherClient
from antojitos_sim.config import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_LATITUDE,
    OPEN_METEO_LONGITUDE,
    TIMEZONE,
    START_DATE,
    END_DATE,
    RAW_DATA_DIR,
)
from antojitos_sim.models import ClimaDiario

logger = logging.getLogger(__name__)


def map_weather_condition(weather_code: int, precip_mm: float) -> str:
    """Map WMO weather code to business condition."""
    if precip_mm >= 15.0 or weather_code in [65, 81, 82, 95, 96, 99]:
        return "tormenta"
    elif precip_mm > 0.5 or weather_code in [51, 53, 55, 61, 63, 80]:
        return "lluvia_ligera"
    elif weather_code in [1, 2, 3]:
        return "nublado"
    else:
        return "despejado"


def generate_synthetic_weather_fallback(start_date: str = START_DATE, end_date: str = END_DATE) -> dict[str, Any]:
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
                code = 95
            elif p_val > 5.0:
                code = 63
            else:
                code = 51
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


def fetch_open_meteo_archive(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    cache_path: Path | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch daily historical weather for Managua from Open-Meteo Archive API or cache."""
    if cache_path is None:
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = RAW_DATA_DIR / "clima_managua_2024.json"

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


def parse_weather_dataframe(raw_json: dict[str, Any]) -> pd.DataFrame:
    """Parse Open-Meteo response into structured DataFrame matching clima_diario schema."""
    daily = raw_json["daily"]
    df = pd.DataFrame({
        "fecha": pd.to_datetime(daily["time"]).date,
        "precipitacion_mm": [float(p) if p is not None else 0.0 for p in daily["precipitation_sum"]],
        "temperatura_c": [float(t) if t is not None else 28.0 for t in daily["temperature_2m_mean"]],
        "weather_code": [int(c) if c is not None else 0 for c in (daily.get("weather_code") or daily.get("weathercode", []))],
    })

    df["condicion_cielo"] = [
        map_weather_condition(code, p)
        for code, p in zip(df["weather_code"], df["precipitacion_mm"], strict=True)
    ]

    return df[["fecha", "precipitacion_mm", "temperatura_c", "condicion_cielo"]]


def get_daily_weather_series(force_refresh: bool = False) -> tuple[pd.DataFrame, list[ClimaDiario]]:
    """Retrieve full 2024 weather DataFrame and Pydantic records."""
    raw = fetch_open_meteo_archive(force_refresh=force_refresh)
    df = parse_weather_dataframe(raw)
    records = [
        ClimaDiario(
            fecha=row["fecha"],
            precipitacion_mm=row["precipitacion_mm"],
            temperatura_c=row["temperatura_c"],
            condicion_cielo=row["condicion_cielo"],
        )
        for _, row in df.iterrows()
    ]
    return df, records

