"""Unit tests for Hourly Traffic Indicators and Dynamic Driver Routing in MoviGo."""

from datetime import date, datetime, timedelta
import unittest
import numpy as np
import pandas as pd

from movigo_sim.engine.entities import DriverAgent
from movigo_sim.engine.simulator import MoviGoSimulationEngine
from movigo_sim.engine.world import WorldEnvironment
from movigo_sim.models import Driver, Vehicle, Quadrant, UrbanZone
from movigo_sim.analytics import compute_traffic_routing_metrics


class TestTrafficRouting(unittest.TestCase):
    """Test suite validating hourly traffic indicators on map and dynamic routing decisions."""

    def setUp(self):
        self.rng = np.random.Generator(np.random.PCG64(42))

        self.driver_model_comfort = Driver(
            driver_id=1,
            name="Roberto Gomez",
            average_rating=4.95,
            acceptance_rate_pct=98.0,
            status="activo",
        )
        self.driver_model_moto = Driver(
            driver_id=2,
            name="Luis Blandon",
            average_rating=4.75,
            acceptance_rate_pct=88.0,
            status="activo",
        )

        self.vehicle_comfort = Vehicle(
            vehicle_id=1,
            driver_id=1,
            service_type="movigo_comfort",
            vehicle_model="Toyota Corolla Hybrid",
            vehicle_year=2023,
            license_plate="M-800001",
        )
        self.vehicle_moto = Vehicle(
            vehicle_id=2,
            driver_id=2,
            service_type="movigo_moto",
            vehicle_model="Honda GL 150",
            vehicle_year=2022,
            license_plate="M-800002",
        )

        self.agent_comfort = DriverAgent(
            driver_id=1,
            driver_model=self.driver_model_comfort,
            vehicle_model=self.vehicle_comfort,
            current_node=100,
            available_at=datetime(2024, 6, 15, 6, 0),
            status="disponible",
            acceptance_rate_pct=98.0,
            home_zone_id=1,
            home_quadrant_id=1,
        )
        self.agent_moto = DriverAgent(
            driver_id=2,
            driver_model=self.driver_model_moto,
            vehicle_model=self.vehicle_moto,
            current_node=100,
            available_at=datetime(2024, 6, 15, 6, 0),
            status="disponible",
            acceptance_rate_pct=88.0,
            home_zone_id=1,
            home_quadrant_id=1,
        )

    def test_driver_decision_rule_vehicle_tier(self):
        """Verify comfort drivers adopt traffic navigation significantly more often than moto drivers."""
        n_samples = 1000
        # Peak rush hour 8 AM, moderate congestion 2.0
        comfort_choices = [
            self.agent_comfort.decide_traffic_aware_navigation(8, 2.0, self.rng)
            for _ in range(n_samples)
        ]
        moto_choices = [
            self.agent_moto.decide_traffic_aware_navigation(8, 2.0, self.rng)
            for _ in range(n_samples)
        ]

        comfort_pct = sum(comfort_choices) / n_samples
        moto_pct = sum(moto_choices) / n_samples

        self.assertGreater(comfort_pct, moto_pct)
        self.assertGreater(comfort_pct, 0.60)
        self.assertLess(moto_pct, 0.60)

    def test_driver_decision_rule_rush_hour_and_stress(self):
        """Verify rush hour and accumulated driver stress increase adoption probability."""
        n_samples = 1000
        # Off-peak 3 AM vs Morning Rush 8 AM for same driver
        self.agent_comfort.traffic_stress_accumulated = 0.0
        offpeak_choices = [
            self.agent_comfort.decide_traffic_aware_navigation(3, 1.1, self.rng)
            for _ in range(n_samples)
        ]
        rush_choices = [
            self.agent_comfort.decide_traffic_aware_navigation(8, 2.5, self.rng)
            for _ in range(n_samples)
        ]

        offpeak_pct = sum(offpeak_choices) / n_samples
        rush_pct = sum(rush_choices) / n_samples
        self.assertGreater(rush_pct, offpeak_pct)

        # High stress boost
        self.agent_comfort.traffic_stress_accumulated = 2.0
        stress_choices = [
            self.agent_comfort.decide_traffic_aware_navigation(3, 1.1, self.rng)
            for _ in range(n_samples)
        ]
        stress_pct = sum(stress_choices) / n_samples
        self.assertGreater(stress_pct, offpeak_pct)

    def test_world_hourly_traffic_cache_management(self):
        """Verify update_hourly_traffic caches up to 24 keys and purges older keys."""
        # Create minimal synthetic world environment
        quads = [
            Quadrant(
                quadrant_id=i,
                zone_id=1,
                district="Distrito I",
                quadrant_code=f"Q{i:02d}",
                quadrant_name=f"Quad {i}",
                grid_row=0,
                grid_col=i,
                lat_min=12.10,
                lat_max=12.12,
                lon_min=-86.25,
                lon_max=-86.23,
                mean_altitude_masl=100,
                flood_risk="bajo",
                main_drainage_channels="Ninguno",
            )
            for i in range(1, 5)
        ]
        zones = [
            UrbanZone(
                zone_id=1,
                zone_name="Zona Central",
                district="Distrito I",
                latitude=12.11,
                longitude=-86.24,
                coverage_radius_km=3.5,
                socioeconomic_stratum="medio",
                base_flag_drop_fare=35.0,
            )
        ]
        # 4 nodes, 3 edges
        street_net = {
            "nodes": [
                [12.105, -86.245, 1, 1],
                [12.106, -86.244, 2, 1],
                [12.107, -86.243, 3, 1],
                [12.108, -86.242, 4, 1],
            ],
            "edges": [
                [0, 1, 0.5, 30.0, 1, 0, 1],
                [1, 2, 0.6, 25.0, 2, 0, 1],
                [2, 3, 0.4, 20.0, 3, 0, 1],
            ],
            "quad_hubs": {"1": 0, "2": 1, "3": 2, "4": 3},
            "quadrant_node_indices": {"1": [0], "2": [1], "3": [2], "4": [3]},
        }
        world = WorldEnvironment(quads, zones, street_net)

        # Prime with 30 distinct keys
        cong_arr = np.array([1.2, 1.8, 2.5, 1.1])
        for k in range(30):
            world.update_hourly_traffic(k, cong_arr)

        # Ensure cache size does not exceed 24
        self.assertLessEqual(len(world.hourly_preds_traffic_hubs), 24)
        # Most recent key 29 must exist
        self.assertIn(29, world.hourly_preds_traffic_hubs)

    def test_compute_traffic_routing_metrics(self):
        """Verify computation of comparative traffic routing and delay reduction metrics."""
        self.agent_comfort.trips_rerouted_traffic = 15
        self.agent_comfort.traffic_minutes_saved = 45.0
        self.agent_moto.trips_rerouted_traffic = 5
        self.agent_moto.traffic_minutes_saved = 10.0

        df_trips = pd.DataFrame([{"trip_id": i} for i in range(100)])
        agents = [self.agent_comfort, self.agent_moto]

        metrics = compute_traffic_routing_metrics(agents, df_trips)

        self.assertEqual(metrics["total_viajes"], 100)
        self.assertEqual(metrics["total_viajes_re_enrutados_trafico"], 20)
        self.assertEqual(metrics["porcentaje_re_enrutamiento_trafico"], 20.0)
        self.assertEqual(metrics["minutos_totales_demora_evitados"], 55.0)
        self.assertEqual(metrics["promedio_minutos_ahorrados_por_re_enrutamiento"], 2.75)
        self.assertIn("movigo_comfort", metrics["desglose_por_categoria_servicio"])
        self.assertEqual(
            metrics["desglose_por_categoria_servicio"]["movigo_comfort"]["viajes_re_enrutados_por_trafico"],
            15,
        )

    def test_traffic_routing_hourly_slice_and_rerouting(self):
        """Verify MoviGoSimulationEngine runs with hourly traffic indicators and records rerouting."""
        engine = MoviGoSimulationEngine(random_seed=42)
        target_dt = datetime(2024, 6, 15, 8, 0) # Morning rush hour 8 AM
        weather_dict = {
            "precipitation_mm": 2.5,
            "congestion_index": 2.35,
            "temperature_c": 28.5,
        }
        trips, payments, ratings, cancellations, telemetry, maintenance, weather_records = (
            engine.simulate_hourly_slice(target_dt, weather_dict)
        )

        self.assertGreater(len(trips), 0)
        self.assertEqual(len(weather_records), len(engine.quadrants))

        # Check telemetry breadcrumbs
        self.assertGreater(len(telemetry), 0)
        for ping in telemetry[:5]:
            self.assertGreater(ping.speed_kmh, 0.0)
            self.assertIn(ping.availability_status, ("en_camino_recogida", "ocupado", "disponible", "descanso"))

        # Compute traffic metrics across engine's driver agents
        df_trips = pd.DataFrame([t.model_dump() for t in trips])
        metrics = compute_traffic_routing_metrics(engine.driver_agents, df_trips)
        self.assertIn("total_viajes_re_enrutados_trafico", metrics)
        self.assertIn("minutos_totales_demora_evitados", metrics)


if __name__ == "__main__":
    unittest.main()
