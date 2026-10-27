"""Unit tests for MoviGo Spatial GIS, Spatial Econometrics, and Hydrological Hazard Modeling."""

import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

from movigo_sim.weather import get_movigo_weather_series
from movigo_sim.generator import (
    MoviGoSimulationEngine,
    load_movigo_quadrants,
    load_movigo_drainage_channels,
)
from movigo_sim.spatial import (
    build_deterministic_urban_zones,
    build_deterministic_drainage_channels,
    haversine_km,
)
from movigo_sim.spatial_analytics import (
    build_od_matrix,
    calibrate_gravity_model,
    build_spatial_weights_matrix,
    compute_global_moran,
    compute_local_lisa,
    compute_cauce_vulnerability_surface,
    generate_hexagonal_grid,
)
from movigo_sim.exporter import export_movigo_spatial_layers
from movigo_sim.analytics import compute_movigo_spatial_gis


class TestMoviGoSpatialGIS(unittest.TestCase):
    """Verifies geospatial algorithms, spatial autocorrelation, and GIS layer exports."""

    @classmethod
    def setUpClass(cls):
        cls.weather_df, cls.weather_records = get_movigo_weather_series(seed=42)
        # Use 3 days simulation for fast reproducible testing
        cls.sim_weather = cls.weather_df.head(3)
        cls.engine = MoviGoSimulationEngine(random_seed=42)
        (
            cls.trips,
            cls.payments,
            cls.ratings,
            cls.cancellations,
            cls.telemetry,
            cls.maintenance,
        ) = cls.engine.run_simulation(cls.sim_weather)

        cls.df_trips = pd.DataFrame([t.model_dump() for t in cls.trips])
        cls.df_quadrants = pd.DataFrame([q.model_dump() for q in cls.engine.quadrants])
        cls.df_zones = pd.DataFrame([z.model_dump() for z in cls.engine.zones])
        cls.df_cauces = pd.DataFrame([c.model_dump() for c in load_movigo_drainage_channels()])

    def test_drainage_channels_catalog(self):
        """Verify 3NF drainage channels catalog integrity."""
        cauces = load_movigo_drainage_channels()
        self.assertGreaterEqual(len(cauces), 14)
        valid_zones = {z.zone_id for z in self.engine.zones}
        valid_risks = {"bajo", "medio", "alto", "critico"}

        for c in cauces:
            self.assertIn(c.zone_id, valid_zones)
            self.assertIn(c.vulnerability_level, valid_risks)
            self.assertGreater(c.critical_radius_km, 0.2)
            self.assertTrue(12.00 <= c.latitude <= 12.30)
            self.assertTrue(-86.45 <= c.longitude <= -86.10)
            self.assertTrue(len(c.channel_name) > 5)

    def test_od_matrix_conservation_and_flows(self):
        """Verify Origin-Destination matrix balances completed trips."""
        od_res = build_od_matrix(self.df_trips, self.df_quadrants, self.df_zones)
        completed_count = int((self.df_trips["trip_status"] == "completado").sum())

        self.assertEqual(od_res["total_completed_trips"], completed_count)
        self.assertAlmostEqual(
            od_res["intra_zone_share_pct"] + od_res["inter_zone_share_pct"],
            100.0,
            delta=0.01,
        )

        # Total trips in zone flow pairs equals completed trips
        sum_flows = sum(flow["num_trips"] for flow in od_res["zone_flows"])
        self.assertEqual(sum_flows, completed_count)

        # Distances and durations must be positive
        for flow in od_res["zone_flows"]:
            self.assertGreater(flow["mean_distance_km"], 0.0)
            self.assertGreater(flow["mean_duration_min"], 0.0)

    def test_wilson_gravity_model_distance_friction(self):
        """Verify Wilson's Gravity model parameter estimation displays distance decay (gamma > 0)."""
        od_res = build_od_matrix(self.df_trips, self.df_quadrants, self.df_zones)
        gravity_res = calibrate_gravity_model(od_res["zone_flows"], self.df_zones)

        # Spatial friction coefficient gamma must be strictly positive (distance decay)
        self.assertGreater(gravity_res["friction_gamma"], 0.0)
        self.assertTrue(0.0 <= gravity_res["r_squared"] <= 1.0)
        self.assertIn("Fricción de distancia estimada", gravity_res["interpretation"])

    def test_spatial_weights_matrix_properties(self):
        """Verify row-standardized spatial contiguity weights matrix W."""
        W_std, quadrant_ids = build_spatial_weights_matrix(self.df_quadrants, threshold_km=1.25)
        n = len(quadrant_ids)

        self.assertEqual(n, len(self.df_quadrants))
        self.assertEqual(W_std.shape, (len(self.df_quadrants), len(self.df_quadrants)))

        # Diagonal must be 0 (no self-loops in spatial lag)
        for i in range(n):
            self.assertEqual(W_std[i, i], 0.0)

        # Each row of row-standardized matrix must sum to 1.0
        row_sums = np.sum(W_std, axis=1)
        for s in row_sums:
            self.assertAlmostEqual(s, 1.0, delta=1e-5)

    def test_global_moran_i_spatial_autocorrelation(self):
        """Verify Global Moran's I on trip demand across Managua quadrants."""
        W_std, quadrant_ids = build_spatial_weights_matrix(self.df_quadrants, threshold_km=1.25)
        pickup_counts = self.df_trips.groupby("origin_quadrant_id").size().to_dict()
        demand_values = np.array([float(pickup_counts.get(qid, 0)) for qid in quadrant_ids])

        moran_res = compute_global_moran(demand_values, W_std)

        # Moran's I must be in valid correlation range [-1.0, 1.0]
        self.assertTrue(-1.0 <= moran_res["moran_i"] <= 1.0)
        self.assertLess(moran_res["expected_i"], 0.0)  # E[I] = -1 / (N - 1)
        self.assertGreater(moran_res["variance"], 0.0)
        self.assertIsInstance(moran_res["is_spatially_clustered"], bool)

    def test_local_lisa_hotspot_classification(self):
        """Verify Local Indicators of Spatial Association (LISA) classifications."""
        W_std, quadrant_ids = build_spatial_weights_matrix(self.df_quadrants, threshold_km=1.25)
        pickup_counts = self.df_trips.groupby("origin_quadrant_id").size().to_dict()
        demand_values = np.array([float(pickup_counts.get(qid, 0)) for qid in quadrant_ids])

        lisa_res = compute_local_lisa(demand_values, W_std, quadrant_ids, self.df_quadrants)

        self.assertEqual(lisa_res["total_quadrants"], len(self.df_quadrants))
        total_classified = sum(lisa_res["cluster_counts"].values())
        self.assertEqual(total_classified, len(self.df_quadrants))

        # Check that top hotspots list is populated
        self.assertGreater(len(lisa_res["top_hotspots"]), 0)
        for h in lisa_res["top_hotspots"]:
            self.assertEqual(h["cluster_type"], "High-High")
            self.assertGreaterEqual(h["z_std"], 0.0)
            self.assertGreaterEqual(h["spatial_lag"], 0.0)

    def test_cauce_flood_vulnerability_surface(self):
        """Verify hydraulic flood hazard index across all quadrants."""
        vuln_res = compute_cauce_vulnerability_surface(self.df_quadrants, self.df_cauces)

        self.assertEqual(vuln_res["total_quadrants"], len(self.df_quadrants))
        total_by_tier = sum(vuln_res["risk_distribution"].values())
        self.assertEqual(total_by_tier, len(self.df_quadrants))

        for q in vuln_res["quadrant_hazard_records"]:
            self.assertTrue(0.0 <= q["flood_hazard_index"] <= 1.0)
            self.assertIn(q["hydraulic_risk_tier"], {"bajo", "medio", "alto", "critico"})
            self.assertGreater(q["distance_to_cauce_km"], 0.0)

    def test_districts_coverage(self):
        """Verify all 7 municipal districts of Managua are represented."""
        districts = set(self.df_quadrants["district"].unique())
        expected_districts = {f"Distrito {d}" for d in ["I", "II", "III", "IV", "V", "VI", "VII"]}
        self.assertEqual(districts, expected_districts)

    def test_hexagonal_mesh_generation(self):
        """Verify hexagonal discrete tessellation mesh."""
        hex_cells = generate_hexagonal_grid()
        self.assertGreater(len(hex_cells), 50)

        for h in hex_cells:
            self.assertTrue(h["hex_id"].startswith("HEX_"))
            coords = h["polygon_coordinates"][0]
            # 6 vertices + 1 closing vertex = 7 coordinate pairs
            self.assertEqual(len(coords), 7)
            self.assertEqual(coords[0], coords[-1])  # Closed polygon

    def test_spatial_geojson_layers_export(self):
        """Verify GeoJSON layers export cleanly to disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            exported = export_movigo_spatial_layers(
                output_dir=tmp_path,
                quadrants=self.engine.quadrants,
                zones=self.engine.zones,
                drainage_channels=load_movigo_drainage_channels(),
            )

            self.assertIn("managua_quadrants", exported)
            self.assertIn("managua_zones", exported)
            self.assertIn("managua_cauces", exported)
            self.assertIn("managua_hex_grid", exported)

            # Validate GeoJSON format
            for name, p in exported.items():
                self.assertTrue(p.exists())
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data["type"], "FeatureCollection")
                self.assertGreater(len(data["features"]), 0)

            # Validate authentic LineString geometries in managua_cauces
            with open(exported["managua_cauces"], encoding="utf-8") as f:
                cauce_data = json.load(f)
            self.assertEqual(cauce_data["features"][0]["geometry"]["type"], "LineString")
            self.assertGreaterEqual(len(cauce_data["features"]), 100)

    def test_analytics_spatial_gis_integration(self):
        """Verify compute_movigo_spatial_gis returns all expected academic sections."""
        gis_summary = compute_movigo_spatial_gis(
            self.df_trips,
            self.df_quadrants,
            self.df_zones,
            self.df_cauces,
        )
        self.assertIn("matriz_origen_destino", gis_summary)
        self.assertIn("modelo_gravedad_wilson", gis_summary)
        self.assertIn("autocorrelacion_espacial_moran", gis_summary)
        self.assertIn("agrupamiento_lisa_puntos_calientes", gis_summary)
        self.assertIn("vulnerabilidad_hidraulica_cauces", gis_summary)


if __name__ == "__main__":
    unittest.main()
