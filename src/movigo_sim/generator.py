"""Numerical and operational simulation engine for MoviGo ride-hailing app in Managua (3NF OLTP schema).

Generates realistic urban mobility facts with strict mathematical guarantees:
- Two-tier 3NF spatial architecture: 12 urban pricing zones (urban_zones) grouping 92 fine-grained square quadrants (quadrants, ~0.88 km x 0.88 km)
- Time-of-day Origin-Destination (OD) Gravity Model capturing Managua's morning residential->hub commute, midday commercial/market activity, evening reverse commute, and nightlife corridors
- Expanded deterministic population: 800 passengers (users) with Pareto/Zipf ride frequency and registration date enforcement, 150 drivers & 150 vehicles
- Non-overlapping chronological driver dispatch via `driver_available_at` state clock
- Normalized transactional entities:
  * drivers & vehicles (separated 1:1)
  * trips (lean 15-column core ride lifecycle header without transitive zone FKs or pre-calculated fare breakdowns)
  * trip_payments (payment_method, base_fare, surge_multiplier, tip_amount, final_fare, payment_status)
  * trip_ratings (user_rating, driver_rating for completed trips only)
  * trip_cancellations (cancelled_by, cancellation_reason, wait_time_minutes, origin_active_requests, origin_available_drivers for cancelled trips only)
  * driver_telemetry (multi-point GPS breadcrumb trajectories linked via trip_id and quadrant_id without transitive zone_id)
"""

