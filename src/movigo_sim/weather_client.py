"""Open-Meteo weather client and continuous hourly climate resolver for MoviGo."""

from datetime import date, datetime, timedelta
import json
import logging
import math
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error

logger = logging.getLogger("movigo_sim.weather_client")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "movigo"
HISTORIC_2024_PATH = DATA_DIR / "clima_managua_movigo_2024.json"
LIVE_CACHE_PATH = DATA_DIR / "clima_managua_live_cache.json"

MANAGUA_LAT = 12.1364
MANAGUA_LON = -86.2514


class MoviGoWeatherClient:
    """Provides hourly weather conditions for Managua with layered caching (2024 local cache + Open-Meteo live API)."""

    def __init__(self, historic_path: Path = HISTORIC_2024_PATH, live_cache_path: Path = LIVE_CACHE_PATH) -> None:
        self.historic_path = historic_path
        self.live_cache_path = live_cache_path
        self.hourly_index: dict[str, dict[str, Any]] = {}
        self._load_historic_cache()
        self._load_live_cache()

    def _load_historic_cache(self) -> None:
        """Load 2024 baseline hourly records from local JSON cache."""
        if not self.historic_path.exists():
            logger.warning("Historic 2024 weather cache not found at %s", self.historic_path)
            return

        try:
            with open(self.historic_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            precips = hourly.get("precipitation", [])
            rains = hourly.get("rain", [])
            winds = hourly.get("wind_speed_10m", [])

            for i, t_str in enumerate(times):
                key = t_str[:13]  # YYYY-MM-DDTHH
                self.hourly_index[key] = {
                    "temperature_c": float(temps[i]) if i < len(temps) and temps[i] is not None else 28.0,
                    "precipitation_mm": float(precips[i]) if i < len(precips) and precips[i] is not None else 0.0,
                    "rain_mm": float(rains[i]) if i < len(rains) and rains[i] is not None else 0.0,
                    "wind_speed_kmh": float(winds[i]) if i < len(winds) and winds[i] is not None else 12.0,
                }
            logger.info("Loaded %d historic 2024 hourly weather records into index.", len(self.hourly_index))
        except Exception as e:
            logger.error("Failed loading historic weather cache: %s", e)

    def _load_live_cache(self) -> None:
        """Load supplemental live cache for dates beyond 2024."""
        if not self.live_cache_path.exists():
            return
        try:
            with open(self.live_cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self.hourly_index[k] = v
            logger.info("Loaded %d supplemental live weather records from %s.", len(data), self.live_cache_path)
        except Exception as e:
            logger.warning("Failed loading live weather cache: %s", e)

    def _save_live_cache(self) -> None:
        """Persist live records back to cache file."""
        try:
            self.live_cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Only save keys not belonging to 2024
            live_records = {k: v for k, v in self.hourly_index.items() if not k.startswith("2024-")}
            with open(self.live_cache_path, "w", encoding="utf-8") as f:
                json.dump(live_records, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save live weather cache: %s", e)

    def _fetch_open_meteo_for_date_range(self, start_date: date, end_date: date) -> bool:
        """Fetch weather data from Open-Meteo for a given date range and populate index."""
        today = date.today()
        # Choose archive endpoint for historic past dates, forecast endpoint for recent/current dates
        if end_date < today:
            url = (
                f"https://archive-api.open-meteo.com/v1/archive?latitude={MANAGUA_LAT}&longitude={MANAGUA_LON}"
                f"&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
                "&hourly=temperature_2m,precipitation,rain,wind_speed_10m&timezone=America/Managua"
            )
        else:
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={MANAGUA_LAT}&longitude={MANAGUA_LON}"
                f"&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
                "&hourly=temperature_2m,precipitation,rain,wind_speed_10m&timezone=America/Managua"
            )

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MoviGoSimulation/2.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    hourly = data.get("hourly", {})
                    times = hourly.get("time", [])
                    temps = hourly.get("temperature_2m", [])
                    precips = hourly.get("precipitation", [])
                    rains = hourly.get("rain", [])
                    winds = hourly.get("wind_speed_10m", [])
                    for i, t_str in enumerate(times):
                        key = t_str[:13]
                        self.hourly_index[key] = {
                            "temperature_c": float(temps[i]) if i < len(temps) and temps[i] is not None else 28.0,
                            "precipitation_mm": float(precips[i]) if i < len(precips) and precips[i] is not None else 0.0,
                            "rain_mm": float(rains[i]) if i < len(rains) and rains[i] is not None else 0.0,
                            "wind_speed_kmh": float(winds[i]) if i < len(winds) and winds[i] is not None else 12.0,
                        }
                    self._save_live_cache()
                    logger.info("Successfully fetched %d hours from Open-Meteo (%s to %s)", len(times), start_date, end_date)
                    return True
        except Exception as e:
            logger.warning("Open-Meteo API fetch failed (%s): %s. Falling back to seasonal synthesis.", url, e)
        return False

    def _synthesize_seasonal_weather(self, dt: datetime) -> dict[str, Any]:
        """Generate deterministic, realistic Managua tropical seasonal weather if API is unavailable."""
        month = dt.month
        hour = dt.hour
        # Managua rainy season: May to October
        is_rainy_season = 5 <= month <= 10
        # Afternoon convective precipitation peak (14:00 - 18:00)
        is_afternoon_convective = 14 <= hour <= 18
        
        # Diurnal temperature cycle: min 23C at 5am, max 34C at 13pm
        hour_rad = 2.0 * math.pi * (hour - 5) / 24.0
        base_temp = 28.5 + 5.5 * math.sin(hour_rad)

        precip = 0.0
        # Deterministic pseudorandom factor based on day of year and hour
        day_seed = (dt.year * 365 + dt.timetuple().tm_yday * 24 + hour) % 100
        if is_rainy_season and is_afternoon_convective:
            if day_seed < 35:  # 35% chance of afternoon rain
                precip = round(2.0 + (day_seed % 15) * 1.8, 1)
        elif is_rainy_season and day_seed < 12:
            precip = round(0.5 + (day_seed % 5) * 0.8, 1)
        
        return {
            "temperature_c": round(base_temp, 1),
            "precipitation_mm": precip,
            "rain_mm": precip,
            "wind_speed_kmh": round(10.0 + (day_seed % 18) * 0.8, 1),
        }

    def get_hourly_weather(self, dt: datetime) -> dict[str, Any]:
        """Retrieve weather dictionary for a specific hour, fetching or synthesizing if not present."""
        key = dt.strftime("%Y-%m-%dT%H")
        if key not in self.hourly_index:
            # Attempt to fetch the whole month or 7-day window to minimize API roundtrips
            start_d = dt.date()
            end_d = min(date.today(), start_d + timedelta(days=6))
            fetched = self._fetch_open_meteo_for_date_range(start_d, end_d)
            if not fetched or key not in self.hourly_index:
                # Synthesize and store
                self.hourly_index[key] = self._synthesize_seasonal_weather(dt)
                self._save_live_cache()

        w = dict(self.hourly_index[key])
        precip = w.get("precipitation_mm", 0.0)
        h = dt.hour
        dow = dt.weekday()
        # Congestion calculation
        is_rush = (7 <= h <= 9) or (17 <= h <= 19)
        base_cong = 1.35 if is_rush and dow < 5 else (1.15 if 10 <= h <= 16 else 1.0)
        weather_factor = min(0.65, precip * 0.08)
        w["congestion_index"] = round(base_cong + weather_factor, 2)
        w["is_severe_rain"] = precip >= 3.0
        return w


# Global singleton client
weather_client = MoviGoWeatherClient()
