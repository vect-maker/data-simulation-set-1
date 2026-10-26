"""Hourly spatial weather, cauce runoff, and urban traffic congestion engine for MoviGo (Managua).

Models Managua's 92 fine-grained square quadrants (~0.88 km x 0.88 km) grouped inside the 12 urban zones:
- Localized convective storm cells (Southern Sierras, Eastern Corridor, Western Lakefront, City-Wide Squalls)
- Topographical runoff (escorrentia_cauce_mm) draining from high-altitude southern quadrants (Sierras / Santo Domingo / Las Colinas)
  into low-lying northern basins (Mercado Oriental, Ciudad Jardín, Bello Horizonte, Linda Vista)
- Street flooding flags (vias_anegadas) when runoff exceeds quadrant drainage capacity
"""

import json
import logging
import math
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np

from data_sim.core.weather import WeatherClient
from movigo_sim.config import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_LATITUDE,
    OPEN_METEO_LONGITUDE,
    TIMEZONE,
    START_DATE,
    END_DATE,
    RAW_DATA_DIR,
    DETERMINISTIC_SEEDS_DIR,
)
from movigo_sim.models import Cuadrante, ClimaCuadrantes

logger = logging.getLogger(__name__)

RISK_FLOOD_THRESHOLD_MM: dict[str, float] = {
    "bajo": 24.0,
    "medio": 14.5,
    "alto": 9.2,
    "critico": 6.5,
}


class VectorizedClimaRecords:
    """List-compatible sequence of ClimaCuadrantes backed by a vectorized DataFrame for instant CSV export."""

    def __init__(self, df: pd.DataFrame):
        self._df = df

    def to_dataframe(self) -> pd.DataFrame:
        return self._df

    def filter_dates(self, valid_dates: set[date]) -> "VectorizedClimaRecords":
        filtered = self._df[self._df["fecha"].isin(valid_dates)].reset_index(drop=True)
        return VectorizedClimaRecords(filtered)

    def __len__(self) -> int:
        return len(self._df)

    def __bool__(self) -> bool:
        return not self._df.empty

    def _row_to_model(self, row: Any) -> ClimaCuadrantes:
        return ClimaCuadrantes.model_construct(
            id_clima=int(row.id_clima),
            id_cuadrante=int(row.id_cuadrante),
            fecha_hora=row.fecha_hora if isinstance(row.fecha_hora, datetime) else datetime.fromisoformat(str(row.fecha_hora)),
            fecha=row.fecha,
            hora=int(row.hora),
            precipitacion_mm=float(row.precipitacion_mm),
            escorrentia_cauce_mm=float(row.escorrentia_cauce_mm),
            temperatura_c=float(row.temperatura_c),
            indice_congestion=float(row.indice_congestion),
            vias_anegadas=bool(row.vias_anegadas),
            condicion_cielo=str(row.condicion_cielo),
        )

    def __getitem__(self, item: int | slice) -> Any:
        if isinstance(item, slice):
            sub_df = self._df.iloc[item]
            return [self._row_to_model(r) for r in sub_df.itertuples(index=False)]
        row = self._df.iloc[item]
        return self._row_to_model(row)

    def __iter__(self):
        for r in self._df.itertuples(index=False):
            yield self._row_to_model(r)


def load_cuadrantes_catalog() -> list[Cuadrante]:
    """Load the 92 Managua fine-grained square quadrants from deterministic seed fixture."""
    path = DETERMINISTIC_SEEDS_DIR / "cuadrantes.json"
    with open(path, encoding="utf-8") as f:
        return [Cuadrante(**c) for c in json.load(f)]


def map_sky_condition(precip_mm: float, weather_code: int) -> str:
    """Map hourly meteorological readings to sky condition."""
    if precip_mm >= 6.0 or weather_code in [65, 81, 82, 95, 96, 99]:
        return "tormenta"
    elif precip_mm >= 0.3 or weather_code in [51, 53, 55, 61, 63, 80]:
        return "lluvia_ligera"
    elif weather_code in [1, 2, 3]:
        return "nublado"
    else:
        return "despejado"


