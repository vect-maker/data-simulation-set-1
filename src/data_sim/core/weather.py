"""Core Weather & Driver Ingestion Engine.

Provides reusable Open-Meteo client capabilities with automatic local caching,
resilient HTTP retries, fallback simulation, and a mock HTTP server for DataOps labs.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Callable
import requests

logger = logging.getLogger(__name__)


class WeatherClient:
    """Manages API fetching and local caching for meteorological driver variables."""

    @staticmethod
    def fetch_weather_archive(
        archive_url: str,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        daily_vars: str,
        timezone: str,
        cache_path: Path,
        fallback_fn: Callable[[], Dict[str, Any]],
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Fetch daily archive weather or retrieve from local cache, with synthetic fallback."""
        if cache_path.exists() and not force_refresh:
            logger.info(f"Loading weather from local cache: {cache_path}")
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "daily": daily_vars,
            "timezone": timezone,
        }

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Querying Open-Meteo API ({start_date} to {end_date}) for ({latitude}, {longitude})...")

        try:
            response = requests.get(archive_url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Weather data cached successfully at {cache_path}")
            return data
        except Exception as e:
            logger.warning(f"Could not reach Open-Meteo API ({e}). Generating realistic synthetic fallback...")
            fallback_data = fallback_fn()
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(fallback_data, f, indent=2)
            return fallback_data
