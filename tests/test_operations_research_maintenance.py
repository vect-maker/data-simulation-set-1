"""Unit tests for Prioridad 4: Physical Workshops, M/M/c Multi-Bay Queueing System,
Vehicle Fuel Tanks & Refueling Pitstops (Operations Research Track).
"""

from datetime import datetime, timedelta
import unittest
import pandas as pd

from movigo_sim.engine.entities import FuelTank, DriverAgent
from movigo_sim.engine.world import MaintenanceWorkshop, WorldEnvironment
from movigo_sim.models import Driver, Quadrant, UrbanZone, Vehicle
from movigo_sim.analytics import compute_operations_research_maintenance_and_queue_metrics


class TestOperationsResearchMaintenance(unittest.TestCase):
    """Test suite validating OOP fuel tanks, multi-server workshop queues, and spatial assignment."""

    def test_fuel_tank_oop_mechanics(self):
        """Verify that FuelTank models burning, reserve thresholds, and refill operations."""
        tank = FuelTank(capacity_liters=45.0, current_liters=40.0, low_fuel_threshold_pct=0.15)
        self.assertAlmostEqual(tank.level_pct, 88.89, delta=0.01)
        self.assertFalse(tank.needs_refueling)

        burned = tank.burn(34.0)
        self.assertEqual(burned, 34.0)
        self.assertEqual(tank.current_liters, 6.0)
        self.assertAlmostEqual(tank.level_pct, 13.33, delta=0.01)
        self.assertTrue(tank.needs_refueling)

        pumped = tank.refill()
        self.assertEqual(pumped, 39.0)
        self.assertEqual(tank.current_liters, 45.0)
        self.assertEqual(tank.refueling_count, 1)
        self.assertEqual(tank.total_liters_refilled, 39.0)
        self.assertFalse(tank.needs_refueling)

    def test_workshop_mmc_multi_server_queue(self):
        """Verify that MaintenanceWorkshop enforces M/M/c bay capacity and calculates FIFO queue delay."""
        workshop = MaintenanceWorkshop(
            workshop_id=1,
            name="Centro Automotriz Carretera Norte",
            zone_id=8,
            quadrant_id=62,
            node_id=10,
            latitude=12.152,
            longitude=-86.218,
            capacity_bays=3,
        )

        t0 = datetime(2024, 1, 2, 8, 0)
        # Vehicles 1, 2, 3 arrive at 8:00 AM for 4-hour repairs
        for vid in [101, 102, 103]:
            start_t, finish_t, wait_min = workshop.admit_vehicle(vid, t0, service_duration_hours=4.0)
            self.assertEqual(start_t, t0)
            self.assertEqual(finish_t, t0 + timedelta(hours=4))
            self.assertEqual(wait_min, 0.0)

        self.assertEqual(len(workshop.active_bays_busy_until), 3)

        # Vehicle 4 arrives at 9:00 AM (all 3 bays occupied until 12:00 PM)
        t_arr_4 = datetime(2024, 1, 2, 9, 0)
        start_4, finish_4, wait_min_4 = workshop.admit_vehicle(104, t_arr_4, service_duration_hours=2.0)
        self.assertEqual(start_4, datetime(2024, 1, 2, 12, 0))
        self.assertEqual(finish_4, datetime(2024, 1, 2, 14, 0))
        self.assertEqual(wait_min_4, 180.0)  # 3 hours wait in queue

        self.assertEqual(workshop.total_vehicles_serviced, 4)
        self.assertEqual(workshop.total_queue_wait_minutes, 180.0)

    def test_world_workshops_locations_and_spatial_proximity(self):
        """Verify that WorldEnvironment initializes 3 official workshops and routes to closest."""
        from movigo_sim.engine.simulator import load_movigo_quadrants
        from movigo_sim.spatial import CANONICAL_URBAN_ZONES
        quads = load_movigo_quadrants()
        zones = [UrbanZone(**z) for z in CANONICAL_URBAN_ZONES]
        world = WorldEnvironment(quadrants=quads, zones=zones, street_network={})
        self.assertEqual(len(world.workshops), 3)

        # A vehicle in Carretera Norte (12.153, -86.215) should pick Carretera Norte workshop
        w_north = world.find_closest_workshop(12.153, -86.215)
        self.assertIn("Carretera Norte", w_north.name)

        # A vehicle in Las Colinas / Masaya (12.100, -86.240) should pick Masaya workshop
        w_south = world.find_closest_workshop(12.100, -86.240)
        self.assertIn("Masaya", w_south.name)

        # A vehicle in Bolonia (12.130, -86.280) should pick Bolonia workshop
        w_central = world.find_closest_workshop(12.130, -86.280)
        self.assertIn("Bolonia", w_central.name)

    def test_driver_autonomous_refuel_pitstop(self):
        """Verify that DriverAgent performs autonomous pitstop when fuel drops below 15%."""
        d_model = Driver(driver_id=1, name="Juan Perez", average_rating=4.9, acceptance_rate_pct=95.0, status="activo")
        v_model = Vehicle(vehicle_id=1, driver_id=1, service_type="movigo_estandar", vehicle_model="Toyota Yaris", vehicle_year=2021, license_plate="M-101")
        agent = DriverAgent(
            driver_id=1,
            driver_model=d_model,
            vehicle_model=v_model,
            current_node=100,
            available_at=datetime(2024, 1, 2, 10, 0),
            status="activo",
            acceptance_rate_pct=95.0,
            home_zone_id=1,
            home_quadrant_id=1,
        )

        self.assertIsNotNone(agent.fuel_tank)
        agent.fuel_tank.current_liters = 5.0  # 5.0 / 45.0 = 11.1% (< 15%)
        self.assertTrue(agent.fuel_tank.needs_refueling)

        t_now = datetime(2024, 1, 2, 11, 0)
        pumped = agent.refuel_pitstop(t_now, pitstop_minutes=15.0)
        self.assertEqual(pumped, 40.0)
        self.assertEqual(agent.fuel_tank.current_liters, 45.0)
        self.assertEqual(agent.available_at, t_now + timedelta(minutes=15.0))
        self.assertFalse(agent.fuel_tank.needs_refueling)

    def test_operations_research_metrics_calculation(self):
        """Verify that compute_operations_research_maintenance_and_queue_metrics computes utilization and wait stats."""
        df_maintenance = pd.DataFrame([
            {"maintenance_id": 1, "workshop_name": "Taller Central MoviGo Bolonia", "maintenance_type": "preventivo", "cost_nio": 3200.0, "downtime_hours": 4.5},
            {"maintenance_id": 2, "workshop_name": "Taller Central MoviGo Bolonia", "maintenance_type": "correctivo", "cost_nio": 8500.0, "downtime_hours": 12.0},
            {"maintenance_id": 3, "workshop_name": "AutoServicio Masaya MoviGo", "maintenance_type": "preventivo", "cost_nio": 2800.0, "downtime_hours": 3.8},
        ])
        df_vehicles = pd.DataFrame([{"vehicle_id": 1}, {"vehicle_id": 2}])

        w1 = MaintenanceWorkshop(1, "Taller Central MoviGo Bolonia", 6, 49, 1, 12.13, -86.28, capacity_bays=4)
        w1.total_vehicles_serviced = 2
        w1.total_queue_wait_minutes = 45.0
        w1.total_service_hours = 16.5

        metrics = compute_operations_research_maintenance_and_queue_metrics(
            df_maintenance=df_maintenance,
            df_vehicles=df_vehicles,
            workshops=[w1],
            total_simulated_days=3,
        )

        self.assertEqual(metrics["costo_total_mantenimiento_flota_nio"], 14500.0)
        self.assertEqual(metrics["horas_totales_inactividad_flota"], 20.3)
        self.assertIn("Taller Central MoviGo Bolonia", metrics["colas_multicanal_mmc_talleres"])
        taller_info = metrics["colas_multicanal_mmc_talleres"]["Taller Central MoviGo Bolonia"]
        self.assertEqual(taller_info["vehiculos_atendidos"], 2)
        self.assertEqual(taller_info["tiempo_medio_espera_cola_min"], 22.5)
        self.assertGreater(taller_info["factor_utilizacion_bahias_rho"], 0.0)


if __name__ == "__main__":
    unittest.main()
