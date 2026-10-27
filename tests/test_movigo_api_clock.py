"""Unit and integration tests for MoviGo continuous simulation clock, hourly slicing, and time-bound queries."""

from datetime import datetime, date, timedelta
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.movigo_clock import movigo_clock
from movigo_sim.generator import MoviGoSimulationEngine
from movigo_sim.weather_client import weather_client


class TestMoviGoAPIClock(unittest.TestCase):
    """Test suite for MoviGo simulation clock status, time bounds validation, and hourly slice simulation."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Seed clock boundaries for deterministic testing
        movigo_clock.earliest_datetime = datetime(2024, 1, 1, 0, 0, 0)
        movigo_clock.latest_datetime = datetime(2024, 1, 3, 23, 59, 59)
        movigo_clock.current_status = "ready"

    def tearDown(self):
        # Reset clock state after each test
        with movigo_clock._lock:
            movigo_clock.earliest_datetime = datetime(2024, 1, 1, 0, 0, 0)
            movigo_clock.latest_datetime = datetime(2024, 1, 3, 23, 59, 59)
            movigo_clock.current_status = "ready"

    def test_simulation_status_endpoint(self):
        """GET /movigo/simulation/status returns 200 with complete clock and progress metadata."""
        response = self.client.get("/movigo/simulation/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("case_name", data)
        self.assertIn("current_status", data)
        self.assertIn("earliest_datetime", data)
        self.assertIn("latest_datetime", data)
        self.assertIn("target_datetime", data)
        self.assertIn("hours_remaining_catch_up", data)
        self.assertIn("total_hours_simulated", data)
        self.assertIn("total_trips_simulated", data)
        self.assertEqual(data["current_status"], "ready")

    def test_trips_within_valid_bounds(self):
        """GET /movigo/trips with start_time and end_time within bounds validates correctly."""
        with patch("src.api.routers.movigo.execute_paginated_query") as mock_query:
            mock_query.return_value = {
                "items": [],
                "count": 0,
                "total": 0,
                "offset": 0,
                "limit": 10,
            }
            response = self.client.get(
                "/movigo/trips",
                params={
                    "start_time": "2024-01-01T08:00:00",
                    "end_time": "2024-01-01T12:00:00",
                    "limit": 10,
                },
            )
            self.assertEqual(response.status_code, 200)
            mock_query.assert_called_once()
            _, kwargs = mock_query.call_args
            filters = kwargs.get("filters", [])
            filter_cols = [f[0] for f in filters]
            self.assertIn("requested_at", filter_cols)

    def test_trips_future_end_time_returns_400(self):
        """GET /movigo/trips requesting ungenerated future time returns HTTP 400 Bad Request."""
        response = self.client.get(
            "/movigo/trips",
            params={"end_time": "2029-01-01T00:00:00"},
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("supera la última hora generada", data["detail"])

    def test_trips_past_start_time_returns_400(self):
        """GET /movigo/trips requesting time prior to earliest boundary returns HTTP 400 Bad Request."""
        response = self.client.get(
            "/movigo/trips",
            params={"start_time": "2020-01-01T00:00:00"},
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("anterior al límite inicial", data["detail"])

    def test_trips_inverted_time_range_returns_400(self):
        """GET /movigo/trips where end_time < start_time returns HTTP 400 Bad Request."""
        response = self.client.get(
            "/movigo/trips",
            params={
                "start_time": "2024-01-02T15:00:00",
                "end_time": "2024-01-02T10:00:00",
            },
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("no puede ser anterior", data["detail"])

    def test_weather_future_time_returns_400(self):
        """GET /movigo/weather with future end_time returns HTTP 400."""
        response = self.client.get(
            "/movigo/weather",
            params={"end_time": "2030-01-01T00:00:00"},
        )
        self.assertEqual(response.status_code, 400)

    def test_telemetry_future_time_returns_400(self):
        """GET /movigo/telemetry with future end_time returns HTTP 400."""
        response = self.client.get(
            "/movigo/telemetry",
            params={"end_time": "2030-01-01T00:00:00"},
        )
        self.assertEqual(response.status_code, 400)

    def test_maintenance_future_date_returns_400(self):
        """GET /movigo/maintenance with future end_date returns HTTP 400."""
        response = self.client.get(
            "/movigo/maintenance",
            params={"end_date": "2030-01-01"},
        )
        self.assertEqual(response.status_code, 400)

    def test_simulate_hourly_slice_execution(self):
        """Verify simulate_hourly_slice runs an atomic 1-hour slice generating all 7 entity collections."""
        engine = MoviGoSimulationEngine(random_seed=42)
        target_dt = datetime(2024, 1, 1, 15, 0, 0)
        w = weather_client.get_hourly_weather(target_dt)
        trips, payments, ratings, cancellations, telemetry, maintenance, weather_records = (
            engine.simulate_hourly_slice(target_dt, w)
        )
        self.assertGreaterEqual(len(trips), 1)
        self.assertEqual(len(payments), len(trips))
        self.assertGreaterEqual(len(ratings), 1)
        self.assertEqual(len(weather_records), len(engine.quadrants))  # All quadrants recorded for the hour
        self.assertGreaterEqual(len(telemetry), 1)
        for t in trips:
            self.assertEqual(t.requested_at.hour, 15)
            self.assertEqual(t.requested_at.date(), date(2024, 1, 1))

    def test_simulate_daily_slice_execution(self):
        """Verify simulate_daily_slice runs a complete 24-hour day slice generating all entities."""
        engine = MoviGoSimulationEngine(random_seed=42)
        target_date = date(2024, 1, 1)
        daily_weather = weather_client.get_daily_weather(target_date)
        self.assertEqual(len(daily_weather), 24)

        trips, payments, ratings, cancellations, telemetry, maintenance, weather_records = (
            engine.simulate_daily_slice(target_date, daily_weather)
        )
        self.assertGreaterEqual(len(trips), 20)
        self.assertEqual(len(payments), len(trips))
        self.assertGreaterEqual(len(ratings), 10)
        # All quadrants across all 24 hours of that day
        self.assertEqual(len(weather_records), len(engine.quadrants) * 24)
        for t in trips:
            self.assertEqual(t.requested_at.date(), target_date)

    def test_climate_prefetch_large_batching(self):
        """Verify prefetch_climate_range batches date ranges into large chunks without spamming API."""
        from movigo_sim.weather_client import MoviGoWeatherClient
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock

        with tempfile.TemporaryDirectory() as tmp_dir:
            client = MoviGoWeatherClient(
                historic_path=Path(tmp_dir) / "empty_hist.json",
                live_cache_path=Path(tmp_dir) / "test_live_cache.json",
            )
            client._fetch_open_meteo_for_date_range = MagicMock(return_value=True)

            # Request 360 days: should split into 2 chunks of 180 days, NOT 50+ 7-day calls
            start_d = date(2025, 1, 1)
            end_d = date(2025, 12, 26)
            client.prefetch_climate_range(start_d, end_d, chunk_days=180)

            # Verified call count is 2 (2 large chunks of 180 days)
            self.assertEqual(client._fetch_open_meteo_for_date_range.call_count, 2)
            first_call_args = client._fetch_open_meteo_for_date_range.call_args_list[0][0]
            self.assertEqual(first_call_args[0], start_d)
            self.assertEqual(first_call_args[1], start_d + timedelta(days=179))

    def test_get_daily_weather_returns_24_hours(self):
        """Verify get_daily_weather provides exactly 24 chronological hours for target date."""
        target_d = date(2024, 1, 15)
        w_list = weather_client.get_daily_weather(target_d)
        self.assertEqual(len(w_list), 24)
        for h, w in enumerate(w_list):
            self.assertIn("temperature_c", w)
            self.assertIn("precipitation_mm", w)
            self.assertIn("congestion_index", w)

    def test_api_serves_requests_while_catching_up(self):
        """Verify API serves endpoints immediately with HTTP 200 while status is catching_up."""
        with movigo_clock._lock:
            movigo_clock.current_status = "catching_up"
            movigo_clock.latest_datetime = datetime(2024, 1, 1, 12, 0, 0)

        # /movigo/simulation/status responds immediately with catching_up
        response = self.client.get("/movigo/simulation/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["current_status"], "catching_up")
        self.assertGreater(data["hours_remaining_catch_up"], 0)

        # Static collection endpoints respond without delay
        with patch("src.api.routers.movigo.execute_paginated_query") as mock_query:
            mock_query.return_value = {"items": [], "count": 0, "total": 0, "offset": 0, "limit": 10}
            resp_quads = self.client.get("/movigo/quadrants?limit=10")
            self.assertEqual(resp_quads.status_code, 200)

        # Root welcome endpoint responds
        resp_root = self.client.get("/")
        self.assertEqual(resp_root.status_code, 200)

        # Restore ready status
        with movigo_clock._lock:
            movigo_clock.current_status = "ready"
            movigo_clock.latest_datetime = datetime(2024, 1, 3, 23, 59, 59)

    def test_concurrent_multithreaded_clock_access(self):
        """Verify thread-safe concurrent reads and validation while clock state is being updated."""
        import threading
        import time

        errors = []

        def reader_task():
            try:
                for _ in range(50):
                    status = movigo_clock.get_status()
                    self.assertIn(status["current_status"], ("ready", "catching_up"))
                    movigo_clock.validate_time_bounds(
                        start_time=datetime(2024, 1, 1, 6, 0, 0),
                        end_time=datetime(2024, 1, 1, 8, 0, 0),
                    )
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def writer_task():
            try:
                for i in range(50):
                    with movigo_clock._lock:
                        movigo_clock.current_status = "catching_up" if i % 2 == 0 else "ready"
                        movigo_clock.latest_datetime = datetime(2024, 1, 2, i % 24, 0, 0)
                        movigo_clock.total_hours_simulated += 1
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader_task) for _ in range(10)]
        threads.append(threading.Thread(target=writer_task))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Encountered concurrency errors: {errors}")


if __name__ == "__main__":
    unittest.main()
