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
        weather_df, clima_records = get_movigo_weather_series()
        weather_df = weather_df.head(3)

        engine = MoviGoSimulationEngine(random_seed=42)
        viajes, telemetria = engine.run_simulation(weather_df)

        valid_cuadrantes = {q.id_cuadrante: q for q in engine.cuadrantes}
        valid_zonas = {z.id_zona for z in engine.zonas}
        valid_usuarios = {u.id_usuario for u in engine.usuarios}
        valid_conductores = {c.id_conductor for c in engine.conductores}
        valid_viajes = {v.id_viaje for v in viajes}

        self.assertEqual(len(engine.cuadrantes), 92)
        det_zonas, det_cuadrantes, _ = generate_deterministic_spatial_seeds(dry_run=True)
        self.assertEqual([z.model_dump() for z in det_zonas], [z.model_dump() for z in engine.zonas])
        self.assertEqual([q.model_dump() for q in det_cuadrantes], [q.model_dump() for q in engine.cuadrantes])
        for q in engine.cuadrantes:
            self.assertIn(q.id_zona, valid_zonas)

        for c in clima_records[:184]:
            self.assertIn(c.id_cuadrante, valid_cuadrantes)
            self.assertTrue(0 <= c.hora <= 23)
            self.assertGreaterEqual(c.escorrentia_cauce_mm, 0.0)

        for v in viajes:
            self.assertIn(v.id_usuario, valid_usuarios)
            if v.id_conductor is not None:
                self.assertIn(v.id_conductor, valid_conductores)
            self.assertIn(v.id_zona_origen, valid_zonas)
            self.assertIn(v.id_zona_destino, valid_zonas)
            self.assertIn(v.id_cuadrante_origen, valid_cuadrantes)
            self.assertIn(v.id_cuadrante_destino, valid_cuadrantes)
            qo = valid_cuadrantes[v.id_cuadrante_origen]
            qd = valid_cuadrantes[v.id_cuadrante_destino]
            self.assertEqual(qo.id_zona, v.id_zona_origen)
            self.assertEqual(qd.id_zona, v.id_zona_destino)
            self.assertTrue(qo.lat_min <= v.latitud_origen <= qo.lat_max)
            self.assertTrue(qo.lon_min <= v.longitud_origen <= qo.lon_max)
            self.assertTrue(qd.lat_min <= v.latitud_destino <= qd.lat_max)
            self.assertTrue(qd.lon_min <= v.longitud_destino <= qd.lon_max)
            self.assertGreaterEqual(v.tiempo_espera_minutos, 0.0)
            self.assertGreaterEqual(v.distancia_km, 0.0)
            self.assertGreaterEqual(v.duracion_minutos, 0.0)
            self.assertAlmostEqual(
                v.tarifa_base,
                v.tarifa_bajada_bandera + v.cargo_distancia + v.cargo_tiempo,
                delta=0.02,
            )
            self.assertGreaterEqual(v.multiplicador_dinamico, 1.0)
            self.assertAlmostEqual(
                v.tarifa_final,
                round(v.tarifa_base * v.multiplicador_dinamico, 2),
                delta=0.02,
            )
            self.assertGreaterEqual(v.solicitudes_activas_origen, 1)
            self.assertGreaterEqual(v.conductores_disponibles_origen, 1)

        for t in telemetria:
            self.assertIn(t.id_conductor, valid_conductores)
            self.assertIn(t.id_zona, valid_zonas)
            self.assertIn(t.id_cuadrante, valid_cuadrantes)
            qt = valid_cuadrantes[t.id_cuadrante]
            self.assertEqual(qt.id_zona, t.id_zona)
            self.assertTrue(qt.lat_min <= t.latitud <= qt.lat_max)
            self.assertTrue(qt.lon_min <= t.longitud <= qt.lon_max)
            self.assertGreaterEqual(t.velocidad_kmh, 0.0)
            self.assertIn(t.estado_disponibilidad, ["disponible", "ocupado", "en_camino_recogida"])
            if t.estado_disponibilidad == "disponible":
                self.assertIsNone(t.id_viaje)
            else:
                self.assertIn(t.id_viaje, valid_viajes)

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

        viajes_1, tel_1 = engine.run_simulation(w_df_1.head(3))
        viajes_1 = enricher.enrich_trips(viajes_1)

        # Mutate global np.random in between to prove complete RNG isolation
        np.random.seed(99999)
        _ = np.random.rand(100)

        viajes_2, tel_2 = engine.run_simulation(w_df_2.head(3))
        viajes_2 = enricher.enrich_trips(viajes_2)

        self.assertEqual([v.model_dump() for v in viajes_1], [v.model_dump() for v in viajes_2])
        self.assertEqual([t.model_dump() for t in tel_1], [t.model_dump() for t in tel_2])


if __name__ == "__main__":
    unittest.main()
