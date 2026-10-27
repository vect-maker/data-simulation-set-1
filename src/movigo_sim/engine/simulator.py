"""Simulation coordinator and event engine for MoviGo ride-hailing simulation.

Orchestrates:
- Autonomous Driver and Rider entities
- WorldEnvironment road network & traffic physics
- MoviGoPlatform dispatch & surge pricing
- SimulationRecorder 3NF transactional event sinks
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta, time
from time import perf_counter
from typing import Any
import numpy as np
import pandas as pd

from movigo_sim.config import (
    DETERMINISTIC_SEEDS_DIR,
    LLM_SEEDS_DIR,
    SIMULATION_SEED,
    BASE_PER_KM_NIO,
    BASE_PER_MINUTE_NIO,
)
from movigo_sim.models import (
    Quadrant,
    UrbanZone,
    User,
    Driver,
    Vehicle,
    Trip,
    TripPayment,
    TripRating,
    TripCancellation,
    DriverTelemetry,
    IncentiveCampaign,
    VehicleMaintenance,
    DrainageChannel,
    QuadrantWeather,
)
from movigo_sim.engine.entities import DriverAgent, RiderAgent, RiderPersona
from movigo_sim.engine.world import (
    WorldEnvironment,
    get_gravity_regime_name,
    haversine_km,
)
from movigo_sim.engine.platform import (
    MoviGoPlatform,
    STRATUM_PAYMENT_PROBABILITIES,
    PAYMENT_METHODS,
)
from movigo_sim.engine.recorder import SimulationRecorder

logger = logging.getLogger(__name__)


def load_movigo_quadrants() -> list[Quadrant]:
    """Load the 92 Managua geographical square quadrants from deterministic JSON seed fixture."""
    with open(DETERMINISTIC_SEEDS_DIR / "quadrants.json", encoding="utf-8") as f:
        return [Quadrant(**c) for c in json.load(f)]


def load_movigo_vehicles() -> list[Vehicle]:
    """Load the 150 driver vehicles from deterministic JSON seed fixture."""
    with open(DETERMINISTIC_SEEDS_DIR / "vehicles.json", encoding="utf-8") as f:
        return [Vehicle(**v) for v in json.load(f)]


def load_movigo_drainage_channels() -> list[DrainageChannel]:
    """Load the 12 Managua drainage channels (cauces) from deterministic JSON seed fixture or catalog."""
    path = DETERMINISTIC_SEEDS_DIR / "drainage_channels.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return [DrainageChannel(**c) for c in json.load(f)]
    from movigo_sim.spatial import build_deterministic_drainage_channels
    return [DrainageChannel(**c) for c in build_deterministic_drainage_channels()]


def load_movigo_seed_catalogs() -> tuple[
    list[UrbanZone],
    list[User],
    list[Driver],
    list[IncentiveCampaign],
    dict[str, Any],
]:
    """Load dimensional seed catalogs from deterministic/ and llm/ JSON fixtures."""
    with open(DETERMINISTIC_SEEDS_DIR / "urban_zones.json", encoding="utf-8") as f:
        zones = [UrbanZone(**z) for z in json.load(f)]

    with open(DETERMINISTIC_SEEDS_DIR / "users.json", encoding="utf-8") as f:
        users = [User(**u) for u in json.load(f)]

    with open(DETERMINISTIC_SEEDS_DIR / "drivers.json", encoding="utf-8") as f:
        drivers = [Driver(**c) for c in json.load(f)]

    with open(LLM_SEEDS_DIR / "incentive_campaigns.json", encoding="utf-8") as f:
        campaigns = [IncentiveCampaign(**cmp) for cmp in json.load(f)]

    with open(LLM_SEEDS_DIR / "semantic_templates.json", encoding="utf-8") as f:
        templates = json.load(f)

    return zones, users, drivers, campaigns, templates


def load_managua_street_network() -> dict[str, Any]:
    """Load cached OpenStreetMap drivable street segments and flood-hotspot flags from deterministic/."""
    network_path = DETERMINISTIC_SEEDS_DIR / "managua_street_network.json"
    if network_path.exists():
        with open(network_path, encoding="utf-8") as f:
            return json.load(f)
    return {"zones": {}, "arterials": [], "zone_flood_flags": {}, "quadrant_streets": {}, "quadrant_flood_flags": {}}


class MoviGoSimulationEngine:
    """Core numerical simulation engine for MoviGo ride-hailing facts in 3NF OLTP form."""

    def __init__(self, random_seed: int = SIMULATION_SEED):
        self.random_seed = random_seed
        self.rng = np.random.default_rng(self.random_seed)
        np.random.seed(self.random_seed)

        self.quadrants = load_movigo_quadrants()
        (
            self.zones,
            self.users,
            self.drivers,
            self.campaigns,
            self.templates,
        ) = load_movigo_seed_catalogs()
        self.vehicles = load_movigo_vehicles()
        self.street_network = load_managua_street_network()

        # Initialize Environment and Platform
        self.world = WorldEnvironment(self.quadrants, self.zones, self.street_network)
        self.platform = MoviGoPlatform(self.campaigns, self.templates)

        # Backward compatibility properties
        self.quadrants_map = self.world.quadrants_map
        self.quadrants_centers = self.world.quadrants_centers
        self.zones_map = self.world.zones_map
        self.drivers_map = {c.driver_id: c for c in self.drivers}
        self.operational_drivers = [c for c in self.drivers if c.status != "inactivo"]
        self.vehicles_by_driver = {v.driver_id: v for v in self.vehicles}

        # Initialize Driver Agents with 3 formal shifts and rotating rest days
        self.driver_agents: list[DriverAgent] = []
        for idx, d in enumerate(self.operational_drivers):
            home_zid = (d.driver_id % len(self.zones)) + 1
            home_quads = self.world.zone_quadrants.get(home_zid, self.quadrants)
            hq = home_quads[d.driver_id % len(home_quads)].quadrant_id
            h_idx = self.world.qid_to_hub_idx.get(hq, 0)
            initial_node = (
                self.world.hub_node_indices[h_idx]
                if self.world.hub_node_indices
                else 0
            )
            v_model = self.vehicles_by_driver.get(d.driver_id, self.vehicles[0])

            # Demand-proportional formal shifts: 65 Matutino, 65 Vespertino, 20 Nocturno
            if idx < 65:
                shift_name = "matutino"
                s_start, s_end = 6, 14
                mb_start, mb_end = time(10, 40), time(11, 20)
            elif idx < 130:
                shift_name = "vespertino"
                s_start, s_end = 14, 22
                mb_start, mb_end = time(17, 40), time(18, 20)
            else:
                shift_name = "nocturno"
                s_start, s_end = 22, 6
                mb_start, mb_end = time(2, 0), time(2, 40)

            weekly_rest = d.driver_id % 7
            base_odo = round(18000.0 + (2024 - v_model.vehicle_year) * 8500.0 + ((d.driver_id * 137) % 3000), 2)
            if d.driver_id % 20 == 0:
                init_service_km = round(4975.0 + float(d.driver_id % 15), 2)
            else:
                init_service_km = round(float(1000.0 + ((d.driver_id * 739) % 3600)), 2)

            self.driver_agents.append(
                DriverAgent(
                    driver_id=d.driver_id,
                    driver_model=d,
                    vehicle_model=v_model,
                    current_node=initial_node,
                    available_at=datetime.min,
                    status=d.status,
                    acceptance_rate_pct=d.acceptance_rate_pct,
                    home_zone_id=home_zid,
                    home_quadrant_id=hq,
                    shift_name=shift_name,
                    shift_start_hour=s_start,
                    shift_end_hour=s_end,
                    meal_break_start=mb_start,
                    meal_break_end=mb_end,
                    weekly_rest_dow=weekly_rest,
                    odometer_km=base_odo,
                    km_since_service=init_service_km,
                )
            )

        # Initialize Rider Agents with 6 diverse urban archetypes and persistent anchor coordinates
        self.rider_agents: list[RiderAgent] = []
        for u in self.users:
            arch_id = u.user_id % 6
            if arch_id == 0:
                archetype = "oficinista"
                home_z_opts = [2, 3, 7, 8]
                anchor_z_opts = [1, 9, 4]
                commute_days = [0, 1, 2, 3, 4]
                out_h, ret_h = [7, 8], [17, 18]
                routine_p = 0.80
            elif arch_id == 1:
                archetype = "estudiante_universitario"
                home_z_opts = [5, 7, 8, 10]
                anchor_z_opts = [9, 1]
                commute_days = [0, 1, 2, 3, 4]
                out_h, ret_h = [6, 7, 12], [13, 17, 21]
                routine_p = 0.75
            elif arch_id == 2:
                archetype = "comerciante_mercado"
                home_z_opts = [7, 8, 10]
                anchor_z_opts = [11, 12]
                commute_days = [0, 1, 2, 3, 4, 5]
                out_h, ret_h = [4, 5, 6], [14, 15]
                routine_p = 0.85
            elif arch_id == 3:
                archetype = "trabajador_salud_servicios"
                home_z_opts = [2, 3, 7, 8]
                anchor_z_opts = [6, 5]
                commute_days = [0, 1, 2, 3, 4, 5]
                out_h, ret_h = [6, 14, 22], [14, 22, 6]
                routine_p = 0.70
            elif arch_id == 4:
                archetype = "compras_hogar"
                home_z_opts = [2, 5, 7, 8]
                anchor_z_opts = [9, 10, 4]
                commute_days = [1, 3, 5]
                out_h, ret_h = [10, 11, 14], [13, 16]
                routine_p = 0.65
            else:
                archetype = "vida_nocturna_ocio"
                home_z_opts = [1, 2, 3, 5, 7, 8]
                anchor_z_opts = [4, 3, 1]
                commute_days = [4, 5]
                out_h, ret_h = [19, 20, 21], [0, 1, 2]
                routine_p = 0.75

            hz = home_z_opts[u.user_id % len(home_z_opts)]
            az = anchor_z_opts[(u.user_id * 3) % len(anchor_z_opts)]
            if hz == az:
                az = (az % len(self.world.zones)) + 1

            home_zone_obj = self.world.zones_map.get(hz, self.world.zones[0])
            anchor_zone_obj = self.world.zones_map.get(az, self.world.zones[-1])

            h_lat, h_lon, hq_id, _, h_hub = self.world.sample_street_coordinate(home_zone_obj, self.rng)
            a_lat, a_lon, aq_id, _, a_hub = self.world.sample_street_coordinate(anchor_zone_obj, self.rng)

            persona = RiderPersona(
                archetype=archetype,
                home_zone_id=home_zone_obj.zone_id,
                home_quadrant_id=hq_id,
                home_node=h_hub,
                home_lat=h_lat,
                home_lon=h_lon,
                anchor_zone_id=anchor_zone_obj.zone_id,
                anchor_quadrant_id=aq_id,
                anchor_node=a_hub,
                anchor_lat=a_lat,
                anchor_lon=a_lon,
                commute_days=commute_days,
                outbound_hours=out_h,
                return_hours=ret_h,
                routine_probability=routine_p,
            )
            self.rider_agents.append(
                RiderAgent(
                    user_id=u.user_id,
                    user_model=u,
                    registration_date=u.registration_date,
                    preferred_payment_method=u.preferred_payment_method,
                    persona=persona,
                )
            )

        # Initialize Rider Agents & Precompute propensity weights
        self.user_reg_dates = np.array([u.registration_date for u in self.users], dtype=object)
        ranks = np.arange(1, len(self.users) + 1, dtype=float)
        zipf_weights = 1.0 / (ranks ** 0.75)
        perm_rng = np.random.default_rng(self.random_seed + 303)
        self.user_base_weights = perm_rng.permutation(zipf_weights)
        user_method_indices = np.array(
            [PAYMENT_METHODS.index(u.preferred_payment_method) for u in self.users],
            dtype=int,
        )
        self.user_stratum_weights: dict[str, np.ndarray] = {}
        for stratum, probs in STRATUM_PAYMENT_PROBABILITIES.items():
            probs_arr = np.array(probs, dtype=float)
            self.user_stratum_weights[stratum] = self.user_base_weights * probs_arr[user_method_indices]

        self.audit_logs: list[dict[str, Any]] = []

    def sample_origin_destination_zones(self, hour: int, dow: int) -> tuple[UrbanZone, UrbanZone]:
        """Sample (origin_zone, destination_zone) from WorldEnvironment."""
        return self.world.sample_origin_destination_zones(hour, dow, self.rng)

    def sample_street_coordinate(
        self, zone: UrbanZone
    ) -> tuple[float, float, int, bool, int]:
        """Sample a GPS coordinate strictly on a drivable street within one of the urban zone's square quadrants."""
        return self.world.sample_street_coordinate(zone, self.rng)

    def snap_to_nearest_street_and_quadrant(
        self, target_lat: float, target_lon: float, fallback_zone: UrbanZone
    ) -> tuple[float, float, int, int]:
        """Snap coordinate onto nearest street in active quadrant."""
        return self.world.snap_to_nearest_street_and_quadrant(target_lat, target_lon, fallback_zone, self.rng)

    def get_osm_route(
        self,
        origin_node_idx: int,
        dest_node_idx: int,
        origin_qid: int,
        dest_qid: int,
        is_flood_aware: bool = False,
        is_traffic_aware: bool = False,
        hour: Any | None = None,
        is_perturbed: bool = False,
    ) -> tuple[list[int], float]:
        """Reconstruct continuous sequence of real OSM nodes."""
        return self.world.get_osm_route(
            origin_node_idx,
            dest_node_idx,
            origin_qid,
            dest_qid,
            is_flood_aware=is_flood_aware,
            is_traffic_aware=is_traffic_aware,
            hour=hour,
            is_perturbed=is_perturbed,
            rng=self.rng,
        )

    def calculate_daily_demand(self, precip_mm: float, dow: int) -> int:
        """Daily ride requests from Platform."""
        return self.platform.calculate_daily_demand(precip_mm, dow, self.rng)

    def sample_trip_time(self, curr_date: date) -> datetime:
        """Sample request timestamp via NHPP."""
        return self.platform.sample_trip_time(curr_date, self.rng)

    def simulate_supply_demand_and_surge(
        self,
        origin_zone: UrbanZone,
        hourly_precip_mm: float,
        runoff_mm: float,
        flooded_roads: bool,
        hour: int,
        dow: int,
        curr_date: date | None = None,
    ) -> tuple[int, int, float]:
        """Simulate origin zone active demand (Dt), available drivers (St), and equilibrium surge multiplier m*."""
        return self.platform.simulate_supply_demand_and_surge(
            origin_zone,
            hourly_precip_mm,
            runoff_mm,
            flooded_roads,
            hour,
            dow,
            self.world,
            self.rng,
            curr_date=curr_date,
        )

    def calculate_surge_multiplier(self, precip_mm: float, hour: int) -> float:
        """Helper to calculate dynamic surge multiplier."""
        _, _, m = self.simulate_supply_demand_and_surge(self.zones[0], precip_mm, precip_mm, precip_mm > 12.0, hour, 2)
        return m

    def sample_payment_method_for_stratum(
        self,
        stratum: str,
        preferred_method: str | None = None,
        user_weight: float = 0.75,
    ) -> str:
        """Sample payment method coupling user preference with origin zone stratum (Chi-Square guarantee)."""
        return self.platform.sample_payment_method_for_stratum(
            stratum, preferred_method, self.rng, user_weight=user_weight
        )

    def estimate_distance_and_duration(
        self,
        lat_o: float,
        lon_o: float,
        lat_d: float,
        lon_d: float,
        congestion_idx: float,
        effective_water_mm: float = 0.0,
        flood_affected_route: bool = False,
        raw_route_km: float | None = None,
        is_suboptimal: bool = False,
        is_cauce_overflow: bool = False,
    ) -> tuple[float, float, bool]:
        """Calculate road distance and duration from real OpenStreetMap route trajectory with flood/traffic physics."""
        return self.world.estimate_distance_and_duration(
            lat_o,
            lon_o,
            lat_d,
            lon_d,
            congestion_idx,
            self.rng,
            effective_water_mm=effective_water_mm,
            flood_affected_route=flood_affected_route,
            raw_route_km=raw_route_km,
            is_suboptimal=is_suboptimal,
            is_cauce_overflow=is_cauce_overflow,
        )

    def evaluate_cancellation(
        self,
        stratum: str,
        payment_method: str,
        surge: float,
        final_fare: float,
        wait_min: float,
        effective_water_mm: float,
        flood_affected: bool,
        congestion_idx: float,
        hour: int,
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate trip cancellation via micro-behavioral logistic model and assign structured reason."""
        return self.platform.evaluate_cancellation(
            stratum=stratum,
            payment_method=payment_method,
            surge=surge,
            final_fare=final_fare,
            wait_min=wait_min,
            effective_water_mm=effective_water_mm,
            flood_affected=flood_affected,
            congestion_idx=congestion_idx,
            hour=hour,
            rng=self.rng,
        )

    def run_simulation(
        self,
        weather_df: pd.DataFrame,
        recorder: SimulationRecorder | None = None,
        progress_callback: Any = None,
    ) -> tuple[
        list[Trip],
        list[TripPayment],
        list[TripRating],
        list[TripCancellation],
        list[DriverTelemetry],
        list[VehicleMaintenance],
    ]:
        """Run full year MoviGo simulation emitting 3NF OLTP transactional tables with Gravity OD & non-overlapping dispatch."""
        self.rng = np.random.default_rng(self.random_seed)
        logger.info(f"Starting MoviGo 3NF simulation across {len(weather_df)} days (seed={self.random_seed})...")

        hourly_matrices: dict[str, Any] | None = weather_df.attrs.get("hourly_matrices")
        date_hour_to_idx: dict[tuple[date, int], int] = (
            hourly_matrices["date_hour_to_idx"] if hourly_matrices else {}
        )

        if recorder is None:
            recorder = SimulationRecorder()

        # Reset driver agent state for fresh simulation
        for agent in self.driver_agents:
            h_idx = self.world.qid_to_hub_idx.get(agent.home_quadrant_id, 0)
            initial_node = (
                self.world.hub_node_indices[h_idx]
                if self.world.hub_node_indices
                else 0
            )
            agent.current_node = initial_node
            agent.available_at = datetime.min
            agent.maintenance_until = datetime.min
            if agent.driver_id % 20 == 0:
                agent.km_since_service = round(4975.0 + float(agent.driver_id % 15), 2)
            else:
                agent.km_since_service = round(float(1000.0 + ((agent.driver_id * 739) % 3600)), 2)
            agent.fuel_tank.current_liters = round(agent.fuel_tank.capacity_liters * 0.85, 2)
            agent.shift_trips_completed = 0
            agent.shift_minutes_worked = 0.0
            agent.traffic_stress_accumulated = 0.0
            agent.odometer_km = round(18000.0 + (2024 - agent.vehicle_model.vehicle_year) * 8500.0 + ((agent.driver_id * 137) % 3000), 2)
            agent.cumulative_fuel_liters = 0.0
            agent.flood_exposure_count = 0

        # Reset workshop queues for deterministic replay
        for ws in self.world.workshops:
            ws.active_bays_busy_until.clear()
            ws.total_vehicles_serviced = 0
            ws.total_queue_wait_minutes = 0.0
            ws.total_service_hours = 0.0

        sim_total_days = len(weather_df)
        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
            day_t0 = perf_counter()
            trips_before = len(recorder.trips)
            cancels_before = len(recorder.cancellations)
            telemetry_before = len(recorder.telemetry)

            curr_date: date = row["date"]
            daily_precip_mm: float = float(row["precipitation_mm"])
            daily_cong_idx: float = float(row["congestion_index"])
            dow: int = curr_date.weekday()

            daily_target = self.calculate_daily_demand(daily_precip_mm, dow)
            driver_meal_logged: set[int] = set()

            # Filter users registered on or before curr_date
            eligible_mask = self.user_reg_dates <= curr_date
            eligible_users = [u for u, m in zip(self.users, eligible_mask) if m]
            eligible_stratum_probs: dict[str, np.ndarray] = {}
            for stratum, w_arr in self.user_stratum_weights.items():
                ew = w_arr[eligible_mask].copy()
                ew /= ew.sum()
                eligible_stratum_probs[stratum] = ew

            # Sample and sort request timestamps chronologically within the day
            req_times = sorted(self.sample_trip_time(curr_date) for _ in range(daily_target))

            for req_time in req_times:
                self._dispatch_trip_request(
                    req_time=req_time,
                    recorder=recorder,
                    driver_meal_logged=driver_meal_logged,
                    daily_precip_mm=daily_precip_mm,
                    daily_cong_idx=daily_cong_idx,
                    hourly_matrices=hourly_matrices,
                    date_hour_to_idx=date_hour_to_idx,
                    eligible_users=eligible_users,
                    eligible_stratum_probs=eligible_stratum_probs,
                )

            day_duration = perf_counter() - day_t0
            trips_day = len(recorder.trips) - trips_before
            cancels_day = len(recorder.cancellations) - cancels_before
            telemetry_day = len(recorder.telemetry) - telemetry_before
            day_name = curr_date.strftime("%A")

            audit_entry = recorder.record_audit_entry(
                simulation_date=str(curr_date),
                day_name=day_name,
                is_weekend=(dow >= 5),
                weather_precip_mm=daily_precip_mm,
                congestion_index=daily_cong_idx,
                daily_demand_target=daily_target,
                trips_dispatched=len(req_times),
                trips_completed=trips_day,
                trips_canceled=cancels_day,
                telemetry_records=telemetry_day,
                step_duration_seconds=day_duration,
            )

            logger.info(
                f"[MoviGo Sim] Día {day_idx + 1:3d}/{sim_total_days} | {curr_date} ({day_name:9s}) | "
                f"Lluvia: {daily_precip_mm:5.1f}mm | Congestión: {daily_cong_idx:.2f} | "
                f"Viajes: {trips_day:3d} ok, {cancels_day:2d} canc | Acumulado: {len(recorder.trips):6d} | {day_duration:5.2f}s"
            )

            if progress_callback:
                try:
                    progress_callback(audit_entry, day_idx + 1, sim_total_days)
                except Exception as cb_err:
                    logger.debug("Progress callback exception: %s", cb_err)

        self.audit_logs = recorder.get_audit_logs()
        trips, payments, ratings, cancellations, telemetry, maintenance = recorder.get_results()
        self.maintenance_records = maintenance
        logger.info(
            f"MoviGo simulation completed! Produced {len(trips)} trips, {len(payments)} payments, "
            f"{len(ratings)} ratings, {len(cancellations)} cancellations, {len(telemetry)} telemetry pings, "
            f"and {len(maintenance)} maintenance services across {len(self.audit_logs)} simulated days."
        )
        return trips, payments, ratings, cancellations, telemetry, maintenance

    def _dispatch_trip_request(
        self,
        req_time: datetime,
        recorder: SimulationRecorder,
        driver_meal_logged: set[int],
        daily_precip_mm: float = 0.0,
        daily_cong_idx: float = 1.0,
        hourly_matrices: dict[str, Any] | None = None,
        date_hour_to_idx: dict[tuple[date, int], int] | None = None,
        eligible_users: list[User] | None = None,
        eligible_stratum_probs: dict[str, np.ndarray] | None = None,
    ) -> None:
        if eligible_users is None:
            eligible_users = self.users
        if eligible_stratum_probs is None:
            eligible_stratum_probs = self.user_stratum_weights
        curr_date = req_time.date()
        dow = req_time.weekday()
        hour = req_time.hour

        # Mandatory meal break rest logging for on-duty drivers in their scheduled meal window
        for agent in self.driver_agents:
            if (
                agent.driver_id not in driver_meal_logged
                and agent.is_on_duty(req_time)
                and agent.is_in_meal_break(req_time)
                and agent.is_available_at(req_time)
            ):
                driver_meal_logged.add(agent.driver_id)
                c_lat = float(self.world.node_coords[agent.current_node, 0])
                c_lon = float(self.world.node_coords[agent.current_node, 1])
                c_qid = (
                    int(self.world.node_quadrants[agent.current_node])
                    if len(self.world.node_quadrants) > agent.current_node
                    else agent.home_quadrant_id
                )
                recorder.record_telemetry(
                    driver_id=agent.driver_id,
                    trip_id=None,
                    quadrant_id=c_qid,
                    recorded_at=req_time,
                    latitude=c_lat,
                    longitude=c_lon,
                    speed_kmh=0.0,
                    availability_status="descanso",
                )

        origin_zone, destination_zone = self.sample_origin_destination_zones(hour, dow)

        u_probs = eligible_stratum_probs.get(origin_zone.socioeconomic_stratum)
        if u_probs is not None:
            u_idx = int(self.rng.choice(len(eligible_users), p=u_probs))
        else:
            u_idx = int(self.rng.integers(0, len(eligible_users)))
        user = eligible_users[u_idx]

        user_agent = self.rider_agents[user.user_id - 1]
        persona = user_agent.persona

        # Dual-mode demand: 70% recurrent persona anchor commutes vs 30% spontaneous gravity trips
        is_commute = False
        if persona is not None and dow in persona.commute_days:
            if hour in persona.outbound_hours and float(self.rng.random()) < persona.routine_probability:
                origin_zone = self.world.zones_map[persona.home_zone_id]
                destination_zone = self.world.zones_map[persona.anchor_zone_id]
                lat_o, lon_o, q_o, node_o = persona.home_lat, persona.home_lon, persona.home_quadrant_id, persona.home_node
                lat_d, lon_d, q_d, node_d = persona.anchor_lat, persona.anchor_lon, persona.anchor_quadrant_id, persona.anchor_node
                flood_street_o = (self.world.quadrants_map[q_o].flood_risk == "critico")
                flood_street_d = (self.world.quadrants_map[q_d].flood_risk == "critico")
                is_commute = True
            elif hour in persona.return_hours and float(self.rng.random()) < persona.routine_probability:
                origin_zone = self.world.zones_map[persona.anchor_zone_id]
                destination_zone = self.world.zones_map[persona.home_zone_id]
                lat_o, lon_o, q_o, node_o = persona.anchor_lat, persona.anchor_lon, persona.anchor_quadrant_id, persona.anchor_node
                lat_d, lon_d, q_d, node_d = persona.home_lat, persona.home_lon, persona.home_quadrant_id, persona.home_node
                flood_street_o = (self.world.quadrants_map[q_o].flood_risk == "critico")
                flood_street_d = (self.world.quadrants_map[q_d].flood_risk == "critico")
                is_commute = True

        if not is_commute:
            # Real OpenStreetMap coordinates inside exact square quadrants
            lat_o, lon_o, q_o, flood_street_o, node_o = self.sample_street_coordinate(origin_zone)
            lat_d, lon_d, q_d, flood_street_d, node_d = self.sample_street_coordinate(destination_zone)

        # Look up localized hourly weather & cauce runoff for Origin and Destination Square Quadrants
        t_idx = date_hour_to_idx.get((curr_date, hour)) if hourly_matrices else None
        if hourly_matrices is not None and t_idx is not None:
            qo_idx = q_o - 1
            qd_idx = q_d - 1
            h_precip_o = float(hourly_matrices["precip"][t_idx, qo_idx])
            h_esc_o = float(hourly_matrices["runoff"][t_idx, qo_idx])
            h_cong_o = float(hourly_matrices["congestion"][t_idx, qo_idx])
            h_aneg_o = bool(hourly_matrices["flooded"][t_idx, qo_idx])

            h_esc_d = float(hourly_matrices["runoff"][t_idx, qd_idx])
            h_cong_d = float(hourly_matrices["congestion"][t_idx, qd_idx])
            h_aneg_d = bool(hourly_matrices["flooded"][t_idx, qd_idx])

            effective_congestion = round(0.60 * h_cong_o + 0.40 * h_cong_d, 2)
            effective_water_mm = max(h_precip_o, h_esc_o, 0.80 * h_esc_d)

            overflow_quads: set[int] = set()
            if "cauce_overflow_quads" in hourly_matrices:
                overflow_quads = set(np.where(hourly_matrices["cauce_overflow_quads"][t_idx])[0] + 1)

            is_cauce_overflow = bool(
                (q_o in overflow_quads) or (q_d in overflow_quads)
            )
            flood_affected = bool(
                h_aneg_o
                or h_aneg_d
                or is_cauce_overflow
                or ((flood_street_o or flood_street_d) and effective_water_mm >= 3.0)
            )
        else:
            h_precip_o = daily_precip_mm / 8.0 if hour in range(13, 21) else 0.0
            h_esc_o = h_precip_o
            effective_congestion = daily_cong_idx
            effective_water_mm = h_precip_o
            overflow_quads = set()
            is_cauce_overflow = False
            flood_affected = bool((flood_street_o or flood_street_d) and daily_precip_mm > 15.0)
            h_aneg_o = flood_affected

        # Ensure dynamic traffic indicators and Dijkstra hub tables are primed for current date-hour
        cache_key = (curr_date, hour)
        if hourly_matrices is not None and t_idx is not None:
            self.world.update_hourly_traffic(cache_key, hourly_matrices["congestion"][t_idx, :])
        else:
            self.world.update_hourly_traffic(cache_key, {q.quadrant_id: daily_cong_idx for q in self.quadrants})

        # 1. Independent supply, demand and dynamic surge multipliers across the 3 categories
        cat_surge_dict = self.platform.simulate_category_surge_multipliers(
            origin_zone, h_precip_o, h_esc_o, h_aneg_o, hour, dow, self.world, self.rng, curr_date=curr_date
        )

        # Precompute baseline fare quotes and expected wait times for mode choice
        flag_drop_fare = round(float(origin_zone.base_flag_drop_fare), 2)
        hav_approx = haversine_km(lat_o, lon_o, lat_d, lon_d)
        est_km = max(0.65, hav_approx * 1.25)
        est_min = max(3.0, (est_km / 26.0) * 60.0)

        cat_fares: dict[str, float] = {}
        cat_etas: dict[str, float] = {}
        for cat in ["movigo_moto", "movigo_estandar", "movigo_comfort"]:
            m_cat = cat_surge_dict[cat][2]
            _, f_cat = self.platform.compute_fare(flag_drop_fare, est_km, est_min, m_cat, service_type=cat)
            cat_fares[cat] = f_cat
            s_cat = cat_surge_dict[cat][1]
            cat_etas[cat] = max(2.5, min(18.0, 35.0 / max(1.0, float(s_cat))))

        # 2. Rider Multinomial Logit Discrete Mode Choice
        chosen_service, choice_probs = self.platform.sample_mode_choice(
            stratum=origin_zone.socioeconomic_stratum,
            effective_water_mm=effective_water_mm,
            category_fares=cat_fares,
            category_etas=cat_etas,
            rng=self.rng,
        )

        d_t, s_t, surge = cat_surge_dict[chosen_service]

        payment_method = self.sample_payment_method_for_stratum(
            origin_zone.socioeconomic_stratum,
            preferred_method=user.preferred_payment_method,
        )

        # Route selection on dense OSM graph (45% habitual, 35% perturbed detour, 20% weather-aware)
        # When cauce overflow occurs, 75% of drivers switch to flood-aware detour routing
        beh_roll = float(self.rng.random())
        if is_cauce_overflow or flood_affected:
            is_fl_aware = (beh_roll < 0.75)
            is_pert = (0.75 <= beh_roll < 0.90)
        else:
            if beh_roll < 0.45:
                is_fl_aware = False
                is_pert = False
            elif beh_roll < 0.80:
                is_fl_aware = False
                is_pert = True
            else:
                is_fl_aware = bool(flood_affected)
                is_pert = False

        ride_nodes, raw_road_km = self.get_osm_route(
            node_o, node_d, q_o, q_d, is_flood_aware=is_fl_aware, is_perturbed=is_pert
        )

        # Check if the chosen path crosses an overflowing cauce quadrant
        if not is_cauce_overflow and overflow_quads:
            is_cauce_overflow = self.world.is_route_affected_by_overflow(ride_nodes, overflow_quads)

        dist_km, dur_min, is_suboptimal = self.estimate_distance_and_duration(
            lat_o, lon_o, lat_d, lon_d, effective_congestion, effective_water_mm, flood_affected,
            raw_route_km=raw_road_km, is_suboptimal=is_pert, is_cauce_overflow=is_cauce_overflow
        )

        # Update driver shifts if new calendar date / shift begins
        for agent in self.driver_agents:
            agent.reset_shift_if_needed(req_time)

        # Stateful on-duty free drivers & greedy proximity dispatch
        free_agents = [
            agent for agent in self.driver_agents
            if agent.is_dispatchable(req_time)
        ]

        # Idle cruising: if a free driver was idle > 45 min, reposition along OSM graph
        for agent in free_agents:
            if agent.idle_minutes(req_time) > 45.0 and self.rng.random() < 0.20:
                regime_name = get_gravity_regime_name(hour, dow)
                top_z = 9 if "rush" in regime_name else (4 if "night" in regime_name else 11)
                top_quads = self.world.zone_quadrants.get(top_z, self.quadrants)
                target_q = top_quads[int(self.rng.integers(0, len(top_quads)))].quadrant_id
                target_node = self.world.hub_node_indices[self.world.qid_to_hub_idx.get(target_q, 0)]
                agent.cruise_to(target_node, req_time)

                if self.rng.random() < 0.35:
                    c_lat = float(self.world.node_coords[target_node, 0])
                    c_lon = float(self.world.node_coords[target_node, 1])
                    c_qid = (
                        int(self.world.node_quadrants[target_node])
                        if len(self.world.node_quadrants) > target_node
                        else target_q
                    )
                    recorder.record_telemetry(
                        driver_id=agent.driver_id,
                        trip_id=None,
                        quadrant_id=c_qid,
                        recorded_at=req_time,
                        latitude=c_lat,
                        longitude=c_lon,
                        speed_kmh=round(float(self.rng.uniform(10.0, 24.0)), 2),
                        availability_status="disponible",
                    )

        driver_agent, extra_wait, reject_reason = self.platform.dispatch_driver(
            free_drivers=free_agents,
            all_operational_drivers=self.driver_agents,
            lat_o=lat_o,
            lon_o=lon_o,
            req_time=req_time,
            world=self.world,
            rng=self.rng,
            service_type=chosen_service,
            trip_dist_km=dist_km,
            trip_dur_min=dur_min,
            fare=100.0,
            is_route_overflow=is_cauce_overflow,
            dest_zone_id=destination_zone.zone_id,
        )

        if reject_reason is not None:
            # Trip was rejected by all candidate drivers (risk aversion, fatigue, or deadhead)
            trip_status = "cancelado_conductor"
            start_time = None
            end_time = None
            tip_amount = 0.0
            payment_status = "anulado"
            cancelled_by = "conductor"
            wait_min = round(float(np.clip(extra_wait, 1.0, 4.0)), 2)
            driver_agent.assign_trip(driver_agent.current_node, req_time + timedelta(minutes=wait_min))

            trip_id = recorder.record_trip(
                user_id=user.user_id,
                driver_id=driver_agent.driver_id,
                origin_quadrant_id=q_o,
                destination_quadrant_id=q_d,
                origin_latitude=lat_o,
                origin_longitude=lon_o,
                destination_latitude=lat_d,
                destination_longitude=lon_d,
                requested_at=req_time,
                started_at=start_time,
                completed_at=end_time,
                distance_km=dist_km,
                duration_minutes=dur_min,
                trip_status=trip_status,
            )
            b_fare, f_fare = self.platform.compute_fare(
                flag_drop_fare, dist_km, dur_min, surge, service_type=driver_agent.vehicle_model.service_type
            )
            recorder.record_payment(
                trip_id=trip_id,
                payment_method=payment_method,
                base_fare=b_fare,
                surge_multiplier=surge,
                tip_amount=tip_amount,
                final_fare=f_fare,
                payment_status=payment_status,
            )
            recorder.record_cancellation(
                trip_id=trip_id,
                cancelled_by=cancelled_by,
                cancellation_reason=reject_reason,
                wait_time_minutes=wait_min,
                origin_active_requests=d_t,
                origin_available_drivers=s_t,
            )
            return

        # Determine if driver uses traffic-aware navigation and dynamic hourly indicators
        is_traffic_aware = driver_agent.decide_traffic_aware_navigation(
            hour=hour,
            effective_congestion=effective_congestion,
            rng=self.rng,
        )

        if is_traffic_aware:
            ride_nodes_ta, raw_road_km_ta = self.get_osm_route(
                node_o,
                node_d,
                q_o,
                q_d,
                is_flood_aware=is_fl_aware,
                is_traffic_aware=True,
                hour=cache_key,
                is_perturbed=is_pert,
            )
            if len(self.world.node_quadrants) > 0 and ride_nodes_ta:
                path_q = self.world.node_quadrants[ride_nodes_ta]
                if hourly_matrices is not None and t_idx is not None:
                    cong_vals = [float(hourly_matrices["congestion"][t_idx, q - 1]) for q in set(path_q) if 1 <= q <= 92]
                    path_cong = float(np.mean(cong_vals)) if cong_vals else effective_congestion
                else:
                    path_cong = effective_congestion
            else:
                path_cong = effective_congestion

            experienced_congestion = min(effective_congestion, round(path_cong, 2))
            dist_km_ta, dur_min_ta, _ = self.estimate_distance_and_duration(
                lat_o,
                lon_o,
                lat_d,
                lon_d,
                experienced_congestion,
                effective_water_mm,
                flood_affected,
                raw_route_km=raw_road_km_ta,
                is_suboptimal=False,
                is_cauce_overflow=is_cauce_overflow,
            )
            time_saved = max(0.0, round(dur_min - dur_min_ta, 2))
            driver_agent.traffic_minutes_saved += time_saved
            driver_agent.trips_rerouted_traffic += 1
            ride_nodes = ride_nodes_ta
            dist_km = dist_km_ta
            dur_min = dur_min_ta
        else:
            experienced_congestion = effective_congestion

        # Compute fare based on actual dispatched vehicle category
        base_fare, final_fare = self.platform.compute_fare(
            flag_drop_fare, dist_km, dur_min, surge, service_type=driver_agent.vehicle_model.service_type
        )

        # Pickup leg traversal on OSM graph
        drv_n = driver_agent.current_node
        drv_q = int(self.world.node_quadrants[drv_n]) if len(self.world.node_quadrants) > drv_n else q_o
        pickup_nodes, pickup_km = self.get_osm_route(
            drv_n,
            node_o,
            drv_q,
            q_o,
            is_flood_aware=is_fl_aware,
            is_traffic_aware=is_traffic_aware,
            hour=cache_key,
        )
        pickup_overflow = bool(self.world.is_route_affected_by_overflow(pickup_nodes, overflow_quads) if overflow_quads else False)
        if pickup_overflow:
            pickup_spd = max(5.5, 16.0 / experienced_congestion)
            base_wait = (pickup_km / pickup_spd) * 60.0 + float(self.rng.uniform(2.0, 5.0))
        else:
            pickup_spd = max(10.0, 30.0 / experienced_congestion)
            base_wait = (pickup_km / pickup_spd) * 60.0 + float(self.rng.uniform(0.5, 2.0))
        wait_min = round(float(np.clip(base_wait + extra_wait, 1.5, 28.0)), 2)

        is_canceled, cancel_state, reason = self.evaluate_cancellation(
            stratum=origin_zone.socioeconomic_stratum,
            payment_method=payment_method,
            surge=surge,
            final_fare=final_fare,
            wait_min=wait_min,
            effective_water_mm=effective_water_mm,
            flood_affected=flood_affected,
            congestion_idx=experienced_congestion,
            hour=hour,
        )

        if is_canceled:
            trip_status = cancel_state or "cancelado_usuario"
            start_time = None
            end_time = None
            tip_amount = 0.0
            payment_status = "anulado"
            cancelled_by = "conductor" if trip_status == "cancelado_conductor" else "usuario"
            c_step = min(len(pickup_nodes) - 1, max(0, int(len(pickup_nodes) * min(1.0, wait_min / 12.0))))
            driver_agent.assign_trip(pickup_nodes[c_step], req_time + timedelta(minutes=wait_min))
            pickup_fuel = driver_agent.compute_trip_fuel_liters(pickup_km, wait_min, experienced_congestion, False)
            driver_agent.accumulate_distance_and_fuel(pickup_km, pickup_fuel, False, duration_min=wait_min, congestion_idx=experienced_congestion)

            trip_id = recorder.record_trip(
                user_id=user.user_id,
                driver_id=driver_agent.driver_id,
                origin_quadrant_id=q_o,
                destination_quadrant_id=q_d,
                origin_latitude=lat_o,
                origin_longitude=lon_o,
                destination_latitude=lat_d,
                destination_longitude=lon_d,
                requested_at=req_time,
                started_at=start_time,
                completed_at=end_time,
                distance_km=dist_km,
                duration_minutes=dur_min,
                trip_status=trip_status,
            )
            recorder.record_cancellation(
                trip_id=trip_id,
                cancelled_by=cancelled_by,
                cancellation_reason=reason or "Tarifa dinámica sobrepasa presupuesto",
                wait_time_minutes=wait_min,
                origin_active_requests=d_t,
                origin_available_drivers=s_t,
            )
            if driver_agent.fuel_tank and driver_agent.fuel_tank.needs_refueling:
                driver_agent.refuel_pitstop(req_time + timedelta(minutes=wait_min), pitstop_minutes=15.0)
        else:
            trip_status = "completado"
            start_time = req_time + timedelta(minutes=wait_min)
            end_time = start_time + timedelta(minutes=dur_min)
            driver_agent.assign_trip(node_d, end_time)
            trip_fuel = driver_agent.compute_trip_fuel_liters(dist_km, dur_min, experienced_congestion, is_cauce_overflow or flood_affected)
            driver_agent.accumulate_distance_and_fuel(dist_km, trip_fuel, is_cauce_overflow or flood_affected, duration_min=dur_min, congestion_idx=experienced_congestion)

            # Scheduled preventive maintenance check (every 5,000 km)
            if driver_agent.km_since_service >= 5000.0:
                service_odo = driver_agent.odometer_km
                maint_cost = round(float(self.rng.uniform(2400.0, 4800.0)), 2)
                down_hrs = round(float(self.rng.uniform(3.0, 6.5)), 1)
                target_workshop = self.world.find_closest_workshop(lat_d, lon_d)
                transit_km = max(0.5, haversine_km(lat_d, lon_d, target_workshop.latitude, target_workshop.longitude))
                transit_min = (transit_km / 28.0) * 60.0
                transit_fuel = driver_agent.compute_trip_fuel_liters(transit_km, transit_min, effective_congestion, False)
                driver_agent.accumulate_distance_and_fuel(transit_km, transit_fuel, False, duration_min=transit_min, congestion_idx=effective_congestion)
                arrival_at_workshop = end_time + timedelta(minutes=transit_min)

                start_svc, finish_svc, wait_queue_min = target_workshop.admit_vehicle(
                    driver_agent.vehicle_model.vehicle_id, arrival_at_workshop, service_duration_hours=down_hrs
                )
                total_downtime_hours = max(1.0, round((finish_svc - end_time).total_seconds() / 3600.0, 1))
                milestone = int(round(service_odo / 5000.0) * 5000)
                recorder.record_maintenance(
                    vehicle_id=driver_agent.vehicle_model.vehicle_id,
                    service_date=curr_date,
                    maintenance_type="preventivo",
                    odometer_km=service_odo,
                    description=f"Mantenimiento preventivo {milestone} km: cambio de aceite, filtro y revisión en bahía (espera cola: {round(wait_queue_min, 1)} min en {target_workshop.name})",
                    cost_nio=maint_cost,
                    downtime_hours=total_downtime_hours,
                    workshop_name=target_workshop.name,
                )
                driver_agent.send_to_maintenance(finish_svc, queue_wait_min=wait_queue_min)
                driver_agent.current_node = target_workshop.node_id

            elif (is_cauce_overflow or flood_affected) and (self.rng.random() < (0.075 if is_cauce_overflow else 0.035)):
                # Corrective maintenance triggered by flooded cauce transit or overflowed crossing
                maint_cost = round(float(self.rng.uniform(6500.0, 15500.0)), 2)
                down_hrs = round(float(self.rng.uniform(8.0, 24.0)), 1)
                target_workshop = self.world.find_closest_workshop(lat_d, lon_d)
                transit_km = max(0.5, haversine_km(lat_d, lon_d, target_workshop.latitude, target_workshop.longitude))
                transit_min = (transit_km / 28.0) * 60.0
                transit_fuel = driver_agent.compute_trip_fuel_liters(transit_km, transit_min, effective_congestion, False)
                driver_agent.accumulate_distance_and_fuel(transit_km, transit_fuel, False, duration_min=transit_min, congestion_idx=effective_congestion)
                arrival_at_workshop = end_time + timedelta(minutes=transit_min)

                start_svc, finish_svc, wait_queue_min = target_workshop.admit_vehicle(
                    driver_agent.vehicle_model.vehicle_id, arrival_at_workshop, service_duration_hours=down_hrs
                )
                total_downtime_hours = max(1.0, round((finish_svc - end_time).total_seconds() / 3600.0, 1))
                recorder.record_maintenance(
                    vehicle_id=driver_agent.vehicle_model.vehicle_id,
                    service_date=curr_date,
                    maintenance_type="correctivo",
                    odometer_km=driver_agent.odometer_km,
                    description=f"Mantenimiento correctivo: reparación suspensión y secado frenos (espera cola: {round(wait_queue_min, 1)} min en {target_workshop.name})",
                    cost_nio=maint_cost,
                    downtime_hours=total_downtime_hours,
                    workshop_name=target_workshop.name,
                )
                driver_agent.send_to_maintenance(finish_svc, queue_wait_min=wait_queue_min)
                driver_agent.current_node = target_workshop.node_id

            # Fuel tank check: autonomous pitstop if reserve drops below 15%
            if driver_agent.fuel_tank and driver_agent.fuel_tank.needs_refueling:
                driver_agent.refuel_pitstop(end_time, pitstop_minutes=15.0)

            rating_usr, rating_drv = self.platform.sample_ratings(self.rng)
            if driver_agent.vehicle_model.service_type == "movigo_moto" and effective_water_mm > 0.5:
                rating_usr = max(1.0, round(float(rating_usr - self.rng.uniform(0.3, 0.7)), 1))
            elif driver_agent.vehicle_model.service_type == "movigo_comfort":
                rating_usr = min(5.0, round(float(rating_usr + self.rng.uniform(0.1, 0.3)), 1))
            tip_amount = self.platform.sample_tip(self.rng)
            payment_status = "pagado"

            trip_id = recorder.record_trip(
                user_id=user.user_id,
                driver_id=driver_agent.driver_id,
                origin_quadrant_id=q_o,
                destination_quadrant_id=q_d,
                origin_latitude=lat_o,
                origin_longitude=lon_o,
                destination_latitude=lat_d,
                destination_longitude=lon_d,
                requested_at=req_time,
                started_at=start_time,
                completed_at=end_time,
                distance_km=dist_km,
                duration_minutes=dur_min,
                trip_status=trip_status,
            )
            recorder.record_rating(
                trip_id=trip_id,
                user_rating=rating_usr,
                driver_rating=rating_drv,
            )

        recorder.record_payment(
            trip_id=trip_id,
            payment_method=payment_method,
            base_fare=base_fare,
            surge_multiplier=surge,
            tip_amount=tip_amount,
            final_fare=final_fare,
            payment_status=payment_status,
        )

        # Generate real street-snapped telemetry checkpoints along actual traversed OSM nodes
        if not is_canceled and self.rng.random() < 0.14:
            if is_cauce_overflow:
                avg_speed_kmh = max(5.0, min(18.0, (dist_km / max(0.05, dur_min / 60.0))))
            else:
                avg_speed_kmh = max(9.0, min(75.0, (dist_km / max(0.05, dur_min / 60.0))))

            if len(pickup_nodes) > 1:
                mid_p_idx = pickup_nodes[len(pickup_nodes) // 2]
                p_lat = float(self.world.node_coords[mid_p_idx, 0])
                p_lon = float(self.world.node_coords[mid_p_idx, 1])
                p_qid = int(self.world.node_quadrants[mid_p_idx])
            else:
                p_lat, p_lon, p_qid = lat_o, lon_o, q_o

            recorder.record_telemetry(
                driver_id=driver_agent.driver_id,
                trip_id=trip_id,
                quadrant_id=p_qid,
                recorded_at=req_time + timedelta(minutes=round(wait_min * 0.5, 2)),
                latitude=p_lat,
                longitude=p_lon,
                speed_kmh=round(float(np.clip(avg_speed_kmh * self.rng.uniform(0.75, 1.15), 8.0, 60.0)), 2),
                availability_status="en_camino_recogida",
            )

            n_ride = len(ride_nodes)
            for frac in (0.20, 0.55, 0.88):
                step = min(n_ride - 1, max(0, int(n_ride * frac)))
                node_ckpt = ride_nodes[step]
                wp_lat = float(self.world.node_coords[node_ckpt, 0])
                wp_lon = float(self.world.node_coords[node_ckpt, 1])
                wp_qid = int(self.world.node_quadrants[node_ckpt])

                if flood_affected and frac == 0.55:
                    wp_speed = float(self.rng.uniform(4.5, 11.5))
                else:
                    wp_speed = float(np.clip(avg_speed_kmh * self.rng.uniform(0.80, 1.25), 12.0, 58.0))

                recorder.record_telemetry(
                    driver_id=driver_agent.driver_id,
                    trip_id=trip_id,
                    quadrant_id=wp_qid,
                    recorded_at=start_time + timedelta(minutes=round(dur_min * frac, 2)),
                    latitude=wp_lat,
                    longitude=wp_lon,
                    speed_kmh=round(wp_speed, 2),
                    availability_status="ocupado",
                )


    def simulate_hourly_slice(
        self,
        target_dt: datetime,
        weather_dict: dict[str, Any],
        starting_ids: dict[str, int] | None = None,
    ) -> tuple[
        list[Trip],
        list[TripPayment],
        list[TripRating],
        list[TripCancellation],
        list[DriverTelemetry],
        list[VehicleMaintenance],
        list[QuadrantWeather],
    ]:
        """Simulate a single chronological hour slice of MoviGo urban mobility preserving driver physical agent state."""
        hour = target_dt.hour
        dow = target_dt.weekday()
        curr_date = target_dt.date()
        precip_mm = float(weather_dict.get("precipitation_mm", 0.0))
        cong_idx = float(weather_dict.get("congestion_index", 1.0))

        from movigo_sim.engine.platform import HOURLY_TRIP_WEIGHTS
        hourly_base_lam = 175.0 * HOURLY_TRIP_WEIGHTS[hour]
        rain_mult = 1.0 + 0.15 * min(3.0, precip_mm / 5.0)
        n_trips = max(0, int(round(float(self.rng.poisson(lam=max(0.15, hourly_base_lam * rain_mult))))))
        if n_trips == 0 and 7 <= hour <= 21:
            n_trips = 1

        recorder = SimulationRecorder()
        if starting_ids:
            recorder.set_counters(
                trip_id=starting_ids.get("trip_id", 1),
                payment_id=starting_ids.get("payment_id", 1),
                rating_id=starting_ids.get("rating_id", 1),
                cancellation_id=starting_ids.get("cancellation_id", 1),
                telemetry_id=starting_ids.get("telemetry_id", 1),
                maintenance_id=starting_ids.get("maintenance_id", 1),
            )

        eligible_stratum_probs: dict[str, np.ndarray] = {}
        for stratum, w_arr in self.user_stratum_weights.items():
            ew = w_arr.copy()
            ew /= ew.sum()
            eligible_stratum_probs[stratum] = ew

        driver_meal_logged: set[int] = set()
        req_times = sorted(
            target_dt.replace(minute=int(self.rng.integers(0, 60)), second=int(self.rng.integers(0, 60)))
            for _ in range(n_trips)
        )

        for req_time in req_times:
            self._dispatch_trip_request(
                req_time=req_time,
                recorder=recorder,
                driver_meal_logged=driver_meal_logged,
                daily_precip_mm=precip_mm,
                daily_cong_idx=cong_idx,
                hourly_matrices=None,
                date_hour_to_idx=None,
                eligible_users=self.users,
                eligible_stratum_probs=eligible_stratum_probs,
            )

        # Build QuadrantWeather records for all 92 quadrants
        w_start_id = starting_ids.get("weather_id", 1) if starting_ids else 1
        weather_records: list[QuadrantWeather] = []
        for q_idx, q in enumerate(self.world.quadrants_map.values()):
            elev_factor = 1.25 if q.flood_risk in ("alto", "critico") else 0.90
            q_precip = round(precip_mm * elev_factor, 2)
            q_runoff = round(q_precip * (0.85 if q.flood_risk == "critico" else 0.35), 2)
            is_flooded = q_precip >= 8.0 or (q_precip >= 3.0 and q.flood_risk == "critico")
            sky = "tormenta" if q_precip >= 15.0 else ("lluvia_ligera" if q_precip > 0.5 else ("nublado" if weather_dict.get("rain_mm", 0.0) > 0 else "despejado"))
            weather_records.append(
                QuadrantWeather(
                    weather_id=w_start_id + q_idx,
                    quadrant_id=q.quadrant_id,
                    recorded_at=target_dt,
                    date=curr_date,
                    hour=hour,
                    precipitation_mm=q_precip,
                    channel_runoff_mm=q_runoff,
                    temperature_c=float(weather_dict.get("temperature_c", 28.0)),
                    congestion_index=cong_idx,
                    flooded_roads=is_flooded,
                    sky_condition=sky,
                )
            )

        trips, payments, ratings, cancellations, telemetry, maintenance = recorder.get_results()
        return trips, payments, ratings, cancellations, telemetry, maintenance, weather_records

    def simulate_daily_slice(
        self,
        target_date: date,
        hourly_weather_list: list[dict[str, Any]],
        starting_ids: dict[str, int] | None = None,
    ) -> tuple[
        list[Trip],
        list[TripPayment],
        list[TripRating],
        list[TripCancellation],
        list[DriverTelemetry],
        list[VehicleMaintenance],
        list[QuadrantWeather],
    ]:
        """Simulate a full 24-hour day slice of MoviGo urban mobility preserving driver physical agent state."""
        dow = target_date.weekday()
        from movigo_sim.engine.platform import HOURLY_TRIP_WEIGHTS

        recorder = SimulationRecorder()
        if starting_ids:
            recorder.set_counters(
                trip_id=starting_ids.get("trip_id", 1),
                payment_id=starting_ids.get("payment_id", 1),
                rating_id=starting_ids.get("rating_id", 1),
                cancellation_id=starting_ids.get("cancellation_id", 1),
                telemetry_id=starting_ids.get("telemetry_id", 1),
                maintenance_id=starting_ids.get("maintenance_id", 1),
            )

        # Filter eligible users registered on or before target_date
        eligible_mask = self.user_reg_dates <= target_date
        eligible_users = [u for u, m in zip(self.users, eligible_mask) if m]
        if not eligible_users:
            eligible_users = self.users

        eligible_stratum_probs: dict[str, np.ndarray] = {}
        for stratum, w_arr in self.user_stratum_weights.items():
            ew = w_arr[eligible_mask] if len(w_arr) == len(eligible_mask) else w_arr.copy()
            if ew.sum() > 0:
                ew /= ew.sum()
            else:
                ew = np.ones(len(eligible_users)) / len(eligible_users)
            eligible_stratum_probs[stratum] = ew

        # Generate requests distributed across all 24 hours
        all_req_times: list[tuple[datetime, int, float, float]] = []
        for hour in range(24):
            w_h = hourly_weather_list[hour] if hour < len(hourly_weather_list) else {}
            h_precip = float(w_h.get("precipitation_mm", 0.0))
            h_cong = float(w_h.get("congestion_index", 1.0))

            hourly_base_lam = 175.0 * HOURLY_TRIP_WEIGHTS[hour]
            rain_mult = 1.0 + 0.15 * min(3.0, h_precip / 5.0)
            n_trips = max(0, int(round(float(self.rng.poisson(lam=max(0.15, hourly_base_lam * rain_mult))))))
            if n_trips == 0 and 7 <= hour <= 21:
                n_trips = 1

            h_dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)
            for _ in range(n_trips):
                req_t = h_dt.replace(minute=int(self.rng.integers(0, 60)), second=int(self.rng.integers(0, 60)))
                all_req_times.append((req_t, hour, h_precip, h_cong))

        # Sort all 24-hour requests chronologically
        all_req_times.sort(key=lambda x: x[0])

        driver_meal_logged: set[int] = set()
        for req_time, hour, h_precip, h_cong in all_req_times:
            self._dispatch_trip_request(
                req_time=req_time,
                recorder=recorder,
                driver_meal_logged=driver_meal_logged,
                daily_precip_mm=h_precip,
                daily_cong_idx=h_cong,
                hourly_matrices=None,
                date_hour_to_idx=None,
                eligible_users=eligible_users,
                eligible_stratum_probs=eligible_stratum_probs,
            )

        # Build QuadrantWeather records across all 24 hours and all quadrants
        w_start_id = starting_ids.get("weather_id", 1) if starting_ids else 1
        weather_records: list[QuadrantWeather] = []
        curr_w_id = w_start_id

        quads_list = list(self.world.quadrants_map.values())
        for hour in range(24):
            w_h = hourly_weather_list[hour] if hour < len(hourly_weather_list) else {}
            h_dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)
            h_precip = float(w_h.get("precipitation_mm", 0.0))
            h_temp = float(w_h.get("temperature_c", 28.0))
            h_cong = float(w_h.get("congestion_index", 1.0))
            h_rain = float(w_h.get("rain_mm", 0.0))

            for q in quads_list:
                elev_factor = 1.25 if q.flood_risk in ("alto", "critico") else 0.90
                q_precip = round(h_precip * elev_factor, 2)
                q_runoff = round(q_precip * (0.85 if q.flood_risk == "critico" else 0.35), 2)
                is_flooded = q_precip >= 8.0 or (q_precip >= 3.0 and q.flood_risk == "critico")
                sky = "tormenta" if q_precip >= 15.0 else ("lluvia_ligera" if q_precip > 0.5 else ("nublado" if h_rain > 0 else "despejado"))
                weather_records.append(
                    QuadrantWeather(
                        weather_id=curr_w_id,
                        quadrant_id=q.quadrant_id,
                        recorded_at=h_dt,
                        date=target_date,
                        hour=hour,
                        precipitation_mm=q_precip,
                        channel_runoff_mm=q_runoff,
                        temperature_c=h_temp,
                        congestion_index=h_cong,
                        flooded_roads=is_flooded,
                        sky_condition=sky,
                    )
                )
                curr_w_id += 1

        trips, payments, ratings, cancellations, telemetry, maintenance = recorder.get_results()
        return trips, payments, ratings, cancellations, telemetry, maintenance, weather_records
