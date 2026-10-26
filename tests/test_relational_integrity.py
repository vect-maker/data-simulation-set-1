"""Integration tests verifying Relational Integrity across simulated databases."""

import unittest
from datetime import datetime
import pandas as pd

from antojitos_sim.weather import get_daily_weather_series
from antojitos_sim.generator import AntojitosSimulationEngine

from volcan_sim.weather import get_coffee_weather_series
from volcan_sim.generator import VolcanSimulationEngine

from movigo_sim.weather import get_movigo_weather_series
from movigo_sim.generator import MoviGoSimulationEngine
from movigo_sim.spatial import generate_deterministic_spatial_seeds


class TestRelationalIntegrity(unittest.TestCase):
    """Verifies primary-foreign key integrity and business constraints."""

    def test_antojitos_integrity(self):
        weather_df, clima_records = get_daily_weather_series()
        weather_df = weather_df.head(3)

        engine = AntojitosSimulationEngine(random_seed=42)
        orders, details = engine.run_simulation(weather_df)

        valid_zonas = {z.id_zona for z in engine.zonas}
        valid_repartidores = {r.id_repartidor for r in engine.repartidores}
        valid_platillos = {p.id_platillo for p in engine.platillos}
        valid_promos = {pr.id_promocion for pr in engine.promociones}

        order_ids = {o.id_orden for o in orders}

        # Check Order constraints
        for o in orders:
            self.assertIn(o.id_zona, valid_zonas)
            if o.id_repartidor is not None:
                self.assertIn(o.id_repartidor, valid_repartidores)
            if o.id_promocion is not None:
                self.assertIn(o.id_promocion, valid_promos)
            self.assertGreaterEqual(o.total_orden, 0.0)
            self.assertGreaterEqual(o.costo_envio, 0.0)
            self.assertGreaterEqual(o.propina, 0.0)

            # Business rule: delivery must not be before creation
            if o.fecha_hora_entrega is not None:
                self.assertGreaterEqual(o.fecha_hora_entrega, o.fecha_hora_creacion)

        # Check Detalle constraints
        for d in details:
            self.assertIn(d.id_orden, order_ids)
            self.assertIn(d.id_platillo, valid_platillos)
            self.assertGreater(d.cantidad, 0)
            self.assertGreater(d.precio_unitario, 0.0)
            self.assertAlmostEqual(d.subtotal, d.cantidad * d.precio_unitario, delta=0.01)

    def test_volcan_integrity(self):
        weather_df, clima_records = get_coffee_weather_series()
        weather_df = weather_df.head(3)

        engine = VolcanSimulationEngine(random_seed=42)
        lotes, procesos, subastas, embarques = engine.run_simulation(weather_df)

        valid_fincas = {f.id_finca for f in engine.fincas}
        valid_variedades = {v.id_variedad for v in engine.variedades}
        valid_beneficios = {b.id_beneficio for b in engine.beneficios}
        valid_lotes = {l.id_lote for l in lotes}

        for l in lotes:
            self.assertIn(l.id_finca, valid_fincas)
            self.assertIn(l.id_variedad, valid_variedades)
            self.assertGreater(l.peso_cereza_kg, 0.0)
            self.assertTrue(70.0 <= l.puntaje_catacion_scaa <= 100.0)
            self.assertTrue(40.0 <= l.humedad_porcentaje <= 68.0)

        for p in procesos:
            self.assertIn(p.id_lote, valid_lotes)
            self.assertIn(p.id_beneficio, valid_beneficios)
            self.assertGreaterEqual(p.peso_salida_kg, 0.0)
            self.assertTrue(0.0 <= p.merma_porcentaje <= 85.0)

        for e in embarques:
            self.assertIn(e.id_lote, valid_lotes)
            self.assertGreater(e.peso_oro_quintales, 0.0)
            self.assertGreater(e.precio_quintal_usd, 0.0)
            self.assertGreater(e.total_usd, 0.0)

    def test_movigo_integrity(self):
        weather_df, weather_records = get_movigo_weather_series()
        weather_df = weather_df.head(3)

        engine = MoviGoSimulationEngine(random_seed=42)
        trips, payments, ratings, cancellations, telemetry = engine.run_simulation(weather_df)

        valid_quadrants = {q.quadrant_id: q for q in engine.quadrants}
        valid_zones = {z.zone_id: z for z in engine.zones}
        valid_users = {u.user_id for u in engine.users}
        valid_drivers = {c.driver_id for c in engine.drivers}
        valid_trips = {v.trip_id: v for v in trips}

        # Verify 1:1 drivers <-> vehicles integrity
        self.assertEqual(len(engine.vehicles), len(engine.drivers))
        seen_vehicle_drivers = set()
        for veh in engine.vehicles:
            self.assertIn(veh.driver_id, valid_drivers)
            seen_vehicle_drivers.add(veh.driver_id)
        self.assertEqual(seen_vehicle_drivers, valid_drivers)

        self.assertEqual(len(engine.quadrants), 92)
        det_zones, det_quadrants, _ = generate_deterministic_spatial_seeds(dry_run=True)
        self.assertEqual([z.model_dump() for z in det_zones], [z.model_dump() for z in engine.zones])
        self.assertEqual([q.model_dump() for q in det_quadrants], [q.model_dump() for q in engine.quadrants])
        for q in engine.quadrants:
            self.assertIn(q.zone_id, valid_zones)

        for c in weather_records[:184]:
            self.assertIn(c.quadrant_id, valid_quadrants)
            self.assertTrue(0 <= c.hour <= 23)
            self.assertGreaterEqual(c.channel_runoff_mm, 0.0)

        for v in trips:
            self.assertIn(v.user_id, valid_users)
            if v.driver_id is not None:
                self.assertIn(v.driver_id, valid_drivers)
            self.assertIn(v.origin_quadrant_id, valid_quadrants)
            self.assertIn(v.destination_quadrant_id, valid_quadrants)
            qo = valid_quadrants[v.origin_quadrant_id]
            qd = valid_quadrants[v.destination_quadrant_id]
            self.assertNotEqual(qo.zone_id, qd.zone_id)
            self.assertTrue(qo.lat_min <= v.origin_latitude <= qo.lat_max)
            self.assertTrue(qo.lon_min <= v.origin_longitude <= qo.lon_max)
            self.assertTrue(qd.lat_min <= v.destination_latitude <= qd.lat_max)
            self.assertTrue(qd.lon_min <= v.destination_longitude <= qd.lon_max)
            self.assertGreaterEqual(v.distance_km, 0.0)
            self.assertGreaterEqual(v.duration_minutes, 0.0)

        # Verify 1:1 trips <-> trip_payments and derived fare formula
        self.assertEqual(len(payments), len(trips))
        for p in payments:
            self.assertIn(p.trip_id, valid_trips)
            t_obj = valid_trips[p.trip_id]
            zo = valid_zones[valid_quadrants[t_obj.origin_quadrant_id].zone_id]
            derived_base_fare = round(zo.base_flag_drop_fare + round(t_obj.distance_km * 18.0, 2) + round(t_obj.duration_minutes * 4.5, 2), 2)
            self.assertAlmostEqual(p.base_fare, derived_base_fare, delta=0.02)
            self.assertGreaterEqual(p.surge_multiplier, 1.0)
            self.assertAlmostEqual(
                p.final_fare,
                round(p.base_fare * p.surge_multiplier, 2),
                delta=0.02,
            )
            if t_obj.trip_status == "completado":
                self.assertEqual(p.payment_status, "pagado")
            else:
                self.assertEqual(p.payment_status, "anulado")

        # Verify trip_ratings (only completed trips) + trip_cancellations (only cancelled trips) partition trips
        self.assertEqual(len(ratings) + len(cancellations), len(trips))
        rated_trip_ids = set()
        for r in ratings:
            self.assertIn(r.trip_id, valid_trips)
            self.assertEqual(valid_trips[r.trip_id].trip_status, "completado")
            self.assertTrue(1.0 <= r.user_rating <= 5.0)
            self.assertTrue(1.0 <= r.driver_rating <= 5.0)
            rated_trip_ids.add(r.trip_id)

        cancelled_trip_ids = set()
        for canc in cancellations:
            self.assertIn(canc.trip_id, valid_trips)
            self.assertIn(valid_trips[canc.trip_id].trip_status, ["cancelado_usuario", "cancelado_conductor"])
            self.assertIn(canc.cancelled_by, ["usuario", "conductor"])
            self.assertGreaterEqual(canc.wait_time_minutes, 0.0)
            self.assertGreaterEqual(canc.origin_active_requests, 1)
            self.assertGreaterEqual(canc.origin_available_drivers, 1)
            cancelled_trip_ids.add(canc.trip_id)

        self.assertTrue(rated_trip_ids.isdisjoint(cancelled_trip_ids))

        for t in telemetry:
            self.assertIn(t.driver_id, valid_drivers)
            self.assertIn(t.quadrant_id, valid_quadrants)
            qt = valid_quadrants[t.quadrant_id]
            self.assertIn(qt.zone_id, valid_zones)
            self.assertTrue(qt.lat_min <= t.latitude <= qt.lat_max)
            self.assertTrue(qt.lon_min <= t.longitude <= qt.lon_max)
            self.assertGreaterEqual(t.speed_kmh, 0.0)
            self.assertIn(t.availability_status, ["disponible", "ocupado", "en_camino_recogida"])
            if t.availability_status == "disponible":
                self.assertIsNone(t.trip_id)
            else:
                self.assertIn(t.trip_id, valid_trips)

    def test_movigo_deterministic_reproducibility(self):
        import numpy as np
        from movigo_sim.config import SIMULATION_SEED
        from movigo_sim.enrichment import MoviGoSemanticEnricher

        self.assertIsInstance(SIMULATION_SEED, int)

        w_df_1, clima_1 = get_movigo_weather_series(seed=SIMULATION_SEED)
        w_df_2, clima_2 = get_movigo_weather_series(seed=SIMULATION_SEED)
        self.assertTrue(w_df_1.equals(w_df_2))
        self.assertTrue(clima_1.to_dataframe().head(200).equals(clima_2.to_dataframe().head(200)))

        engine = MoviGoSimulationEngine(random_seed=SIMULATION_SEED)
        enricher = MoviGoSemanticEnricher(engine.templates, random_seed=SIMULATION_SEED)

        trips_1, pay_1, rat_1, canc_1, tel_1 = engine.run_simulation(w_df_1.head(3))
        canc_1 = enricher.enrich_cancellations(canc_1)

        # Mutate global np.random in between to prove complete RNG isolation
        np.random.seed(99999)
        _ = np.random.rand(100)

        trips_2, pay_2, rat_2, canc_2, tel_2 = engine.run_simulation(w_df_2.head(3))
        canc_2 = enricher.enrich_cancellations(canc_2)

        self.assertEqual([v.model_dump() for v in trips_1], [v.model_dump() for v in trips_2])
        self.assertEqual([p.model_dump() for p in pay_1], [p.model_dump() for p in pay_2])
        self.assertEqual([r.model_dump() for r in rat_1], [r.model_dump() for r in rat_2])
        self.assertEqual([c.model_dump() for c in canc_1], [c.model_dump() for c in canc_2])
        self.assertEqual([t.model_dump() for t in tel_1], [t.model_dump() for t in tel_2])


if __name__ == "__main__":
    unittest.main()
