"""Unit tests for Prioridad 3: Driver Agent Heterogeneity, Shift Fatigue & Burnout,
Hydrological Risk Aversion, and Deadhead Distance Refusal in MoviGo.
"""

from datetime import date, datetime, time, timedelta
import unittest
import numpy as np
import pandas as pd

from movigo_sim.engine.entities import DriverAgent
from movigo_sim.engine.platform import MoviGoPlatform
from movigo_sim.engine.world import WorldEnvironment
from movigo_sim.models import Driver, Vehicle
from movigo_sim.analytics import compute_driver_heterogeneity_and_churn_metrics


class TestDriverHeterogeneity(unittest.TestCase):
    """Test suite validating behavioral driver traits, fatigue, and dispatch retry dynamics."""

    def setUp(self):
        self.rng = np.random.Generator(np.random.PCG64(42))

        # Sample mock driver models
        self.driver_model_1 = Driver(
            driver_id=1,
            name="Carlos Martinez",
            average_rating=4.85,
            acceptance_rate_pct=92.0,
            status="activo",
        )
        self.driver_model_2 = Driver(
            driver_id=2,
            name="Elena Rivas",
            average_rating=4.92,
            acceptance_rate_pct=95.0,
            status="activo",
        )

        # Vehicles
        self.moto_vehicle = Vehicle(
            vehicle_id=1,
            driver_id=1,
            service_type="movigo_moto",
            vehicle_model="Yamaha YBR 125",
            vehicle_year=2022,
            license_plate="M-100001",
        )
        self.comfort_vehicle = Vehicle(
            vehicle_id=2,
            driver_id=2,
            service_type="movigo_comfort",
            vehicle_model="Toyota RAV4",
            vehicle_year=2023,
            license_plate="M-100002",
        )
        self.standard_vehicle = Vehicle(
            vehicle_id=3,
            driver_id=3,
            service_type="movigo_estandar",
            vehicle_model="Toyota Yaris",
            vehicle_year=2021,
            license_plate="M-100003",
        )

    def test_risk_aversion_moto_rejects_overflow_cauce(self):
        """Verify that a moto driver predominantly rejects routes crossing overflowing cauces."""
        moto_agent = DriverAgent(
            driver_id=1,
            driver_model=self.driver_model_1,
            vehicle_model=self.moto_vehicle,
            current_node=100,
            available_at=datetime.min,
            status="activo",
            acceptance_rate_pct=90.0,
            home_zone_id=1,
            home_quadrant_id=1,
        )
        self.assertGreaterEqual(moto_agent.risk_aversion, 0.70)

        rejections = 0
        trials = 100
        req_time = datetime(2024, 1, 2, 8, 30)  # Rested, morning
        for seed in range(trials):
            trial_rng = np.random.Generator(np.random.PCG64(seed))
            accepted, reason = moto_agent.evaluate_trip_offer(
                pickup_km=1.2,
                trip_dist_km=4.5,
                trip_dur_min=12.0,
                fare=95.0,
                is_route_overflow=True,
                dest_zone_id=1,
                req_time=req_time,
                rng=trial_rng,
            )
            if not accepted:
                self.assertIn("cauce desbordado", reason)
                rejections += 1

        # Moto should reject in >= 80% of trials under overflow
        self.assertGreater(rejections / trials, 0.80)

    def test_comfort_suv_higher_water_tolerance(self):
        """Verify that comfort SUVs have higher tolerance and accept overflowing routes much more often."""
        comf_agent = DriverAgent(
            driver_id=2,
            driver_model=self.driver_model_2,
            vehicle_model=self.comfort_vehicle,
            current_node=100,
            available_at=datetime.min,
            status="activo",
            acceptance_rate_pct=95.0,
            home_zone_id=1,
            home_quadrant_id=1,
        )
        self.assertLessEqual(comf_agent.risk_aversion, 0.35)

        accepts = 0
        trials = 100
        req_time = datetime(2024, 1, 2, 8, 30)
        for seed in range(trials):
            trial_rng = np.random.Generator(np.random.PCG64(seed))
            accepted, reason = comf_agent.evaluate_trip_offer(
                pickup_km=1.2,
                trip_dist_km=4.5,
                trip_dur_min=12.0,
                fare=160.0,
                is_route_overflow=True,
                dest_zone_id=1,
                req_time=req_time,
                rng=trial_rng,
            )
            if accepted:
                accepts += 1

        # Comfort SUV should accept in >= 60% of trials
        self.assertGreater(accepts / trials, 0.60)

    def test_fatigue_increases_with_shift_hours(self):
        """Verify that driver fatigue and reaction delay increase monotonically across shift hours."""
        agent = DriverAgent(
            driver_id=3,
            driver_model=self.driver_model_1,
            vehicle_model=self.standard_vehicle,
            current_node=100,
            available_at=datetime.min,
            status="activo",
            acceptance_rate_pct=92.0,
            home_zone_id=1,
            home_quadrant_id=1,
            shift_name="matutino",
            shift_start_hour=6,
            shift_end_hour=14,
        )

        early_time = datetime(2024, 1, 2, 7, 30)  # 1.5 hrs into shift
        mid_time = datetime(2024, 1, 2, 11, 0)    # 5.0 hrs into shift
        late_time = datetime(2024, 1, 2, 13, 30)  # 7.5 hrs into shift

        f_early = agent.get_fatigue_level(early_time)
        f_mid = agent.get_fatigue_level(mid_time)
        f_late = agent.get_fatigue_level(late_time)

        self.assertLess(f_early, f_mid)
        self.assertLess(f_mid, f_late)
        self.assertGreater(f_late, 0.55)

        r_early = agent.get_reaction_time_delay(early_time)
        r_late = agent.get_reaction_time_delay(late_time)
        self.assertLess(r_early, r_late)
        self.assertGreater(r_late, 0.80)

    def test_fatigue_causes_rejection_of_distant_pickups(self):
        """Verify that an exhausted driver rejects distant pickups (> 2.5 km) near the end of their shift."""
        agent = DriverAgent(
            driver_id=3,
            driver_model=self.driver_model_1,
            vehicle_model=self.standard_vehicle,
            current_node=100,
            available_at=datetime.min,
            status="activo",
            acceptance_rate_pct=92.0,
            home_zone_id=1,
            home_quadrant_id=1,
            shift_name="matutino",
            shift_start_hour=6,
            shift_end_hour=14,
            traffic_stress_accumulated=4.0,  # Heavy traffic fatigue
        )

        req_time = datetime(2024, 1, 2, 13, 45)  # 7.75 hours on duty
        rejections = 0
        trials = 100
        for seed in range(trials):
            trial_rng = np.random.Generator(np.random.PCG64(seed))
            accepted, reason = agent.evaluate_trip_offer(
                pickup_km=4.2,  # Distant pickup
                trip_dist_km=8.0,
                trip_dur_min=25.0,
                fare=180.0,
                is_route_overflow=False,
                dest_zone_id=9,
                req_time=req_time,
                rng=trial_rng,
            )
            if not accepted and "fatigado" in reason:
                rejections += 1

        self.assertGreater(rejections / trials, 0.65)

    def test_deadhead_rejection_low_demand_destination(self):
        """Verify that a driver rejects requests with pickup > 4 km when the destination is a low-demand zone."""
        agent = DriverAgent(
            driver_id=3,
            driver_model=self.driver_model_1,
            vehicle_model=self.standard_vehicle,
            current_node=100,
            available_at=datetime.min,
            status="activo",
            acceptance_rate_pct=92.0,
            home_zone_id=1,
            home_quadrant_id=1,
        )

        req_time = datetime(2024, 1, 2, 8, 30)  # Rested

        # Low-demand residential destination: zone 2 (Las Colinas)
        rejections_low_demand = 0
        trials = 100
        for seed in range(trials):
            trial_rng = np.random.Generator(np.random.PCG64(seed))
            accepted, reason = agent.evaluate_trip_offer(
                pickup_km=4.8,  # > 4.0 km
                trip_dist_km=6.0,
                trip_dur_min=18.0,
                fare=140.0,
                is_route_overflow=False,
                dest_zone_id=2,  # Not in {1, 4, 6, 9, 11}
                req_time=req_time,
                rng=trial_rng,
            )
            if not accepted and "vacío" in reason:
                rejections_low_demand += 1

        self.assertGreater(rejections_low_demand / trials, 0.60)

        # High-demand commercial hub destination: zone 9 (Metrocentro)
        rejections_high_demand = 0
        for seed in range(trials):
            trial_rng = np.random.Generator(np.random.PCG64(seed))
            accepted, reason = agent.evaluate_trip_offer(
                pickup_km=4.8,
                trip_dist_km=6.0,
                trip_dur_min=18.0,
                fare=140.0,
                is_route_overflow=False,
                dest_zone_id=9,  # High demand hub
                req_time=req_time,
                rng=trial_rng,
            )
            if not accepted and "vacío" in reason:
                rejections_high_demand += 1

        self.assertEqual(rejections_high_demand, 0)

    def test_acceptance_rate_updates_dynamically(self):
        """Verify that driver acceptance rate updates correctly based on offer history."""
        agent = DriverAgent(
            driver_id=1,
            driver_model=self.driver_model_1,
            vehicle_model=self.moto_vehicle,
            current_node=100,
            available_at=datetime.min,
            status="activo",
            acceptance_rate_pct=90.0,
            home_zone_id=1,
            home_quadrant_id=1,
        )

        agent.record_offer_result(accepted=True)
        agent.record_offer_result(accepted=True)
        agent.record_offer_result(accepted=False)
        agent.record_offer_result(accepted=True)

        self.assertEqual(agent.total_offers, 4)
        self.assertEqual(agent.total_rejections, 1)
        self.assertEqual(agent.acceptance_rate_pct, 75.0)

    def test_compute_driver_heterogeneity_and_churn_metrics(self):
        """Verify that compute_driver_heterogeneity_and_churn_metrics yields valid statistics."""
        df_trips = pd.DataFrame([
            {"trip_id": 1, "driver_id": 1},
            {"trip_id": 2, "driver_id": 2},
            {"trip_id": 3, "driver_id": 3},
        ])
        df_cancellations = pd.DataFrame([
            {"cancellation_id": 1, "trip_id": 1, "cancelled_by": "conductor", "cancellation_reason": "Riesgo de inundación / cauce desbordado (rechazo conductor)"},
            {"cancellation_id": 2, "trip_id": 2, "cancelled_by": "conductor", "cancellation_reason": "Conductor fatigado / fin de turno"},
            {"cancellation_id": 3, "trip_id": 3, "cancelled_by": "conductor", "cancellation_reason": "Desplazamiento en vacío excesivo (>4km a zona baja demanda)"},
        ])
        df_drivers = pd.DataFrame([
            {"driver_id": 1, "acceptance_rate_pct": 70.0, "average_rating": 4.5},
            {"driver_id": 2, "acceptance_rate_pct": 85.0, "average_rating": 4.8},
            {"driver_id": 3, "acceptance_rate_pct": 92.0, "average_rating": 4.9},
        ])
        df_vehicles = pd.DataFrame([
            {"vehicle_id": 1, "driver_id": 1, "service_type": "movigo_moto"},
            {"vehicle_id": 2, "driver_id": 2, "service_type": "movigo_estandar"},
            {"vehicle_id": 3, "driver_id": 3, "service_type": "movigo_comfort"},
        ])

        metrics = compute_driver_heterogeneity_and_churn_metrics(
            df_trips, df_cancellations, df_drivers, df_vehicles
        )

        self.assertEqual(metrics["total_rechazos_conductor"], 3)
        self.assertEqual(metrics["conductores_riesgo_desercion_churn"], 1)
        self.assertAlmostEqual(metrics["tasa_aceptacion_promedio_flota_pct"], 82.33, delta=0.01)
        self.assertEqual(metrics["distribucion_motivos_rechazo_conteo"]["riesgo_cauce_desbordado"], 1)
        self.assertEqual(metrics["distribucion_motivos_rechazo_conteo"]["fatiga_fin_turno"], 1)
        self.assertEqual(metrics["distribucion_motivos_rechazo_conteo"]["desplazamiento_vacio"], 1)


if __name__ == "__main__":
    unittest.main()
