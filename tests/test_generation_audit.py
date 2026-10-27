"""Unit tests for MoviGo simulation generation audit logging and progress feedback."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from movigo_sim.engine.recorder import SimulationRecorder
from movigo_sim.engine.simulator import MoviGoSimulationEngine
from movigo_sim.exporter import (
    export_movigo_audit_logs,
    compute_movigo_simulation_summary,
)
from movigo_sim.models import (
    UrbanZone,
    Quadrant,
    IncentiveCampaign,
)
from movigo_sim.weather import get_movigo_weather_series


class TestGenerationAuditLogs(unittest.TestCase):
    """Test suite for generation audit logs, progress hooks, and export formatting."""

    def test_simulation_recorder_audit_logging(self) -> None:
        """Verify SimulationRecorder captures structured audit entries correctly."""
        recorder = SimulationRecorder()
        self.assertEqual(len(recorder.get_audit_logs()), 0)

        entry = recorder.record_audit_entry(
            simulation_date="2024-01-01",
            day_name="Monday",
            is_weekend=False,
            weather_precip_mm=2.5,
            congestion_index=1.15,
            daily_demand_target=120,
            trips_dispatched=120,
            trips_completed=110,
            trips_canceled=10,
            telemetry_records=550,
            step_duration_seconds=0.3421,
        )

        audit_logs = recorder.get_audit_logs()
        self.assertEqual(len(audit_logs), 1)
        self.assertEqual(audit_logs[0]["simulation_date"], "2024-01-01")
        self.assertEqual(audit_logs[0]["day_name"], "Monday")
        self.assertFalse(audit_logs[0]["is_weekend"])
        self.assertEqual(audit_logs[0]["weather_precip_mm"], 2.5)
        self.assertEqual(audit_logs[0]["congestion_index"], 1.15)
        self.assertEqual(audit_logs[0]["daily_demand_target"], 120)
        self.assertEqual(audit_logs[0]["trips_dispatched"], 120)
        self.assertEqual(audit_logs[0]["trips_completed"], 110)
        self.assertEqual(audit_logs[0]["trips_canceled"], 10)
        self.assertEqual(audit_logs[0]["telemetry_records"], 550)
        self.assertEqual(audit_logs[0]["step_duration_seconds"], 0.3421)
        self.assertIn("real_timestamp", audit_logs[0])

    def test_simulator_generates_daily_audit_logs_and_callback(self) -> None:
        """Verify MoviGoSimulationEngine records audit entries for every simulated day and calls callback."""
        weather_df, _ = get_movigo_weather_series(seed=42)
        three_days_df = weather_df.head(3).copy()

        engine = MoviGoSimulationEngine(random_seed=42)

        callbacks_received: list[dict] = []

        def on_day_progress(audit_entry, day_num, total_days):
            callbacks_received.append({
                "entry": audit_entry,
                "day_num": day_num,
                "total_days": total_days,
            })

        trips, payments, ratings, cancellations, telemetry, maintenance = engine.run_simulation(
            three_days_df,
            progress_callback=on_day_progress,
        )

        self.assertEqual(len(callbacks_received), 3)
        self.assertEqual(callbacks_received[0]["day_num"], 1)
        self.assertEqual(callbacks_received[0]["total_days"], 3)
        self.assertEqual(callbacks_received[2]["day_num"], 3)

        self.assertEqual(len(engine.audit_logs), 3)
        expected_dates = [str(d) for d in three_days_df["date"]]
        actual_dates = [e["simulation_date"] for e in engine.audit_logs]
        self.assertEqual(actual_dates, expected_dates)

        # Check running totals and latency fields
        for entry in engine.audit_logs:
            self.assertGreater(entry["trips_completed"], 0)
            self.assertGreater(entry["step_duration_seconds"], 0.0)
            self.assertIn(entry["day_name"], ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])

    def test_exporter_writes_audit_jsonl_and_summary(self) -> None:
        """Verify export_movigo_audit_logs writes valid JSONL and summary includes audit metrics."""
        mock_audit_logs = [
            {
                "real_timestamp": "2024-01-01T00:00:00Z",
                "simulation_date": "2024-01-01",
                "day_name": "Monday",
                "is_weekend": False,
                "weather_precip_mm": 0.0,
                "congestion_index": 1.0,
                "daily_demand_target": 100,
                "trips_dispatched": 100,
                "trips_completed": 95,
                "trips_canceled": 5,
                "telemetry_records": 400,
                "step_duration_seconds": 0.25,
                "cumulative_trips": 95,
                "cumulative_telemetry": 400,
            },
            {
                "real_timestamp": "2024-01-02T00:00:00Z",
                "simulation_date": "2024-01-02",
                "day_name": "Tuesday",
                "is_weekend": False,
                "weather_precip_mm": 12.0,
                "congestion_index": 1.35,
                "daily_demand_target": 150,
                "trips_dispatched": 150,
                "trips_completed": 138,
                "trips_canceled": 12,
                "telemetry_records": 580,
                "step_duration_seconds": 0.35,
                "cumulative_trips": 233,
                "cumulative_telemetry": 980,
            },
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            jsonl_file = tmp_path / "logs" / "generation_audit.jsonl"
            out_file = export_movigo_audit_logs(mock_audit_logs, log_path=jsonl_file)

            self.assertTrue(out_file.exists())
            with open(out_file, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["simulation_date"], "2024-01-01")
            self.assertEqual(lines[1]["simulation_date"], "2024-01-02")
            self.assertEqual(lines[1]["trips_completed"], 138)

            # Test summary integration
            engine = MoviGoSimulationEngine(random_seed=42)
            weather_df, weather_records = get_movigo_weather_series(seed=42)
            two_days = weather_df.head(2)

            trips, payments, ratings, cancellations, telemetry, maintenance = engine.run_simulation(two_days)

            summary_file = tmp_path / "simulation_summary.json"
            summary = compute_movigo_simulation_summary(
                zones=engine.zones,
                quadrants=engine.quadrants,
                trips=trips,
                payments=payments,
                weather=weather_records,
                campaigns=engine.campaigns,
                cancellations=cancellations,
                maintenance=maintenance,
                vehicles=engine.vehicles,
                drivers=engine.drivers,
                driver_agents=engine.driver_agents,
                workshops=engine.world.workshops,
                seed=42,
                summary_path=summary_file,
                audit_logs=engine.audit_logs,
            )

            self.assertIn("registro_auditoria_generacion", summary)
            aud = summary["registro_auditoria_generacion"]
            self.assertEqual(aud["total_dias_simulados"], 2)
            self.assertGreater(aud["tiempo_total_generacion_segundos"], 0.0)
            self.assertGreater(aud["velocidad_generacion_viajes_por_segundo"], 0.0)
            self.assertTrue(Path(aud["archivo_log_auditoria"]).exists())


if __name__ == "__main__":
    unittest.main()
