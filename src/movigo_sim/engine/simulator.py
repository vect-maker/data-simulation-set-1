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
            h_quads = self.world.zone_quadrants.get(hz, self.quadrants)
            a_quads = self.world.zone_quadrants.get(az, self.quadrants)
            hq = h_quads[(u.user_id * 7) % len(h_quads)]
            aq = a_quads[(u.user_id * 11) % len(a_quads)]
            h_hub = self.world.hub_node_indices[self.world.qid_to_hub_idx.get(hq.quadrant_id, 0)]
            a_hub = self.world.hub_node_indices[self.world.qid_to_hub_idx.get(aq.quadrant_id, 0)]
            h_lat = float(self.world.node_coords[h_hub, 0])
            h_lon = float(self.world.node_coords[h_hub, 1])
            a_lat = float(self.world.node_coords[a_hub, 0])
            a_lon = float(self.world.node_coords[a_hub, 1])

            persona = RiderPersona(
                archetype=archetype,
                home_zone_id=hz,
                home_quadrant_id=hq.quadrant_id,
                home_node=h_hub,
                home_lat=h_lat,
                home_lon=h_lon,
                anchor_zone_id=az,
                anchor_quadrant_id=aq.quadrant_id,
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
        is_perturbed: bool = False,
    ) -> tuple[list[int], float]:
        """Reconstruct continuous sequence of real OSM nodes."""
        return self.world.get_osm_route(
            origin_node_idx,
            dest_node_idx,
            origin_qid,
            dest_qid,
            is_flood_aware=is_flood_aware,
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
    ) -> tuple[
        list[Trip],
        list[TripPayment],
        list[TripRating],
        list[TripCancellation],
        list[DriverTelemetry],
    ]:
        """Run full year MoviGo simulation emitting 3NF OLTP transactional tables with Gravity OD & non-overlapping dispatch."""
        self.rng = np.random.default_rng(self.random_seed)
        logger.info(f"Starting MoviGo 3NF simulation across {len(weather_df)} days (seed={self.random_seed})...")

        hourly_matrices: dict[str, Any] | None = weather_df.attrs.get("hourly_matrices")
        date_hour_to_idx: dict[tuple[date, int], int] = (
            hourly_matrices["date_hour_to_idx"] if hourly_matrices else {}
        )

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

        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
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
                    flood_affected = bool(
                        h_aneg_o
                        or h_aneg_d
                        or ((flood_street_o or flood_street_d) and effective_water_mm >= 3.0)
                    )
                else:
                    h_precip_o = daily_precip_mm / 8.0 if hour in range(13, 21) else 0.0
                    h_esc_o = h_precip_o
                    effective_congestion = daily_cong_idx
                    effective_water_mm = h_precip_o
                    flood_affected = bool((flood_street_o or flood_street_d) and daily_precip_mm > 15.0)
                    h_aneg_o = flood_affected

                # Supply & Demand state at request time and equilibrium surge multiplier
                d_t, s_t, surge = self.simulate_supply_demand_and_surge(
                    origin_zone, h_precip_o, h_esc_o, h_aneg_o, hour, dow, curr_date=curr_date
                )

                payment_method = self.sample_payment_method_for_stratum(
                    origin_zone.socioeconomic_stratum,
                    preferred_method=user.preferred_payment_method,
                )

                # Route selection on dense OSM graph (45% habitual, 35% perturbed detour, 20% weather-aware)
                beh_roll = float(self.rng.random())
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

                dist_km, dur_min, is_suboptimal = self.estimate_distance_and_duration(
                    lat_o, lon_o, lat_d, lon_d, effective_congestion, effective_water_mm, flood_affected,
                    raw_route_km=raw_road_km, is_suboptimal=is_pert
                )

                flag_drop_fare = round(float(origin_zone.base_flag_drop_fare), 2)
                base_fare, final_fare = self.platform.compute_fare(flag_drop_fare, dist_km, dur_min, surge)

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
                            recorder.record_telemetry(
                                driver_id=agent.driver_id,
                                trip_id=None,
                                quadrant_id=target_q,
                                recorded_at=req_time,
                                latitude=c_lat,
                                longitude=c_lon,
                                speed_kmh=round(float(self.rng.uniform(10.0, 24.0)), 2),
                                availability_status="disponible",
                            )

                driver_agent, extra_wait = self.platform.dispatch_driver(
                    free_drivers=free_agents,
                    all_operational_drivers=self.driver_agents,
                    lat_o=lat_o,
                    lon_o=lon_o,
                    req_time=req_time,
                    world=self.world,
                    rng=self.rng,
                )

                # Pickup leg traversal on OSM graph
                drv_n = driver_agent.current_node
                drv_q = int(self.world.node_quadrants[drv_n]) if len(self.world.node_quadrants) > drv_n else q_o
                pickup_nodes, pickup_km = self.get_osm_route(drv_n, node_o, drv_q, q_o)
                pickup_spd = max(10.0, 30.0 / effective_congestion)
                base_wait = (pickup_km / pickup_spd) * 60.0 + float(self.rng.uniform(0.5, 2.0))
                wait_min = round(float(np.clip(base_wait + extra_wait, 1.5, 25.0)), 2)

                is_canceled, cancel_state, reason = self.evaluate_cancellation(
                    stratum=origin_zone.socioeconomic_stratum,
                    payment_method=payment_method,
                    surge=surge,
                    final_fare=final_fare,
                    wait_min=wait_min,
                    effective_water_mm=effective_water_mm,
                    flood_affected=flood_affected,
                    congestion_idx=effective_congestion,
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
                else:
                    trip_status = "completado"
                    start_time = req_time + timedelta(minutes=wait_min)
                    end_time = start_time + timedelta(minutes=dur_min)
                    driver_agent.assign_trip(node_d, end_time)

                    rating_usr, rating_drv = self.platform.sample_ratings(self.rng)
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

            if (day_idx + 1) % 60 == 0 or (day_idx + 1) == len(weather_df):
                logger.info(f"Simulated {day_idx + 1}/{len(weather_df)} days... ({len(recorder.trips)} rides generated)")

        trips, payments, ratings, cancellations, telemetry = recorder.get_results()
        logger.info(
            f"MoviGo simulation completed! Produced {len(trips)} trips, {len(payments)} payments, "
            f"{len(ratings)} ratings, {len(cancellations)} cancellations, and {len(telemetry)} telemetry pings."
        )
        return trips, payments, ratings, cancellations, telemetry
