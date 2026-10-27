"""Unit tests for MoviGo Apache Parquet export and dedicated database loading."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from datetime import datetime, date

import numpy as np
import pandas as pd
from pydantic import BaseModel

from data_sim.core.exporter import export_models_to_parquet
from movigo_sim.exporter import export_movigo_to_parquet
from movigo_sim.models import (
    UrbanZone,
    Quadrant,
    User,
    Driver,
    Vehicle,
    IncentiveCampaign,
    Trip,
    TripPayment,
    TripRating,
    TripCancellation,
    DriverTelemetry,
    VehicleMaintenance,
    DrainageChannel,
    QuadrantWeather,
)
from scripts.load_movigo_parquet_to_postgres import (
    clean_record_value,
    TABLE_LOAD_ORDER,
    load_parquet_table,
    TableLoadResult,
)
from unittest.mock import MagicMock, patch


class SampleModel(BaseModel):
    id: int
    name: str
    amount: float
    is_active: bool
    created_at: datetime


class TestParquetExportAndLoader(unittest.TestCase):
    """Test suite validating Parquet file generation, schemas, and loader helpers."""

    def test_export_models_to_parquet_creates_valid_files(self) -> None:
        """Verify export_models_to_parquet writes valid Snappy Parquet files readable by pandas."""
        records = [
            SampleModel(
                id=1,
                name="Ruta 1",
                amount=125.50,
                is_active=True,
                created_at=datetime(2024, 1, 1, 8, 30),
            ),
            SampleModel(
                id=2,
                name="Ruta 2",
                amount=85.00,
                is_active=False,
                created_at=datetime(2024, 1, 1, 9, 15),
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            files = export_models_to_parquet({"sample_table": records}, out_dir)

            self.assertIn("sample_table", files)
            p_file = files["sample_table"]
            self.assertTrue(p_file.exists())
            self.assertEqual(p_file.suffix, ".parquet")

            # Read back using pandas
            df = pd.read_parquet(p_file)
            self.assertEqual(len(df), 2)
            self.assertEqual(list(df.columns), ["id", "name", "amount", "is_active", "created_at"])
            self.assertEqual(int(df.loc[0, "id"]), 1)
            self.assertEqual(str(df.loc[0, "name"]), "Ruta 1")
            self.assertEqual(float(df.loc[0, "amount"]), 125.50)
            self.assertTrue(bool(df.loc[0, "is_active"]))

    def test_clean_record_value_handles_special_types(self) -> None:
        """Verify clean_record_value normalizes Pandas/Numpy types for psycopg2 binding."""
        self.assertIsNone(clean_record_value(np.nan))
        self.assertIsNone(clean_record_value(pd.NA))
        self.assertIsNone(clean_record_value(None))

        self.assertEqual(clean_record_value(np.int64(42)), 42)
        self.assertEqual(clean_record_value(np.float64(3.1416)), 3.1416)
        self.assertEqual(clean_record_value(np.bool_(True)), True)

        ts = pd.Timestamp("2024-01-01 12:00:00")
        dt_res = clean_record_value(ts)
        self.assertIsInstance(dt_res, datetime)
        self.assertEqual(dt_res.year, 2024)

    def test_export_movigo_to_parquet_generates_all_14_tables(self) -> None:
        """Verify export_movigo_to_parquet exports all 14 relational tables as Parquet."""
        zone = UrbanZone(
            zone_id=1,
            zone_name="Bolonia",
            district="Distrito I",
            latitude=12.13,
            longitude=-86.27,
            coverage_radius_km=3.0,
            socioeconomic_stratum="medio",
            base_flag_drop_fare=35.0,
        )
        quad = Quadrant(
            quadrant_id=1,
            quadrant_code="Q-01-01",
            quadrant_name="Bolonia Norte",
            zone_id=1,
            district="Distrito I",
            grid_row=1,
            grid_col=1,
            lat_min=12.12,
            lat_max=12.14,
            lon_min=-86.28,
            lon_max=-86.26,
            center_lat=12.13,
            center_lon=-86.27,
            mean_altitude_masl=100.0,
            flood_risk="bajo",
            main_drainage_channels="Ninguno",
        )
        user = User(
            user_id=1,
            name="Maria Lopez",
            phone="+50588880001",
            preferred_payment_method="tarjeta",
            average_rating=4.90,
            registration_date=date(2024, 1, 1),
        )
        driver = Driver(
            driver_id=1,
            name="Carlos Ruiz",
            average_rating=4.85,
            acceptance_rate_pct=95.0,
            status="activo",
        )
        vehicle = Vehicle(
            vehicle_id=1,
            driver_id=1,
            service_type="movigo_estandar",
            vehicle_model="Toyota Yaris",
            vehicle_year=2021,
            license_plate="M-123456",
        )
        campaign = IncentiveCampaign(
            campaign_id=1,
            target_zone_id=1,
            bonus_name="Bono Verano",
            budget_cost_nio=5000.0,
            online_hours_increase=60.0,
            incentive_type="meta_viajes",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 15),
            status="activa",
        )
        weather = [
            QuadrantWeather(
                weather_id=1,
                quadrant_id=1,
                recorded_at=datetime(2024, 1, 1, 8, 0),
                date=date(2024, 1, 1),
                hour=8,
                precipitation_mm=0.0,
                channel_runoff_mm=0.0,
                temperature_c=27.5,
                congestion_index=1.2,
                flooded_roads=False,
                sky_condition="despejado",
            )
        ]
        trip = Trip(
            trip_id=1,
            user_id=1,
            driver_id=1,
            origin_quadrant_id=1,
            destination_quadrant_id=1,
            origin_latitude=12.13,
            origin_longitude=-86.27,
            destination_latitude=12.135,
            destination_longitude=-86.265,
            requested_at=datetime(2024, 1, 1, 8, 30),
            started_at=datetime(2024, 1, 1, 8, 35),
            completed_at=datetime(2024, 1, 1, 8, 50),
            distance_km=3.5,
            duration_minutes=15.0,
            trip_status="completado",
        )
        payment = TripPayment(
            payment_id=1,
            trip_id=1,
            payment_method="tarjeta",
            base_fare=100.0,
            surge_multiplier=1.0,
            tip_amount=10.0,
            final_fare=110.0,
            payment_status="pagado",
        )
        rating = TripRating(
            rating_id=1,
            trip_id=1,
            user_rating=5.0,
            driver_rating=5.0,
        )
        cancellation = TripCancellation(
            cancellation_id=1,
            trip_id=1,
            cancelled_by="usuario",
            cancellation_reason="Demora excesiva",
            wait_time_minutes=8.0,
            origin_active_requests=10,
            origin_available_drivers=2,
        )
        tel = DriverTelemetry(
            telemetry_id=1,
            driver_id=1,
            trip_id=1,
            quadrant_id=1,
            recorded_at=datetime(2024, 1, 1, 8, 32),
            latitude=12.13,
            longitude=-86.27,
            speed_kmh=25.0,
            availability_status="en_camino_recogida",
        )
        maint = VehicleMaintenance(
            maintenance_id=1,
            vehicle_id=1,
            service_date=date(2024, 1, 1),
            maintenance_type="preventivo",
            odometer_km=25000.0,
            description="Cambio de aceite",
            cost_nio=1500.0,
            downtime_hours=2.0,
            workshop_name="Taller Central",
        )
        drainage = [
            DrainageChannel(
                channel_id=1,
                channel_name="Cauce Oriental",
                zone_id=1,
                latitude=12.13,
                longitude=-86.27,
                critical_radius_km=1.0,
                vulnerability_level="alto",
                flow_direction="Sur-Norte",
            )
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            files = export_movigo_to_parquet(
                zones=[zone],
                users=[user],
                drivers=[driver],
                vehicles=[vehicle],
                campaigns=[campaign],
                weather=weather,
                trips=[trip],
                payments=[payment],
                ratings=[rating],
                cancellations=[cancellation],
                telemetry=[tel],
                maintenance=[maint],
                drainage_channels=drainage,
                output_dir=out_dir,
                quadrants=[quad],
            )

            # Check that all 14 tables in TABLE_LOAD_ORDER exist
            for tbl in TABLE_LOAD_ORDER:
                self.assertIn(tbl, files)
                p_file = files[tbl]
                self.assertTrue(p_file.exists(), f"File {p_file} should exist")
                self.assertEqual(p_file.suffix, ".parquet")
                df = pd.read_parquet(p_file)
                self.assertGreater(len(df), 0, f"Table {tbl} should have records")

    @patch("scripts.load_movigo_parquet_to_postgres.execute_values")
    def test_load_parquet_table_in_batches(self, mock_execute_values: MagicMock) -> None:
        """Verify load_parquet_table splits large datasets into configurable streaming batches."""
        records = [
            SampleModel(
                id=i,
                name=f"Ruta {i}",
                amount=float(i * 10),
                is_active=(i % 2 == 0),
                created_at=datetime(2024, 1, 1, 8, 0),
            )
            for i in range(1, 26)  # 25 records
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            files = export_models_to_parquet({"sample_table": records}, out_dir)
            p_file = files["sample_table"]

            mock_cur = MagicMock()
            mock_conn = MagicMock()

            # Load with batch_size=10 -> should execute in 3 batches (10, 10, 5)
            result = load_parquet_table(
                cursor=mock_cur,
                parquet_path=p_file,
                table_name="sample_table",
                schema="public",
                batch_size=10,
                conn=mock_conn,
                table_idx=1,
                total_tables=1,
            )

            self.assertIsInstance(result, TableLoadResult)
            self.assertEqual(result.row_count, 25)
            self.assertEqual(result.batch_count, 3)
            self.assertGreater(result.elapsed_seconds, 0.0)
            self.assertEqual(mock_conn.commit.call_count, 3)
            self.assertEqual(mock_execute_values.call_count, 3)

            # Check batch sizes passed to execute_values: 10, 10, 5
            batch_lengths = [len(call[0][2]) for call in mock_execute_values.call_args_list]
            self.assertEqual(batch_lengths, [10, 10, 5])

    def test_load_parquet_table_empty_file(self) -> None:
        """Verify load_parquet_table handles 0-row parquet files gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            p_file = Path(tmp_dir) / "empty.parquet"
            pd.DataFrame({"id": pd.Series(dtype="int64"), "name": pd.Series(dtype="str")}).to_parquet(p_file)

            mock_cur = MagicMock()
            mock_cur.connection.encoding = "UTF8"
            mock_conn = MagicMock()

            result = load_parquet_table(
                cursor=mock_cur,
                parquet_path=p_file,
                table_name="empty_table",
                schema="public",
                batch_size=100,
                conn=mock_conn,
            )

            self.assertEqual(result.row_count, 0)
            self.assertEqual(result.batch_count, 0)
            self.assertEqual(mock_conn.commit.call_count, 0)


if __name__ == "__main__":
    unittest.main()