def generate_synthetic_weather_fallback(start_date: str = START_DATE, end_date: str = END_DATE) -> dict[str, Any]:
    """Generate realistic daily + hourly tropical weather for Managua if network fails."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    num_days = (end - start).days + 1

    dates = [(start + timedelta(days=i)).isoformat() for i in range(num_days)]
    daily_precip = []
    daily_temps = []
    daily_codes = []

    hourly_times = []
    hourly_precip = []
    hourly_temps = []
    hourly_codes = []

    rng = np.random.default_rng(42)
    for d_str in dates:
        dt_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
        month = dt_obj.month
        if month in [1, 2, 3, 4, 12]:
            rain_prob = 0.08
            base_temp = float(rng.normal(30.5, 1.4))
        else:
            rain_prob = 0.58
            base_temp = float(rng.normal(28.0, 1.2))

        is_rainy_day = rng.random() < rain_prob
        day_p_total = float(rng.exponential(scale=12.0)) if is_rainy_day else 0.0

        hour_weights = np.zeros(24)
        if day_p_total > 0.1:
            burst_start = int(rng.choice([6, 13, 14, 15, 16, 17, 18, 19], p=[0.08, 0.10, 0.16, 0.20, 0.18, 0.14, 0.08, 0.06]))
            burst_len = int(rng.integers(2, 5))
            for h_idx in range(burst_start, min(24, burst_start + burst_len)):
                hour_weights[h_idx] = float(rng.uniform(0.4, 1.5))
            if hour_weights.sum() > 0:
                hour_weights /= hour_weights.sum()

        for h in range(24):
            hourly_times.append(f"{d_str}T{h:02d}:00")
            diurnal_swing = -3.2 * np.cos(2.0 * np.pi * (h - 14) / 24.0)
            h_temp = round(float(base_temp + diurnal_swing + rng.normal(0, 0.3)), 1)
            h_p = round(float(day_p_total * hour_weights[h]), 2)
            if h_p >= 6.0:
                h_code = 95
            elif h_p >= 0.3:
                h_code = 61
            else:
                h_code = 2 if is_rainy_day else 0
            hourly_precip.append(h_p)
            hourly_temps.append(h_temp)
            hourly_codes.append(h_code)

        daily_precip.append(round(day_p_total, 2))
        daily_temps.append(round(base_temp, 2))
        daily_codes.append(95 if day_p_total > 20.0 else (63 if day_p_total > 3.0 else 1))

    return {
        "latitude": OPEN_METEO_LATITUDE,
        "longitude": OPEN_METEO_LONGITUDE,
        "timezone": TIMEZONE,
        "daily": {
            "time": dates,
            "precipitation_sum": daily_precip,
            "temperature_2m_mean": daily_temps,
            "weather_code": daily_codes,
        },
        "hourly": {
            "time": hourly_times,
            "precipitation": hourly_precip,
            "temperature_2m": hourly_temps,
            "weather_code": hourly_codes,
        },
    }


def fetch_movigo_weather_archive(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    cache_path: Path | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch daily and hourly historical weather for Managua from Open-Meteo or local cache."""
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
        hourly_vars="precipitation,temperature_2m,weather_code",
        timezone=TIMEZONE,
        cache_path=cache_path,
        fallback_fn=lambda: generate_synthetic_weather_fallback(start_date, end_date),
        force_refresh=force_refresh,
    )


fetch_open_meteo_managua_series = fetch_movigo_weather_archive


