"""Unit tests for MoviGo passenger discrete mode choice (Multinomial Logit) and category-specific dynamic surge."""

import unittest
from datetime import datetime, date
import numpy as np
import pandas as pd

from data_sim.core.config import GLOBAL_SIMULATION_SEED
from movigo_sim.config import SERVICE_CATEGORIES, SERVICE_FARE_FACTORS
from movigo_sim.engine.platform import MoviGoPlatform
from movigo_sim.engine.simulator import (
    load_movigo_seed_catalogs,
    load_movigo_quadrants,
    load_movigo_vehicles,
    load_managua_street_network,
)
from movigo_sim.engine.world import WorldEnvironment
from movigo_sim.engine.entities import DriverAgent
from movigo_sim.analytics import compute_multinomial_mode_choice_metrics


class TestMultimodalChoice(unittest.TestCase):
    """Test suite validating Multinomial Logit mode choice, weather sensitivity, and category-level surge."""

    @classmethod
    def setUpClass(cls):
        cls.zones, cls.users, cls.drivers, cls.campaigns, cls.templates = load_movigo_seed_catalogs()
        cls.quadrants = load_movigo_quadrants()
        cls.vehicles = load_movigo_vehicles()
        cls.street_network = load_managua_street_network()
        cls.world = WorldEnvironment(
            quadrants=cls.quadrants,
            zones=cls.zones,
            street_network=cls.street_network,
        )
        cls.platform = MoviGoPlatform(campaigns=cls.campaigns, templates=cls.templates)
        cls.rng = np.random.default_rng(GLOBAL_SIMULATION_SEED)

    def test_fare_pricing_hierarchy(self):
        """Verify that comfort fare > standard fare > moto fare for identical distance and duration."""
        flag_drop = 45.0
        dist_km = 10.0
        dur_min = 25.0
        surge = 1.0

        base_moto, final_moto = self.platform.compute_fare(flag_drop, dist_km, dur_min, surge, "movigo_moto")
        base_std, final_std = self.platform.compute_fare(flag_drop, dist_km, dur_min, surge, "movigo_estandar")
        base_comf, final_comf = self.platform.compute_fare(flag_drop, dist_km, dur_min, surge, "movigo_comfort")

        self.assertLess(final_moto, final_std)
        self.assertLess(final_std, final_comf)

        # Exact ratio check
        self.assertAlmostEqual(base_moto / base_std, SERVICE_FARE_FACTORS["movigo_moto"], delta=0.01)
        self.assertAlmostEqual(base_comf / base_std, SERVICE_FARE_FACTORS["movigo_comfort"], delta=0.01)

    def test_logit_choice_dry_weather_popular_stratum(self):
        """Verify that in dry weather, popular stratum users exhibit strong preference for economical moto."""
        fares = {"movigo_moto": 80.0, "movigo_estandar": 130.0, "movigo_comfort": 185.0}
        etas = {"movigo_moto": 3.0, "movigo_estandar": 4.5, "movigo_comfort": 6.0}

        chosen, probs = self.platform.sample_mode_choice(
            stratum="popular",
            effective_water_mm=0.0,
            category_fares=fares,
            category_etas=etas,
            rng=self.rng,
        )
        self.assertIn(chosen, SERVICE_CATEGORIES)
        # In dry weather, moto dominates in popular stratum due to high price sensitivity
        self.assertGreater(probs["movigo_moto"], 0.50)
        self.assertLess(probs["movigo_comfort"], 0.10)

    def test_logit_choice_rain_collapse_moto(self):
        """Verify that in torrential rain, moto choice probability collapses to near zero while cars absorb demand."""
        fares = {"movigo_moto": 85.0, "movigo_estandar": 180.0, "movigo_comfort": 260.0}
        etas = {"movigo_moto": 5.0, "movigo_estandar": 7.0, "movigo_comfort": 8.0}

        # 8mm downpour
        chosen, probs = self.platform.sample_mode_choice(
            stratum="popular",
            effective_water_mm=8.0,
            category_fares=fares,
            category_etas=etas,
            rng=self.rng,
        )
        # Moto probability should plummet due to extreme rain aversion beta
        self.assertLess(probs["movigo_moto"], 0.02)
        # Standard and comfort should absorb more than 98% of the choice mass
        self.assertGreater(probs["movigo_estandar"] + probs["movigo_comfort"], 0.98)

    def test_independent_category_surge_multipliers(self):
        """Verify that surge multipliers react independently per category under rain conditions."""
        zone = self.zones[0]
        hour = 17 # Evening peak
        dow = 3

        # Test dry peak
        surge_dry = self.platform.simulate_category_surge_multipliers(
            origin_zone=zone,
            hourly_precip_mm=0.0,
            runoff_mm=0.0,
            flooded_roads=False,
            hour=hour,
            dow=dow,
            world=self.world,
            rng=self.rng,
        )
        self.assertIn("movigo_moto", surge_dry)
        self.assertIn("movigo_estandar", surge_dry)
        self.assertIn("movigo_comfort", surge_dry)

        # Test heavy rain peak
        surge_rain = self.platform.simulate_category_surge_multipliers(
            origin_zone=zone,
            hourly_precip_mm=12.0,
            runoff_mm=10.0,
            flooded_roads=True,
            hour=hour,
            dow=dow,
            world=self.world,
            rng=self.rng,
        )
        # Moto surge under rain remains baseline (demand collapsed)
        self.assertEqual(surge_rain["movigo_moto"][2], 1.00)
        # Standard and comfort surge must spike significantly higher than moto
        self.assertGreater(surge_rain["movigo_estandar"][2], surge_rain["movigo_moto"][2])
        self.assertGreater(surge_rain["movigo_comfort"][2], surge_rain["movigo_moto"][2])

    def test_driver_dispatch_matches_service_category(self):
        """Verify that dispatching filters drivers by their registered vehicle category."""
        # Create mock driver agents on duty (Tuesday)
        driver_agents = []
        veh_map = {v.driver_id: v for v in self.vehicles}
        for d in self.drivers[:30]:
            v = veh_map[d.driver_id]
            agent = DriverAgent(
                driver_id=d.driver_id,
                driver_model=d,
                vehicle_model=v,
                current_node=100,
                available_at=datetime(2024, 1, 2, 8, 0),
                status="activo",
                acceptance_rate_pct=d.acceptance_rate_pct,
                home_zone_id=1,
                home_quadrant_id=1,
                shift_name="matutino",
                weekly_rest_dow=6,  # Sunday rest day
            )
            driver_agents.append(agent)

        req_time = datetime(2024, 1, 2, 10, 0)

        # Dispatch specifically for movigo_moto
        moto_driver, _ = self.platform.dispatch_driver(
            free_drivers=driver_agents,
            all_operational_drivers=driver_agents,
            lat_o=12.1364,
            lon_o=-86.2514,
            req_time=req_time,
            world=self.world,
            rng=self.rng,
            service_type="movigo_moto",
        )
        self.assertEqual(moto_driver.vehicle_model.service_type, "movigo_moto")

        # Dispatch specifically for movigo_comfort
        comf_driver, _ = self.platform.dispatch_driver(
            free_drivers=driver_agents,
            all_operational_drivers=driver_agents,
            lat_o=12.1364,
            lon_o=-86.2514,
            req_time=req_time,
            world=self.world,
            rng=self.rng,
            service_type="movigo_comfort",
        )
        self.assertEqual(comf_driver.vehicle_model.service_type, "movigo_comfort")

    def test_multinomial_mode_choice_metrics_computation(self):
        """Verify that compute_multinomial_mode_choice_metrics produces valid shares and cross elasticities."""
        df_trips = pd.DataFrame([
            {"trip_id": 1, "driver_id": 1, "requested_at": "2024-01-01 10:00:00", "origin_quadrant_id": 1},
            {"trip_id": 2, "driver_id": 2, "requested_at": "2024-01-01 10:30:00", "origin_quadrant_id": 1},
            {"trip_id": 3, "driver_id": 3, "requested_at": "2024-01-01 11:00:00", "origin_quadrant_id": 1},
        ])
        df_payments = pd.DataFrame([
            {"trip_id": 1, "final_fare": 65.0, "surge_multiplier": 1.0},
            {"trip_id": 2, "final_fare": 130.0, "surge_multiplier": 1.2},
            {"trip_id": 3, "final_fare": 220.0, "surge_multiplier": 1.5},
        ])
        df_vehicles = pd.DataFrame([
            {"vehicle_id": 1, "driver_id": 1, "service_type": "movigo_moto"},
            {"vehicle_id": 2, "driver_id": 2, "service_type": "movigo_estandar"},
            {"vehicle_id": 3, "driver_id": 3, "service_type": "movigo_comfort"},
        ])

        res = compute_multinomial_mode_choice_metrics(df_trips, df_payments, df_vehicles)
        self.assertIn("cuota_modal_global", res)
        self.assertIn("elasticidad_precio_cruzada_estandar_moto", res)

        cg = res["cuota_modal_global"]
        self.assertEqual(cg["movigo_moto"]["viajes"], 1)
        self.assertEqual(cg["movigo_estandar"]["viajes"], 1)
        self.assertEqual(cg["movigo_comfort"]["viajes"], 1)
        self.assertAlmostEqual(cg["movigo_moto"]["porcentaje"], 33.33, delta=0.1)


if __name__ == "__main__":
    unittest.main()
