"""Core Weather & Driver Ingestion Engine.

Provides reusable Open-Meteo client capabilities with automatic local caching,
resilient HTTP retries, fallback simulation, and a mock HTTP server for DataOps labs.
"""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Callable, Optional
from urllib.parse import urlparse
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


class MockWeatherHandler(BaseHTTPRequestHandler):
    """Generic HTTP handler mimicking Open-Meteo Archive API for student shell scripts."""

    data_provider: Optional[Callable[[], Dict[str, Any]]] = None
    service_name: str = "mock-open-meteo"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/v1/archive", "/archive"]:
            raw_data = self.data_provider() if self.data_provider else {}
            body = json.dumps(raw_data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/health":
            body = json.dumps({"status": "ok", "service": self.service_name}).encode("utf-8")
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


def start_mock_weather_server(
    data_provider: Callable[[], Dict[str, Any]],
    service_name: str = "mock-open-meteo",
    host: str = "127.0.0.1",
    port: int = 8000,
):
    """Run standalone HTTP mock server for Open-Meteo."""
    handler_class = type(
        "CustomMockWeatherHandler",
        (MockWeatherHandler,),
        {"data_provider": staticmethod(data_provider), "service_name": service_name},
    )

    server_address = (host, port)
    httpd = HTTPServer(server_address, handler_class)
    print(f"\n[Mock API] Serving Open-Meteo endpoint on http://{host}:{port}/v1/archive")
    print(f"[Mock API] Students can ingest with: curl -s 'http://{host}:{port}/v1/archive' | jq .\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Mock API] Shutting down mock weather server.")
        httpd.server_close()