def build_hourly_quadrant_climate(
    raw_json: dict[str, Any],
) -> tuple[VectorizedClimaRecords, dict[str, Any]]:
    """Build vectorized hourly per-quadrant climate, cauce runoff, and congestion across all 92 square quadrants."""
    rng = np.random.default_rng(42)
    cuadrantes = load_cuadrantes_catalog()
    n_quads = len(cuadrantes)

    if "hourly" in raw_json and "time" in raw_json["hourly"]:
        hourly = raw_json["hourly"]
        h_times = hourly["time"]
        h_precip = np.array([float(p) if p is not None else 0.0 for p in hourly["precipitation"]], dtype=float)
        h_temps = np.array([float(t) if t is not None else 28.0 for t in hourly["temperature_2m"]], dtype=float)
        h_codes = np.array([int(c) if c is not None else 0 for c in (hourly.get("weather_code") or hourly.get("weathercode", []))], dtype=int)
    else:
        fallback = generate_synthetic_weather_fallback()
        hourly = fallback["hourly"]
        h_times = hourly["time"]
        h_precip = np.array(hourly["precipitation"], dtype=float)
        h_temps = np.array(hourly["temperature_2m"], dtype=float)
        h_codes = np.array(hourly["weather_code"], dtype=int)

    num_hours = len(h_times)

    # Spatial coordinates, elevation, and drainage properties of each of the 92 square cuadrantes
    clats = np.array([0.5 * (c.lat_min + c.lat_max) for c in cuadrantes], dtype=float)
    clons = np.array([0.5 * (c.lon_min + c.lon_max) for c in cuadrantes], dtype=float)
    alts = np.array([float(c.altitud_media_msnm) for c in cuadrantes], dtype=float)
    flood_thresholds = np.array([RISK_FLOOD_THRESHOLD_MM[c.riesgo_inundacion] for c in cuadrantes], dtype=float)

    # Temperature lapse rate relative to central Managua (~105 msnm): cooler in Southern Sierras, warmer near Lake
    temp_offsets = np.round((105.0 - alts) * 0.011, 2)

    # 4 convective storm cell spatial profiles across the 92 squares:
    # 0: Southern Sierras downpour, 1: Eastern corridor storm, 2: Western/Lakefront storm, 3: City-wide squall
    south_norm = np.clip((12.164 - clats) / (12.164 - 12.086), 0.0, 1.0)
    east_norm = np.clip((clons - (-86.316)) / (-86.204 - (-86.316)), 0.0, 1.0)

    storm_profiles = np.vstack([
        0.25 + 1.25 * (south_norm ** 1.2),                       # Pattern 0: Southern Sierras convective storm
        0.25 + 1.20 * (east_norm ** 1.1),                        # Pattern 1: Eastern Corridor (Huembes / Bello Horizonte)
        0.25 + 1.20 * ((1.0 - east_norm) * (1.0 - 0.5 * south_norm)),  # Pattern 2: Western / Northern Lakefront
        1.02 + 0.12 * south_norm,                                # Pattern 3: City-wide Onda Tropical
    ])

    # Build upstream-to-downstream hydrological drainage transfer matrix W: shape (92, 92)
    # Southern higher-elevation squares drain northward into lower-elevation squares along the same longitude corridor
    drain_matrix = np.zeros((n_quads, n_quads), dtype=float)
    for q_down in range(n_quads):
        low_factor = max(0.0, (235.0 - alts[q_down]) / 185.0)
        if cuadrantes[q_down].riesgo_inundacion == "critico":
            low_factor *= 1.35
        elif cuadrantes[q_down].riesgo_inundacion == "alto":
            low_factor *= 1.15
        weights = np.zeros(n_quads, dtype=float)
        for q_up in range(n_quads):
            if clats[q_up] < clats[q_down] - 0.002 and abs(clons[q_up] - clons[q_down]) <= 0.024:
                weights[q_up] = math.exp(-abs(clons[q_up] - clons[q_down]) / 0.012)
        if weights.sum() > 0:
            drain_matrix[:, q_down] = (weights / weights.sum()) * (0.85 * low_factor)

    # Compute hourly rainfall matrix: shape (num_hours, 92)
    rain_q = np.zeros((num_hours, n_quads), dtype=np.float32)
    pattern_blocks = rng.choice(4, size=(num_hours // 4) + 1, p=[0.35, 0.25, 0.20, 0.20])
    rainy_indices = np.where(h_precip > 0.05)[0]
    for t_idx in rainy_indices:
        pat = pattern_blocks[t_idx // 4]
        jitter = rng.uniform(0.88, 1.14, size=n_quads)
        rain_q[t_idx] = np.round(np.maximum(0.0, h_precip[t_idx] * storm_profiles[pat] * jitter), 2)

    # Compute hydrological cauce runoff matrix: local rain + upstream lagged drainage from southern hills
    lagged_rain = 0.65 * rain_q + 0.35 * np.roll(rain_q, 1, axis=0)
    lagged_rain[0] = rain_q[0]
    upstream_contrib = lagged_rain @ drain_matrix
    local_retention = np.where(alts > 150.0, 0.85, 1.00).astype(np.float32)
    runoff_q = np.round(rain_q * local_retention + upstream_contrib, 2).astype(np.float32)

    # Flooded streets flag when runoff exceeds square drainage capacity
    flooded_q = runoff_q >= flood_thresholds[None, :]

    # Parse timestamps once across the 8,784 hours
    dt_objs = [datetime.strptime(ts, "%Y-%m-%dT%H:%M") for ts in h_times]
    dates_arr = np.array([dt.date() for dt in dt_objs], dtype=object)
    hours_arr = np.array([dt.hour for dt in dt_objs], dtype=np.int16)
    dows_arr = np.array([dt.weekday() for dt in dt_objs], dtype=np.int16)

    # Baseline hourly traffic congestion
    base_hour_cong = np.full(num_hours, 1.15, dtype=np.float32)
    is_weekday = dows_arr < 5
    rush_mask = np.isin(hours_arr, [7, 8, 17, 18])
    mid_mask = np.isin(hours_arr, [12, 13, 16, 19])
    night_mask = np.isin(hours_arr, [0, 1, 2, 3, 4])

    base_hour_cong[rush_mask & is_weekday] = 1.55
    base_hour_cong[rush_mask & ~is_weekday] = 1.25
    base_hour_cong[mid_mask & is_weekday] = 1.32
    base_hour_cong[mid_mask & ~is_weekday] = 1.20
    base_hour_cong[night_mask] = 1.02

    noise_cong = rng.normal(0.0, 0.04, size=(num_hours, n_quads)).astype(np.float32)
    cong_q = np.round(
        np.clip(
            base_hour_cong[:, None]
            + 0.08 * rain_q
            + 0.06 * runoff_q
            + np.where(flooded_q, 0.65, 0.0)
            + noise_cong,
            1.00,
            3.95,
        ),
        2,
    ).astype(np.float32)

    temp_q = np.round(h_temps[:, None] + temp_offsets[None, :], 1).astype(np.float32)

    # Vectorized sky condition classification
    eff_precip = np.maximum(rain_q, 0.6 * runoff_q)
    code_grid = np.broadcast_to(h_codes[:, None], (num_hours, n_quads))
    is_storm = (eff_precip >= 6.0) | ((rain_q > 0.1) & np.isin(code_grid, [65, 81, 82, 95, 96, 99]))
    is_light = (~is_storm) & ((eff_precip >= 0.3) | ((rain_q > 0.1) & np.isin(code_grid, [51, 53, 55, 61, 63, 80])))
    is_cloudy = (~is_storm) & (~is_light) & (code_grid > 0)

    sky_q = np.full((num_hours, n_quads), "despejado", dtype=object)
    sky_q[is_cloudy] = "nublado"
    sky_q[is_light] = "lluvia_ligera"
    sky_q[is_storm] = "tormenta"

    # Flatten (num_hours, n_quads) into the relational DataFrame (808,128 rows)
    total_rows = num_hours * n_quads
    quad_ids = np.array([c.id_cuadrante for c in cuadrantes], dtype=np.int32)
    formatted_fh = np.array([dt.strftime("%Y-%m-%d %H:%M:%S") for dt in dt_objs], dtype=object)

    df_clima = pd.DataFrame({
        "id_clima": np.arange(1, total_rows + 1, dtype=np.int32),
        "id_cuadrante": np.tile(quad_ids, num_hours),
        "fecha_hora": np.repeat(formatted_fh, n_quads),
        "fecha": np.repeat(dates_arr, n_quads),
        "hora": np.repeat(hours_arr, n_quads),
        "precipitacion_mm": rain_q.ravel(),
        "escorrentia_cauce_mm": runoff_q.ravel(),
        "temperatura_c": temp_q.ravel(),
        "indice_congestion": cong_q.ravel(),
        "vias_anegadas": flooded_q.ravel(),
        "condicion_cielo": sky_q.ravel(),
    })

    date_hour_to_idx = {(dates_arr[t], int(hours_arr[t])): t for t in range(num_hours)}
    hourly_matrices = {
        "date_hour_to_idx": date_hour_to_idx,
        "precip": rain_q,
        "runoff": runoff_q,
        "congestion": cong_q,
        "flooded": flooded_q,
    }

    return VectorizedClimaRecords(df_clima), hourly_matrices


def parse_movigo_weather_dataframe(raw_json: dict[str, Any]) -> pd.DataFrame:
    """Parse Open-Meteo daily summary DataFrame for daily demand driver while preserving OLS regression properties."""
    daily = raw_json["daily"]
    dates = [datetime.strptime(t, "%Y-%m-%d").date() for t in daily["time"]]
    precip = [float(p) if p is not None else 0.0 for p in daily["precipitation_sum"]]
    temps = [float(t) if t is not None else 28.0 for t in daily["temperature_2m_mean"]]
    codes = [int(c) if c is not None else 0 for c in (daily.get("weather_code") or daily.get("weathercode", []))]

    rng = np.random.default_rng(42)
    congestion_indices = []
    sky_conditions = []
    for d, p, c in zip(dates, precip, codes, strict=True):
        dow = d.weekday()
        base_cong = 1.20 + (0.35 if dow == 4 else (0.15 if dow in [0, 1, 2, 3] else -0.10))
        rain_bump = min(1.80, p * 0.075)
        cong = round(float(np.clip(base_cong + rain_bump + rng.normal(0, 0.08), 1.00, 3.50)), 2)
        congestion_indices.append(cong)
        sky_conditions.append("tormenta" if p >= 15.0 else ("lluvia_ligera" if p > 0.5 else ("nublado" if c in [1, 2, 3] else "despejado")))

    return pd.DataFrame({
        "fecha": dates,
        "precipitacion_mm": precip,
        "temperatura_c": temps,
        "indice_congestion": congestion_indices,
        "condicion_cielo": sky_conditions,
    })


def get_movigo_weather_series(force_refresh: bool = False) -> tuple[pd.DataFrame, VectorizedClimaRecords]:
    """Retrieve full 2024 daily driver DataFrame (with attached hourly quadrant matrices) and hourly ClimaCuadrantes records."""
    raw = fetch_movigo_weather_archive(force_refresh=force_refresh)
    df = parse_movigo_weather_dataframe(raw)
    hourly_records, hourly_matrices = build_hourly_quadrant_climate(raw)
    df.attrs["hourly_matrices"] = hourly_matrices
    return df, hourly_records