import json
import logging
import math
from datetime import datetime, date, timedelta, time
from typing import Any
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from movigo_sim.config import (
    DETERMINISTIC_SEEDS_DIR,
    LLM_SEEDS_DIR,
    SIMULATION_SEED,
    BASE_PER_KM_NIO,
    BASE_PER_MINUTE_NIO,
    SURGE_RAIN_FACTOR,
    SURGE_MAX,
    OUTLIER_MOBILITY_SHOCK_PROB,
    OUTLIER_AIRPORT_TRIP_PROB,
    OUTLIER_GRIDLOCK_DELAY_PROB,
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

logger = logging.getLogger(__name__)

# Chi-Square Conditional Probability Matrix: P(Payment Method | Socioeconomic Stratum)
# Order: ['efectivo', 'tarjeta', 'billetera_digital']
STRATUM_PAYMENT_PROBABILITIES: dict[str, list[float]] = {
    "alto":      [0.10, 0.65, 0.25], # High stratum: heavily credit/debit card
    "medio":     [0.30, 0.42, 0.28], # Middle stratum: balanced
    "comercial": [0.20, 0.48, 0.32], # Commercial hubs & universities: cards & wallets
    "popular":   [0.75, 0.10, 0.15], # Traditional markets: predominantly cash
}

PAYMENT_METHODS = ["efectivo", "tarjeta", "billetera_digital"]

# Stratum price-sensitivity coefficients for logistic cancellation model
STRATUM_SURGE_BETA: dict[str, float] = {
    "popular":   2.10,
    "medio":     1.25,
    "comercial": 1.00,
    "alto":      0.45,
}

# Hourly arrival curve for Managua urban traffic (24 hours)
HOURLY_TRIP_WEIGHTS = np.array([
    0.015, 0.008, 0.005, 0.004, 0.008, 0.025, # 00:00 - 05:59 (Night)
    0.065, 0.115, 0.085, 0.055, 0.045, 0.055, # 06:00 - 11:59 (Morning peak 7-9am)
    0.080, 0.065, 0.045, 0.040, 0.055, 0.095, # 12:00 - 17:59 (Lunch & mid-afternoon)
    0.110, 0.085, 0.055, 0.040, 0.028, 0.020  # 18:00 - 23:59 (Evening rush & night close)
])
HOURLY_TRIP_WEIGHTS /= HOURLY_TRIP_WEIGHTS.sum()

# Time-of-Day Gravity Profiles: zone_id -> (push_origin_weight, pull_destination_weight)
# Zones:
#  1: Villa Fontana (alto - corporate/financial & residential)
#  2: Las Colinas (alto - residential)
#  3: Santo Domingo (alto - residential & Galerías)
#  4: Los Robles (medio - Zona Hippos dining/nightlife, hotels, offices)
#  5: Altamira (medio - mixed residential & services)
#  6: Bolonia (medio - institutional, medical, embassies)
#  7: Bello Horizonte (medio - high-density east residential)
#  8: Linda Vista (medio - high-density west residential)
#  9: Metrocentro / Eje Corporativo UCA (comercial - central mall, university & business hub)
# 10: Ciudad Jardín (popular - commercial & residential)
# 11: Mercado Oriental (popular - wholesale/retail market hub)
# 12: Mercado Roberto Huembes (popular - bus terminal, market & residential)
ZONE_GRAVITY_REGIMES: dict[str, dict[str, Any]] = {
    "early_dawn": {
        "beta": 0.35,
        "weights": {
            1: (0.7, 0.8),
            2: (0.9, 0.7),
            3: (0.8, 0.7),
            4: (0.9, 1.0),
            5: (1.5, 1.1),
            6: (1.0, 1.3),
            7: (2.6, 1.2),
            8: (2.5, 1.1),
            9: (1.1, 2.2),
            10: (2.2, 1.8),
            11: (1.4, 3.6),
            12: (2.1, 3.2),
        },
    },
    "morning_rush": {
        "beta": 0.30,
        "weights": {
            1: (1.2, 3.1),
            2: (2.6, 0.8),
            3: (2.4, 0.9),
            4: (1.3, 2.6),
            5: (2.2, 1.5),
            6: (1.3, 2.7),
            7: (3.4, 0.9),
            8: (3.2, 0.8),
            9: (1.0, 4.0),
            10: (2.3, 1.6),
            11: (1.1, 3.3),
            12: (2.1, 2.3),
        },
    },
    "midday": {
        "beta": 0.40,
        "weights": {
            1: (1.8, 1.9),
            2: (1.2, 1.3),
            3: (1.3, 1.5),
            4: (2.1, 2.2),
            5: (1.8, 1.8),
            6: (1.9, 1.8),
            7: (1.6, 1.7),
            8: (1.5, 1.6),
            9: (2.9, 3.0),
            10: (2.0, 1.9),
            11: (2.8, 2.7),
            12: (2.3, 2.2),
        },
    },
    "evening_rush": {
        "beta": 0.30,
        "weights": {
            1: (3.1, 1.4),
            2: (0.9, 2.7),
            3: (1.0, 2.5),
            4: (2.7, 1.9),
            5: (1.6, 2.3),
            6: (2.6, 1.3),
            7: (1.1, 3.4),
            8: (1.0, 3.2),
            9: (3.9, 1.3),
            10: (1.7, 2.2),
            11: (3.1, 1.2),
            12: (2.4, 2.1),
        },
    },
    "nightlife_out": {
        "beta": 0.28,
        "weights": {
            1: (2.2, 3.4),
            2: (2.0, 1.3),
            3: (2.1, 2.9),
            4: (2.4, 3.9),
            5: (1.9, 1.7),
            6: (1.4, 1.2),
            7: (2.2, 2.0),
            8: (1.8, 1.4),
            9: (2.5, 2.8),
            10: (1.3, 1.1),
            11: (0.8, 0.6),
            12: (1.4, 1.2),
        },
    },
    "nightlife_return": {
        "beta": 0.28,
        "weights": {
            1: (3.4, 2.0),
            2: (1.2, 2.7),
            3: (2.8, 2.4),
            4: (3.9, 1.8),
            5: (1.6, 2.5),
            6: (1.2, 1.6),
            7: (1.8, 3.1),
            8: (1.2, 2.7),
            9: (2.6, 1.5),
            10: (1.0, 1.8),
            11: (0.6, 0.7),
            12: (1.1, 1.7),
        },
    },
}


def get_gravity_regime_name(hour: int, dow: int) -> str:
    """Map (hour, day_of_week) to the active Managua urban mobility gravity regime."""
    if 3 <= hour <= 5:
        return "early_dawn"
    if 6 <= hour <= 9:
        return "midday" if dow == 6 else "morning_rush"
    if 10 <= hour <= 15:
        return "midday"
    if 16 <= hour <= 19:
        return "midday" if dow == 6 else "evening_rush"
    if 20 <= hour <= 22:
        return "nightlife_out"
    return "nightlife_return"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two WGS84 coordinates."""
    r_earth = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    return 2.0 * r_earth * math.asin(min(1.0, math.sqrt(a)))


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
        self.quadrants_map = {c.quadrant_id: c for c in self.quadrants}
        self.quadrants_centers = np.array(
            [[0.5 * (c.lat_min + c.lat_max), 0.5 * (c.lon_min + c.lon_max)] for c in self.quadrants],
            dtype=float,
        )

        (
            self.zones,
            self.users,
            self.drivers,
            self.campaigns,
            self.templates,
        ) = load_movigo_seed_catalogs()
        self.vehicles = load_movigo_vehicles()

        # Precompute user registration dates, Pareto/Zipf propensity weights, and stratum-coupled rider weights
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

        self.zone_quadrants: dict[int, list[Quadrant]] = {z.zone_id: [] for z in self.zones}
        for c in self.quadrants:
            if c.zone_id in self.zone_quadrants:
                self.zone_quadrants[c.zone_id].append(c)

        self.street_network = load_managua_street_network()
        self.quadrant_streets: dict[int, np.ndarray] = {}
        self.quadrant_flood_flags: dict[int, np.ndarray] = {}
        q_streets_dict = self.street_network.get("quadrant_streets", {})
        q_flags_dict = self.street_network.get("quadrant_flood_flags", {})
        for c in self.quadrants:
            segs = q_streets_dict.get(str(c.quadrant_id), [])
            flags = q_flags_dict.get(str(c.quadrant_id), [])
            if segs:
                self.quadrant_streets[c.quadrant_id] = np.array(segs, dtype=float)
                self.quadrant_flood_flags[c.quadrant_id] = (
                    np.array(flags, dtype=bool) if len(flags) == len(segs) else np.zeros(len(segs), dtype=bool)
                )
            else:
                self.quadrant_streets[c.quadrant_id] = np.empty((0, 4), dtype=float)
                self.quadrant_flood_flags[c.quadrant_id] = np.empty(0, dtype=bool)

        arterials = self.street_network.get("arterials", [])
        self.arterial_segments = np.array(arterials, dtype=float) if arterials else np.empty((0, 4), dtype=float)
        if len(self.arterial_segments) > 0:
            self.arterial_mid_lats = 0.5 * (self.arterial_segments[:, 0] + self.arterial_segments[:, 2])
            self.arterial_mid_lons = 0.5 * (self.arterial_segments[:, 1] + self.arterial_segments[:, 3])
        else:
            self.arterial_mid_lats = np.empty(0, dtype=float)
            self.arterial_mid_lons = np.empty(0, dtype=float)

        # Dense OpenStreetMap Street Graph & Hub Predecessors
        nodes_raw = self.street_network.get("nodes", [])
        edges_raw = self.street_network.get("edges", [])
        if nodes_raw and edges_raw:
            self.node_coords = np.array([[n[0], n[1]] for n in nodes_raw], dtype=float)
            self.node_quadrants = np.array([n[2] for n in nodes_raw], dtype=int)
            self.node_zones = np.array([n[3] for n in nodes_raw], dtype=int)
            self.num_nodes = len(nodes_raw)

            edge_arr = np.array(edges_raw, dtype=float)
            u_idx = edge_arr[:, 0].astype(int)
            v_idx = edge_arr[:, 1].astype(int)
            lengths = edge_arr[:, 2]
            flood_flags = edge_arr[:, 5].astype(int)

            rows = np.concatenate([u_idx, v_idx])
            cols = np.concatenate([v_idx, u_idx])
            dists = np.concatenate([lengths, lengths])
            dists_flood = np.concatenate([
                lengths * np.where(flood_flags == 1, 4.5, 1.0),
                lengths * np.where(flood_flags == 1, 4.5, 1.0),
            ])

            self.csr_dist_normal = csr_matrix((dists, (rows, cols)), shape=(self.num_nodes, self.num_nodes))
            self.csr_dist_flood = csr_matrix((dists_flood, (rows, cols)), shape=(self.num_nodes, self.num_nodes))

            hub_dict = self.street_network.get("quad_hubs", {})
            self.hub_node_indices = [hub_dict.get(str(q.quadrant_id), 0) for q in self.quadrants]
            self.qid_to_hub_idx = {q.quadrant_id: idx for idx, q in enumerate(self.quadrants)}

            self.dists_norm_hubs, self.preds_norm_hubs = dijkstra(
                self.csr_dist_normal, indices=self.hub_node_indices, return_predecessors=True
            )
            self.dists_flood_hubs, self.preds_flood_hubs = dijkstra(
                self.csr_dist_flood, indices=self.hub_node_indices, return_predecessors=True
            )
            self.quad_node_indices = self.street_network.get("quadrant_node_indices", {})
        else:
            self.node_coords = np.empty((0, 2), dtype=float)
            self.node_quadrants = np.empty(0, dtype=int)
            self.node_zones = np.empty(0, dtype=int)
            self.num_nodes = 0
            self.csr_dist_normal = None
            self.csr_dist_flood = None
            self.hub_node_indices = []
            self.qid_to_hub_idx = {}
            self.dists_norm_hubs = None
            self.preds_norm_hubs = None
            self.dists_flood_hubs = None
            self.preds_flood_hubs = None
            self.quad_node_indices = {}

        self.zones_map = {z.zone_id: z for z in self.zones}
        self.drivers_map = {c.driver_id: c for c in self.drivers}
        # All drivers except deactivated ('inactivo') operate shifts across the year
        self.operational_drivers = [c for c in self.drivers if c.status != "inactivo"]
        self.driver_base_weights = np.array(
            [
                (c.acceptance_rate_pct / 100.0) * (0.45 if c.status == "desconectado" else 1.0)
                for c in self.operational_drivers
            ],
            dtype=float,
        )

        # Precompute time-of-day Gravity OD matrices across the 132 directed inter-zone pairs
        self.od_pairs: list[tuple[UrbanZone, UrbanZone]] = []
        zone_dists: list[float] = []
        for zo in self.zones:
            for zd in self.zones:
                if zo.zone_id != zd.zone_id:
                    self.od_pairs.append((zo, zd))
                    zone_dists.append(
                        max(1.2, haversine_km(zo.latitude, zo.longitude, zd.latitude, zd.longitude))
                    )
        zone_dists_arr = np.array(zone_dists, dtype=float)

        self.od_regime_probs: dict[str, np.ndarray] = {}
        self.regime_origin_push_factor: dict[str, dict[int, float]] = {}
        for regime_name, cfg in ZONE_GRAVITY_REGIMES.items():
            beta = float(cfg["beta"])
            w_map: dict[int, tuple[float, float]] = cfg["weights"]
            raw_w = np.array(
                [
                    w_map[zo.zone_id][0] * w_map[zd.zone_id][1]
                    for zo, zd in self.od_pairs
                ],
                dtype=float,
            ) / (zone_dists_arr ** beta)
            self.od_regime_probs[regime_name] = raw_w / raw_w.sum()

            mean_push = float(np.mean([v[0] for v in w_map.values()]))
            self.regime_origin_push_factor[regime_name] = {
                zid: round(v[0] / mean_push, 3) for zid, v in w_map.items()
            }

    def sample_origin_destination_zones(self, hour: int, dow: int) -> tuple[UrbanZone, UrbanZone]:
        """Sample (origin_zone, destination_zone) from the active time-of-day Gravity OD matrix."""
        regime = get_gravity_regime_name(hour, dow)
        probs = self.od_regime_probs[regime]
        pair_idx = int(self.rng.choice(len(self.od_pairs), p=probs))
        return self.od_pairs[pair_idx]

    def sample_street_coordinate(
        self, zone: UrbanZone
    ) -> tuple[float, float, int, bool, int]:
        """Sample a GPS coordinate strictly on a drivable street within one of the urban zone's square quadrants.

        Returns:
            (latitude, longitude, quadrant_id, is_flood_prone_street, nearest_node_idx)
        """
        quad_list = self.zone_quadrants.get(zone.zone_id) or self.quadrants
        q_idx = int(self.rng.integers(0, len(quad_list)))
        quad = quad_list[q_idx]

        segs = self.quadrant_streets.get(quad.quadrant_id)
        flags = self.quadrant_flood_flags.get(quad.quadrant_id)
        q_node_idxs = self.quad_node_indices.get(str(quad.quadrant_id), [])

        if segs is not None and len(segs) > 0:
            idx = int(self.rng.integers(0, len(segs)))
            lat1, lon1, lat2, lon2 = segs[idx]
            t = float(self.rng.uniform(0.0, 1.0))
            lat = round(lat1 + t * (lat2 - lat1), 6)
            lon = round(lon1 + t * (lon2 - lon1), 6)
            is_flood_street = (
                bool(flags[idx])
                if flags is not None and len(flags) > idx
                else (quad.flood_risk == "critico")
            )
            if q_node_idxs and len(self.node_coords) > 0:
                node_coords_q = self.node_coords[q_node_idxs]
                d2 = (node_coords_q[:, 0] - lat) ** 2 + (node_coords_q[:, 1] - lon) ** 2
                best_local_idx = int(np.argmin(d2))
                best_node = q_node_idxs[best_local_idx]
            elif self.hub_node_indices:
                best_node = self.hub_node_indices[
                    self.qid_to_hub_idx.get(quad.quadrant_id, 0)
                ]
            else:
                best_node = 0
            return lat, lon, quad.quadrant_id, is_flood_street, best_node

        hub_idx = (
            self.hub_node_indices[self.qid_to_hub_idx.get(quad.quadrant_id, 0)]
            if self.hub_node_indices
            else 0
        )
        h_lat = (
            float(self.node_coords[hub_idx, 0])
            if len(self.node_coords) > hub_idx
            else float(quad.lat_min + 0.004)
        )
        h_lon = (
            float(self.node_coords[hub_idx, 1])
            if len(self.node_coords) > hub_idx
            else float(quad.lon_min + 0.004)
        )
        return h_lat, h_lon, quad.quadrant_id, (quad.flood_risk == "critico"), hub_idx

    def snap_to_nearest_street_and_quadrant(
        self, target_lat: float, target_lon: float, fallback_zone: UrbanZone
    ) -> tuple[float, float, int, int]:
        """Snap an arbitrary waypoint coordinate onto the nearest real OpenStreetMap street inside an active square quadrant.

        Returns:
            (lat, lon, zone_id, quadrant_id)
        """
        d2 = (self.quadrants_centers[:, 0] - target_lat) ** 2 + (
            self.quadrants_centers[:, 1] - target_lon
        ) ** 2
        nearest_q_idx = int(np.argmin(d2))
        quad = self.quadrants[nearest_q_idx]
        segs = self.quadrant_streets.get(quad.quadrant_id)
        if segs is not None and len(segs) > 0:
            seg_idx = int(self.rng.integers(0, len(segs)))
            lat1, lon1, lat2, lon2 = segs[seg_idx]
            t = float(self.rng.uniform(0.15, 0.85))
            lat = round(float(np.clip(lat1 + t * (lat2 - lat1), quad.lat_min, quad.lat_max)), 6)
            lon = round(float(np.clip(lon1 + t * (lon2 - lon1), quad.lon_min, quad.lon_max)), 6)
            return lat, lon, quad.zone_id, quad.quadrant_id

        lat, lon, qid, _, _ = self.sample_street_coordinate(fallback_zone)
        return lat, lon, fallback_zone.zone_id, qid

    def get_osm_route(
        self,
        origin_node_idx: int,
        dest_node_idx: int,
        origin_qid: int,
        dest_qid: int,
        is_flood_aware: bool = False,
        is_perturbed: bool = False,
    ) -> tuple[list[int], float]:
        """Reconstruct a continuous sequence of real OpenStreetMap street nodes between origin and destination."""
        if origin_node_idx == dest_node_idx or self.preds_norm_hubs is None:
            return [origin_node_idx], 0.20

        lat_o, lon_o = float(self.node_coords[origin_node_idx, 0]), float(
            self.node_coords[origin_node_idx, 1]
        )
        lat_d, lon_d = float(self.node_coords[dest_node_idx, 0]), float(
            self.node_coords[dest_node_idx, 1]
        )
        hav = haversine_km(lat_o, lon_o, lat_d, lon_d)

        if origin_qid == dest_qid or hav < 1.0:
            route_km = max(0.45, round(hav * 1.25, 2))
            return [origin_node_idx, dest_node_idx], route_km

        h_idx = self.qid_to_hub_idx.get(origin_qid, 0)
        hub_node = self.hub_node_indices[h_idx]
        preds = (
            self.preds_flood_hubs[h_idx]
            if is_flood_aware
            else self.preds_norm_hubs[h_idx]
        )

        path_rev = [dest_node_idx]
        curr = dest_node_idx
        for _ in range(350):
            nxt = preds[curr]
            if nxt < 0 or nxt == curr:
                break
            path_rev.append(int(nxt))
            curr = int(nxt)
            if curr == hub_node:
                break

        if path_rev[-1] == hub_node and origin_node_idx != hub_node:
            path_rev.append(origin_node_idx)

        path_nodes = path_rev[::-1]
        coords = self.node_coords[path_nodes]
        dp = np.radians(np.diff(coords[:, 0]))
        dl = np.radians(np.diff(coords[:, 1]))
        p1 = np.radians(coords[:-1, 0])
        p2 = np.radians(coords[1:, 0])
        a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
        dists = 2.0 * 6371.0 * np.arcsin(np.minimum(1.0, np.sqrt(a)))
        raw_km = float(np.sum(dists))

        circuity = (
            float(self.rng.uniform(1.08, 1.22))
            if is_perturbed
            else float(self.rng.uniform(1.02, 1.06))
        )
        route_km = round(max(0.65, max(raw_km * circuity, hav * 1.15)), 2)
        return path_nodes, route_km

    def calculate_daily_demand(self, precip_mm: float, dow: int) -> int:
        """Daily ride requests driven by rain and day-of-week in Managua with realistic noise and mobility shocks."""
        dow_adj = 30.0 if dow in [4, 5] else (0.0 if dow in [0, 1, 2, 3] else -15.0)
        rain_adj = 5.2 * precip_mm
        noise_std = 12.0 + (0.65 * precip_mm)
        noise = float(self.rng.normal(0, noise_std))

        total_rides = 175.0 + rain_adj + dow_adj + noise

        shock_roll = float(self.rng.random())
        if shock_roll < (OUTLIER_MOBILITY_SHOCK_PROB * 0.60):
            total_rides *= float(self.rng.uniform(1.35, 1.65))
        elif shock_roll < OUTLIER_MOBILITY_SHOCK_PROB:
            total_rides *= float(self.rng.uniform(0.50, 0.68))

        return max(60, int(round(total_rides)))

    def sample_trip_time(self, curr_date: date) -> datetime:
        """Sample request timestamp via NHPP."""
        hour = int(self.rng.choice(24, p=HOURLY_TRIP_WEIGHTS))
        minute = int(self.rng.integers(0, 60))
        second = int(self.rng.integers(0, 60))
        return datetime.combine(curr_date, time(hour, minute, second))

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
        """Simulate origin zone active demand (Dt), available drivers (St), and equilibrium surge multiplier m*.

        Couples Dt and St to the excess demand equation:
            f(m) = Dt * exp(-alpha * (m - 1)) - St * (1 + gamma * ln(m)) = 0
        driven by localized hourly quadrant rainfall, cauce runoff, time-of-day gravity push, and active incentive campaigns.
        """
        hour_weight = HOURLY_TRIP_WEIGHTS[hour] / HOURLY_TRIP_WEIGHTS.mean()
        stratum_demand_factor = {
            "comercial": 1.30,
            "popular": 1.20,
            "medio": 1.00,
            "alto": 0.90,
        }.get(origin_zone.socioeconomic_stratum, 1.0)

        regime = get_gravity_regime_name(hour, dow)
        gravity_push = self.regime_origin_push_factor[regime].get(origin_zone.zone_id, 1.0)
        zone_demand_factor = 0.65 * stratum_demand_factor + 0.35 * gravity_push

        weekend_boost = 1.15 if dow in [4, 5] else 1.00
        effective_water_mm = max(hourly_precip_mm, 0.75 * runoff_mm)

        # Active trip requests in origin zone during that hour (Dt)
        expected_d = (14.0 * hour_weight * zone_demand_factor * weekend_boost) + (1.45 * effective_water_mm)
        if flooded_roads:
            expected_d *= 1.22
        d_t = max(2, int(round(self.rng.normal(expected_d, max(1.8, 0.12 * expected_d)))))

        # Available driver supply in origin zone during that hour (St), coupled with active incentive campaigns
        rain_supply_penalty = max(0.45, 1.0 - 0.032 * effective_water_mm - (0.18 if flooded_roads else 0.0))
        peak_supply_factor = 0.82 if hour in [7, 8, 17, 18] else (0.90 if hour in [12, 13, 19] else 1.12)
        campaign_supply_boost = 1.0
        if curr_date is not None:
            for camp in self.campaigns:
                if camp.start_date <= curr_date <= camp.end_date:
                    hours_factor = camp.online_hours_increase / 1000.0
                    if camp.target_zone_id == origin_zone.zone_id:
                        campaign_supply_boost += 0.14 * hours_factor
                    elif camp.incentive_type == "hora_pico_lluvia" and effective_water_mm >= 1.0:
                        campaign_supply_boost += 0.12 * hours_factor
                    else:
                        campaign_supply_boost += 0.04 * hours_factor
        expected_s = (
            13.5 * hour_weight * zone_demand_factor * peak_supply_factor * rain_supply_penalty * campaign_supply_boost
        ) + 2.0
        s_t = max(1, int(round(self.rng.normal(expected_s, max(1.5, 0.10 * expected_s)))))

        # Solve market-clearing surge multiplier m* from excess demand ratio Dt / St
        if d_t <= s_t and effective_water_mm < 0.5 and hour not in [7, 8, 17, 18]:
            base_m = 1.00 + max(0.0, float(self.rng.normal(0.0, 0.03)))
        else:
            m = float(np.clip((d_t / max(1.0, float(s_t))) ** 0.65, 1.01, SURGE_MAX))
            alpha = 0.65
            gamma = 0.85
            for _ in range(4):
                f_val = d_t * math.exp(-alpha * (m - 1.0)) - s_t * (1.0 + gamma * math.log(m))
                df_val = -alpha * d_t * math.exp(-alpha * (m - 1.0)) - (s_t * gamma / m)
                if abs(df_val) > 1e-6:
                    m = float(np.clip(m - f_val / df_val, 1.00, SURGE_MAX))
            rain_boost = 0.045 * effective_water_mm + (0.18 if flooded_roads else 0.0)
            rush_boost = 0.12 if hour in [7, 8, 17, 18] else (0.06 if hour in [12, 13, 19] else 0.0)
            base_m = m + rain_boost + rush_boost + float(self.rng.normal(0.0, 0.04))

        if (flooded_roads or effective_water_mm > 8.0) and hour in [7, 8, 17, 18] and self.rng.random() < 0.22:
            multiplier = float(self.rng.uniform(2.60, 3.20))
        else:
            multiplier = float(np.clip(base_m, 1.00, SURGE_MAX))

        return d_t, s_t, round(multiplier, 2)

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
        stratum_probs = np.array(
            STRATUM_PAYMENT_PROBABILITIES.get(stratum, [0.40, 0.35, 0.25]),
            dtype=float,
        )
        if preferred_method is not None and preferred_method in PAYMENT_METHODS:
            pref_idx = PAYMENT_METHODS.index(preferred_method)
            probs = (1.0 - user_weight) * stratum_probs
            probs[pref_idx] += user_weight
            probs /= probs.sum()
        else:
            probs = stratum_probs
        return str(self.rng.choice(PAYMENT_METHODS, p=probs))

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
        hav_km = haversine_km(lat_o, lon_o, lat_d, lon_d)

        if raw_route_km is not None and raw_route_km > 0.0:
            base_km = raw_route_km
        else:
            base_km = max(0.65, hav_km * 1.25)

        subopt = bool(is_suboptimal or flood_affected_route or (self.rng.random() < 0.16))
        if flood_affected_route:
            detour_factor = float(self.rng.uniform(1.15, 1.45))
        elif subopt:
            detour_factor = float(self.rng.uniform(1.10, 1.28))
        else:
            detour_factor = float(self.rng.uniform(1.02, 1.08))

        dist_km = round(max(0.65, max(base_km * detour_factor, hav_km * 1.15)), 2)

        if flood_affected_route:
            effective_speed_kmh = float(self.rng.uniform(5.5, 12.0))
        else:
            rain_speed_penalty = 1.0 + 0.022 * effective_water_mm
            effective_speed_kmh = max(8.5, 32.0 / (congestion_idx * rain_speed_penalty))

        duration_min = round(
            max(2.5, (dist_km / effective_speed_kmh) * 60.0 + float(self.rng.uniform(1.0, 3.0))),
            2,
        )
        return dist_km, duration_min, subopt

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
        beta_surge = STRATUM_SURGE_BETA.get(stratum, 1.15)
        surge_term = beta_surge * (surge - 1.0)

        cash_term = 0.0
        if payment_method == "efectivo":
            if final_fare > 500.0:
                cash_term = 2.15
            elif final_fare > 200.0:
                cash_term = 1.10

        delay_term = 0.0
        if wait_min > 10.0:
            delay_term = 0.24 * (math.exp(0.22 * min(wait_min - 10.0, 10.0)) - 1.0)

        peak_term = 0.55 if hour in [7, 8, 17, 18] else 0.0
        flood_term = 0.95 if flood_affected else (0.35 if effective_water_mm > 4.0 else (0.18 if congestion_idx > 2.2 else 0.0))

        logit = -3.88 + surge_term + cash_term + delay_term + peak_term + flood_term
        cancel_prob = float(np.clip(1.0 / (1.0 + math.exp(-logit)), 0.015, 0.72))

        if self.rng.random() >= cancel_prob:
            return False, None, None

        if flood_affected or (effective_water_mm > 3.5 and self.rng.random() < 0.55):
            return True, "cancelado_conductor", "Vía anegada / cauce intransitable"

        if (cash_term > 0.0 or surge >= 1.35) and self.rng.random() < 0.58:
            return True, "cancelado_usuario", "Tarifa dinámica sobrepasa presupuesto"

        if wait_min > 10.0:
            if self.rng.random() < 0.62:
                return True, "cancelado_usuario", "Tiempo de llegada excesivo"
            return True, "cancelado_usuario", "Conductor no avanza"

        if congestion_idx > 2.0 and self.rng.random() < 0.55:
            if self.rng.random() < 0.65:
                return True, "cancelado_usuario", "Conductor no avanza"
            return True, "cancelado_usuario", "Tiempo de llegada excesivo"

        roll = float(self.rng.random())
        if roll < 0.40:
            return True, "cancelado_usuario", "Tarifa dinámica sobrepasa presupuesto"
        elif roll < 0.72:
            return True, "cancelado_usuario", "Tiempo de llegada excesivo"
        elif roll < 0.88:
            return True, "cancelado_usuario", "Conductor no avanza"
        else:
            reason = "Vía anegada / cauce intransitable" if effective_water_mm > 1.5 else "Falla mecánica / imprevisto del conductor"
            return True, "cancelado_conductor", reason

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

        trips: list[Trip] = []
        payments: list[TripPayment] = []
        ratings: list[TripRating] = []
        cancellations: list[TripCancellation] = []
        telemetry: list[DriverTelemetry] = []

        trip_counter = 1
        payment_counter = 1
        rating_counter = 1
        cancellation_counter = 1
        telemetry_counter = 1

        # Continuous stateful positioning of operational drivers on the Managua street network
        driver_node: dict[int, int] = {}
        driver_available_at: dict[int, datetime] = {}
        for d in self.operational_drivers:
            home_zid = (d.driver_id % len(self.zones)) + 1
            home_quads = self.zone_quadrants.get(home_zid, self.quadrants)
            hq = home_quads[d.driver_id % len(home_quads)].quadrant_id
            h_idx = self.qid_to_hub_idx.get(hq, 0)
            driver_node[d.driver_id] = self.hub_node_indices[h_idx] if self.hub_node_indices else 0
            driver_available_at[d.driver_id] = datetime.min

        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
            curr_date: date = row["date"]
            daily_precip_mm: float = float(row["precipitation_mm"])
            daily_cong_idx: float = float(row["congestion_index"])
            dow: int = curr_date.weekday()

            daily_target = self.calculate_daily_demand(daily_precip_mm, dow)

            # Filter users who have already registered on or before curr_date and precompute stratum-coupled probabilities
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
                trip_id = trip_counter
                trip_counter += 1

                hour = req_time.hour

                origin_zone, destination_zone = self.sample_origin_destination_zones(hour, dow)

                u_probs = eligible_stratum_probs.get(origin_zone.socioeconomic_stratum)
                if u_probs is not None:
                    u_idx = int(self.rng.choice(len(eligible_users), p=u_probs))
                else:
                    u_idx = int(self.rng.integers(0, len(eligible_users)))
                user = eligible_users[u_idx]

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
                distance_charge = round(dist_km * BASE_PER_KM_NIO, 2)
                time_charge = round(dur_min * BASE_PER_MINUTE_NIO, 2)
                base_fare = round(flag_drop_fare + distance_charge + time_charge, 2)
                final_fare = round(base_fare * surge, 2)

                # Dispatch matching: stateful free drivers & greedy proximity dispatch
                free_indices = [
                    idx for idx, d in enumerate(self.operational_drivers)
                    if driver_available_at[d.driver_id] <= req_time
                ]

                # Idle cruising: if a free driver was idle > 45 min, reposition along OSM graph
                for idx in free_indices:
                    d = self.operational_drivers[idx]
                    idle_gap = (req_time - driver_available_at[d.driver_id]).total_seconds() / 60.0
                    if idle_gap > 45.0 and self.rng.random() < 0.20:
                        regime_name = get_gravity_regime_name(hour, dow)
                        top_z = 9 if "rush" in regime_name else (4 if "night" in regime_name else 11)
                        top_quads = self.zone_quadrants.get(top_z, self.quadrants)
                        target_q = top_quads[int(self.rng.integers(0, len(top_quads)))].quadrant_id
                        target_node = self.hub_node_indices[self.qid_to_hub_idx.get(target_q, 0)]
                        driver_node[d.driver_id] = target_node
                        driver_available_at[d.driver_id] = req_time

                        if self.rng.random() < 0.35:
                            c_lat = float(self.node_coords[target_node, 0])
                            c_lon = float(self.node_coords[target_node, 1])
                            telemetry.append(
                                DriverTelemetry(
                                    telemetry_id=telemetry_counter,
                                    driver_id=d.driver_id,
                                    trip_id=None,
                                    quadrant_id=target_q,
                                    recorded_at=req_time,
                                    latitude=c_lat,
                                    longitude=c_lon,
                                    speed_kmh=round(float(self.rng.uniform(10.0, 24.0)), 2),
                                    availability_status="disponible",
                                )
                            )
                            telemetry_counter += 1

                if free_indices:
                    proximity_w = []
                    for idx in free_indices:
                        d = self.operational_drivers[idx]
                        d_pos = self.node_coords[driver_node[d.driver_id]]
                        d_hav = haversine_km(d_pos[0], d_pos[1], lat_o, lon_o)
                        score = 1.0 / max(0.4, d_hav)
                        w = score * (d.acceptance_rate_pct / 100.0) * (0.45 if d.status == "desconectado" else 1.0)
                        proximity_w.append(w)
                    proximity_w_arr = np.array(proximity_w, dtype=float)
                    proximity_w_arr /= proximity_w_arr.sum()
                    chosen_local_idx = int(self.rng.choice(len(free_indices), p=proximity_w_arr))
                    driver = self.operational_drivers[free_indices[chosen_local_idx]]
                    extra_wait = 0.0
                else:
                    driver = min(self.operational_drivers, key=lambda d: driver_available_at[d.driver_id])
                    extra_wait = max(0.0, (driver_available_at[driver.driver_id] - req_time).total_seconds() / 60.0)

                # Pickup leg traversal on OSM graph
                drv_n = driver_node[driver.driver_id]
                drv_q = int(self.node_quadrants[drv_n]) if len(self.node_quadrants) > drv_n else q_o
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
                    driver_node[driver.driver_id] = pickup_nodes[c_step]
                    driver_available_at[driver.driver_id] = req_time + timedelta(minutes=wait_min)
                    cancellations.append(
                        TripCancellation(
                            cancellation_id=cancellation_counter,
                            trip_id=trip_id,
                            cancelled_by=cancelled_by,
                            cancellation_reason=reason or "Tarifa dinámica sobrepasa presupuesto",
                            wait_time_minutes=wait_min,
                            origin_active_requests=d_t,
                            origin_available_drivers=s_t,
                        )
                    )
                    cancellation_counter += 1
                else:
                    trip_status = "completado"
                    start_time = req_time + timedelta(minutes=wait_min)
                    end_time = start_time + timedelta(minutes=dur_min)
                    driver_node[driver.driver_id] = node_d
                    driver_available_at[driver.driver_id] = end_time
                    rating_usr = float(self.rng.choice([5.0, 4.0, 3.0, 2.0, 1.0], p=[0.67, 0.20, 0.06, 0.04, 0.03]))
                    rating_drv = float(self.rng.choice([5.0, 4.0, 3.0, 2.0, 1.0], p=[0.75, 0.14, 0.05, 0.03, 0.03]))

                    tip_roll = float(self.rng.random())
                    if tip_roll < 0.015:
                        tip_amount = float(self.rng.choice([80.0, 100.0, 150.0]))
                    elif tip_roll < 0.28:
                        tip_amount = float(self.rng.choice([20.0, 30.0, 50.0], p=[0.60, 0.30, 0.10]))
                    else:
                        tip_amount = 0.0
                    payment_status = "pagado"

                    ratings.append(
                        TripRating(
                            rating_id=rating_counter,
                            trip_id=trip_id,
                            user_rating=rating_usr,
                            driver_rating=rating_drv,
                        )
                    )
                    rating_counter += 1

                trips.append(
                    Trip(
                        trip_id=trip_id,
                        user_id=user.user_id,
                        driver_id=driver.driver_id,
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
                )

                payments.append(
                    TripPayment(
                        payment_id=payment_counter,
                        trip_id=trip_id,
                        payment_method=payment_method,
                        base_fare=base_fare,
                        surge_multiplier=surge,
                        tip_amount=tip_amount,
                        final_fare=final_fare,
                        payment_status=payment_status,
                    )
                )
                payment_counter += 1

                # Generate real street-snapped telemetry checkpoints along actual traversed OSM nodes
                if not is_canceled and self.rng.random() < 0.14:
                    avg_speed_kmh = max(9.0, min(75.0, (dist_km / max(0.05, dur_min / 60.0))))

                    if len(pickup_nodes) > 1:
                        mid_p_idx = pickup_nodes[len(pickup_nodes) // 2]
                        p_lat = float(self.node_coords[mid_p_idx, 0])
                        p_lon = float(self.node_coords[mid_p_idx, 1])
                        p_qid = int(self.node_quadrants[mid_p_idx])
                    else:
                        p_lat, p_lon, p_qid = lat_o, lon_o, q_o

                    telemetry.append(
                        DriverTelemetry(
                            telemetry_id=telemetry_counter,
                            driver_id=driver.driver_id,
                            trip_id=trip_id,
                            quadrant_id=p_qid,
                            recorded_at=req_time + timedelta(minutes=round(wait_min * 0.5, 2)),
                            latitude=p_lat,
                            longitude=p_lon,
                            speed_kmh=round(float(np.clip(avg_speed_kmh * self.rng.uniform(0.75, 1.15), 8.0, 60.0)), 2),
                            availability_status="en_camino_recogida",
                        )
                    )
                    telemetry_counter += 1

                    n_ride = len(ride_nodes)
                    for frac in (0.20, 0.55, 0.88):
                        step = min(n_ride - 1, max(0, int(n_ride * frac)))
                        node_ckpt = ride_nodes[step]
                        wp_lat = float(self.node_coords[node_ckpt, 0])
                        wp_lon = float(self.node_coords[node_ckpt, 1])
                        wp_qid = int(self.node_quadrants[node_ckpt])

                        if flood_affected and frac == 0.55:
                            wp_speed = float(self.rng.uniform(4.5, 11.5))
                        else:
                            wp_speed = float(np.clip(avg_speed_kmh * self.rng.uniform(0.80, 1.25), 12.0, 58.0))

                        telemetry.append(
                            DriverTelemetry(
                                telemetry_id=telemetry_counter,
                                driver_id=driver.driver_id,
                                trip_id=trip_id,
                                quadrant_id=wp_qid,
                                recorded_at=start_time + timedelta(minutes=round(dur_min * frac, 2)),
                                latitude=wp_lat,
                                longitude=wp_lon,
                                speed_kmh=round(wp_speed, 2),
                                availability_status="ocupado",
                            )
                        )
                        telemetry_counter += 1

            if (day_idx + 1) % 60 == 0 or (day_idx + 1) == len(weather_df):
                logger.info(f"Simulated {day_idx + 1}/{len(weather_df)} days... ({len(trips)} rides generated)")

        logger.info(
            f"MoviGo simulation completed! Produced {len(trips)} trips, {len(payments)} payments, "
            f"{len(ratings)} ratings, {len(cancellations)} cancellations, and {len(telemetry)} telemetry pings."
        )
        return trips, payments, ratings, cancellations, telemetry
