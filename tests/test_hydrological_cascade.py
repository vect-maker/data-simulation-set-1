"""Unit tests for MoviGo hydrological cascade, cauce overflows, and dynamic street closures."""

import unittest
import numpy as np

from data_sim.core.config import GLOBAL_SIMULATION_SEED
from movigo_sim.weather import (
    load_quadrants_catalog,
    load_drainage_channels_catalog,
    compute_cauce_hydraulic_propagation,
    CAUCE_OVERFLOW_THRESHOLDS,
)
from movigo_sim.engine.world import WorldEnvironment
from movigo_sim.engine.simulator import load_managua_street_network, load_movigo_seed_catalogs


class TestHydrologicalCascade(unittest.TestCase):
    """Test suite validating authentic OSM cauce water propagation and street closures."""

    @classmethod
    def setUpClass(cls):
        cls.quadrants = load_quadrants_catalog()
        cls.channels = load_drainage_channels_catalog()
        cls.raw_graph = load_managua_street_network()
        cls.zones, _, _, _, _ = load_movigo_seed_catalogs()
        cls.world = WorldEnvironment(
            quadrants=cls.quadrants,
            zones=cls.zones,
            street_network=cls.raw_graph,
        )

    def test_cauce_catalog_integrity(self):
        """Verify that authentic OpenStreetMap cauces are correctly loaded."""
        self.assertGreaterEqual(len(self.channels), 14)
        names = {c.channel_name for c in self.channels}
        self.assertIn("Cauce Occidental", names)
        self.assertIn("Cauce Oriental", names)
        self.assertIn("Interceptora Tiscapa", names)

    def test_hydraulic_propagation_dimensions(self):
        """Verify output shapes of compute_cauce_hydraulic_propagation."""
        num_hours = 24
        n_quads = len(self.quadrants)
        rain_q = np.zeros((num_hours, n_quads), dtype=np.float32)
        # Simulate dry day
        discharge, overflow, overflow_quads = compute_cauce_hydraulic_propagation(
            rain_q, self.quadrants, self.channels
        )
        self.assertEqual(discharge.shape, (num_hours, len(self.channels)))
        self.assertEqual(overflow.shape, (num_hours, len(self.channels)))
        self.assertEqual(overflow_quads.shape, (num_hours, n_quads))
        self.assertFalse(np.any(overflow))
        self.assertFalse(np.any(overflow_quads))

    def test_upstream_rainfall_wave_lag(self):
        """Verify that upstream rainfall in southern Sierras propagates downstream with a 1-hour lag."""
        num_hours = 6
        n_quads = len(self.quadrants)
        rain_q = np.zeros((num_hours, n_quads), dtype=np.float32)

        # Identify southern high-altitude quadrants
        alts = np.array([q.mean_altitude_masl for q in self.quadrants])
        south_high_idx = np.where(alts >= 180)[0]
        self.assertGreater(len(south_high_idx), 0)

        # Inject flash downpour only at hour 1 in the southern hills
        rain_q[1, south_high_idx] = 25.0

        discharge, overflow, _ = compute_cauce_hydraulic_propagation(
            rain_q, self.quadrants, self.channels
        )

        # At hour 1, discharge begins rising
        self.assertGreater(np.max(discharge[1]), 0.0)

        # At hour 2 (delayed wave arrival), discharge peaks due to lag
        self.assertGreater(np.max(discharge[2]), 0.0)
        oriental_idx = next(i for i, c in enumerate(self.channels) if c.channel_name == "Cauce Oriental")
        self.assertGreater(discharge[2, oriental_idx], discharge[1, oriental_idx]) # Wave arrival increases discharge

    def test_cauce_overflow_detection(self):
        """Verify that severe downpours trigger cauce overflow flags and affect corridor quadrants."""
        num_hours = 4
        n_quads = len(self.quadrants)
        rain_q = np.full((num_hours, n_quads), 28.0, dtype=np.float32)

        discharge, overflow, overflow_quads = compute_cauce_hydraulic_propagation(
            rain_q, self.quadrants, self.channels
        )

        # Under a 28mm city-wide downpour, critical cauces must overflow
        self.assertTrue(np.any(overflow))
        self.assertTrue(np.any(overflow_quads))

        # Cauce Oriental (critical threshold 7.0) should overflow
        oriental_idx = next(i for i, c in enumerate(self.channels) if c.channel_name == "Cauce Oriental")
        self.assertTrue(overflow[1, oriental_idx])

    def test_world_overflow_route_detection(self):
        """Verify that WorldEnvironment detects paths that traverse active overflow quadrants."""
        active_q = int(self.world.node_quadrants[0])
        dummy_overflow_quads = {active_q}
        q_nodes = [i for i, q in enumerate(self.world.node_quadrants) if q == active_q]
        self.assertGreater(len(q_nodes), 0)

        is_affected = self.world.is_route_affected_by_overflow(q_nodes[:3], dummy_overflow_quads)
        self.assertTrue(is_affected)

        # Nodes in an unaffected quadrant
        diff_q = next((int(q) for q in self.world.node_quadrants if q != active_q), None)
        if diff_q is not None:
            q_other_nodes = [i for i, q in enumerate(self.world.node_quadrants) if q == diff_q]
            if q_other_nodes:
                is_not_affected = self.world.is_route_affected_by_overflow(q_other_nodes[:3], dummy_overflow_quads)
                self.assertFalse(is_not_affected)

    def test_routing_detour_under_overflow(self):
        """Verify that cauce overflow conditions increase travel duration and distance (detour physics)."""
        rng = np.random.default_rng(GLOBAL_SIMULATION_SEED)
        lat_o, lon_o = 12.1350, -86.2917 # Near Cauce Occidental
        lat_d, lon_d = 12.1463, -86.2434 # Near Cauce Oriental

        # Dry normal conditions
        dist_dry, dur_dry, _ = self.world.estimate_distance_and_duration(
            lat_o, lon_o, lat_d, lon_d,
            congestion_idx=1.0, rng=rng,
            effective_water_mm=0.0, flood_affected_route=False, is_cauce_overflow=False
        )

        # Reset RNG to ensure fair comparison
        rng_overflow = np.random.default_rng(GLOBAL_SIMULATION_SEED)
        dist_ovf, dur_ovf, _ = self.world.estimate_distance_and_duration(
            lat_o, lon_o, lat_d, lon_d,
            congestion_idx=1.0, rng=rng_overflow,
            effective_water_mm=12.0, flood_affected_route=True, is_cauce_overflow=True
        )

        self.assertGreaterEqual(dist_ovf, dist_dry)
        self.assertGreater(dur_ovf, dur_dry)

    def test_global_simulation_seed_determinism(self):
        """Verify that arbitrary seeds generate deterministic, reproducible results."""
        from movigo_sim.weather import fetch_movigo_weather_archive, build_hourly_quadrant_climate

        raw = fetch_movigo_weather_archive()

        # Run twice with seed 999
        _, mats_a = build_hourly_quadrant_climate(raw, seed=999)
        _, mats_b = build_hourly_quadrant_climate(raw, seed=999)

        np.testing.assert_array_equal(mats_a["precip"], mats_b["precip"])
        np.testing.assert_array_equal(mats_a["cauce_discharge"], mats_b["cauce_discharge"])
        np.testing.assert_array_equal(mats_a["cauce_overflow"], mats_b["cauce_overflow"])

        # Run with different seed 777: must produce different jitter
        _, mats_c = build_hourly_quadrant_climate(raw, seed=777)
        self.assertFalse(np.array_equal(mats_a["precip"], mats_c["precip"]))


if __name__ == "__main__":
    unittest.main()
