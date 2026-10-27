"""Physical world environment for MoviGo simulation.

Manages the Managua urban environment:
- OpenStreetMap dense street network topology (nodes, edges, CSR matrices).
- Dijkstra shortest path and weather-aware route reconstruction.
- Origin-Destination Gravity Model regimes across the 12 urban zones and 92 quadrants.
- Real coordinate sampling, street snapping, and flood/traffic physics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from movigo_sim.models import Quadrant, UrbanZone

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
            13: (2.2, 1.5),
            14: (1.1, 2.2),
            15: (2.2, 1.6),
            16: (2.4, 1.4),
            17: (1.2, 1.1),
            18: (0.8, 0.7),
            19: (1.1, 2.2),
            20: (2.1, 3.2),
            21: (1.0, 2.4),
            22: (2.3, 1.6),
            23: (2.3, 1.5),
            24: (2.4, 1.4),
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
            13: (3.0, 0.9),
            14: (1.1, 2.8),
            15: (3.1, 0.9),
            16: (3.3, 0.8),
            17: (2.2, 1.3),
            18: (2.6, 0.8),
            19: (1.2, 3.6),
            20: (1.2, 3.4),
            21: (1.0, 3.8),
            22: (3.2, 0.9),
            23: (3.3, 0.8),
            24: (3.4, 0.8),
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
            13: (1.9, 1.8),
            14: (2.5, 2.6),
            15: (1.9, 1.8),
            16: (1.8, 1.7),
            17: (1.6, 1.6),
            18: (1.3, 1.4),
            19: (2.8, 2.9),
            20: (2.6, 2.7),
            21: (2.7, 2.8),
            22: (1.9, 1.8),
            23: (1.8, 1.7),
            24: (1.7, 1.7),
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
            13: (1.0, 3.1),
            14: (2.8, 1.4),
            15: (1.0, 3.2),
            16: (0.9, 3.4),
            17: (1.4, 2.2),
            18: (0.9, 2.8),
            19: (3.5, 1.4),
            20: (3.2, 1.3),
            21: (3.6, 1.1),
            22: (1.0, 3.3),
            23: (0.9, 3.4),
            24: (0.9, 3.5),
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
            13: (1.6, 1.3),
            14: (2.2, 3.6),
            15: (1.6, 1.3),
            16: (1.5, 1.2),
            17: (1.8, 1.6),
            18: (2.0, 2.8),
            19: (2.4, 3.0),
            20: (1.2, 0.9),
            21: (1.4, 1.8),
            22: (1.6, 1.3),
            23: (1.5, 1.2),
            24: (1.4, 1.1),
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
            13: (1.2, 2.6),
            14: (3.5, 1.8),
            15: (1.2, 2.7),
            16: (1.1, 2.9),
            17: (1.4, 2.1),
            18: (2.6, 2.2),
            19: (2.8, 2.0),
            20: (0.8, 1.5),
            21: (1.5, 1.5),
            22: (1.2, 2.8),
            23: (1.1, 2.9),
            24: (1.0, 3.0),
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


@dataclass
class MaintenanceWorkshop:
    """Operations Research multi-server M/M/c maintenance facility entity."""

    workshop_id: int
    name: str
    zone_id: int
    quadrant_id: int
    node_id: int
    latitude: float
    longitude: float
    capacity_bays: int
    active_bays_busy_until: list[datetime] = field(default_factory=list)
    total_vehicles_serviced: int = 0
    total_queue_wait_minutes: float = 0.0
    total_service_hours: float = 0.0

    def admit_vehicle(
        self,
        vehicle_id: int,
        arrival_time: datetime,
        service_duration_hours: float,
    ) -> tuple[datetime, datetime, float]:
        """Admit vehicle into M/M/c multi-server service queue.

        Returns:
            start_service_time: datetime when vehicle enters a mechanical bay
            completion_time: datetime when repair finishes
            wait_minutes: minutes spent in FIFO queue before entering bay
        """
        if len(self.active_bays_busy_until) < self.capacity_bays:
            # An unused bay is immediately available
            start_time = arrival_time
            wait_min = 0.0
            completion_time = start_time + timedelta(hours=service_duration_hours)
            self.active_bays_busy_until.append(completion_time)
        else:
            # All bays have had at least one vehicle; find earliest finishing bay
            earliest_free = min(self.active_bays_busy_until)
            if earliest_free <= arrival_time:
                # Bay is already freed up upon vehicle arrival
                start_time = arrival_time
                wait_min = 0.0
            else:
                # All bays occupied; vehicle waits in queue until earliest bay frees
                start_time = earliest_free
                wait_min = (start_time - arrival_time).total_seconds() / 60.0

            completion_time = start_time + timedelta(hours=service_duration_hours)
            idx = self.active_bays_busy_until.index(earliest_free)
            self.active_bays_busy_until[idx] = completion_time

        self.total_vehicles_serviced += 1
        self.total_queue_wait_minutes += wait_min
        self.total_service_hours += service_duration_hours
        return start_time, completion_time, round(wait_min, 2)


class HourlyTrafficPredsCache(dict):
    """Lazy on-demand Dijkstra predecessor cache for traffic-aware routing.

    Instead of computing Dijkstra for all 298 hubs unconditionally (costing ~2.0s per hour),
    this cache computes single-source Dijkstra on demand for only the specific hub requested
    (costing ~0.0079s), yielding a 100x speedup and 98% memory reduction.
    """

    def __init__(self, world: Any, hour: Any, csr_traffic: csr_matrix):
        super().__init__()
        self.world = world
        self.hour = hour
        self.csr_traffic = csr_traffic

    def __getitem__(self, h_idx: int) -> np.ndarray:
        if h_idx not in self:
            if h_idx < 0 or h_idx >= len(self.world.hub_node_indices):
                raise IndexError(f"Hub index {h_idx} out of range for world hubs")
            hub_node = self.world.hub_node_indices[h_idx]
            _, preds = dijkstra(self.csr_traffic, indices=[hub_node], return_predecessors=True)
            self[h_idx] = preds[0]
        return super().__getitem__(h_idx)


class HourlyTrafficDistsCache(dict):
    """Lazy on-demand Dijkstra distance cache for traffic-aware routing."""

    def __init__(self, world: Any, hour: Any, csr_traffic: csr_matrix):
        super().__init__()
        self.world = world
        self.hour = hour
        self.csr_traffic = csr_traffic

    def __getitem__(self, h_idx: int) -> np.ndarray:
        if h_idx not in self:
            if h_idx < 0 or h_idx >= len(self.world.hub_node_indices):
                raise IndexError(f"Hub index {h_idx} out of range for world hubs")
            hub_node = self.world.hub_node_indices[h_idx]
            dists = dijkstra(self.csr_traffic, indices=[hub_node], return_predecessors=False)
            self[h_idx] = dists[0]
        return super().__getitem__(h_idx)


class WorldEnvironment:
    """Encapsulates spatial layout, street network graph, and traffic physics of Managua."""

    def __init__(
        self,
        quadrants: list[Quadrant],
        zones: list[UrbanZone],
        street_network: dict[str, Any],
    ):
        self.quadrants = quadrants
        self.quadrants_map = {c.quadrant_id: c for c in self.quadrants}
        self.quadrants_centers = np.array(
            [[0.5 * (c.lat_min + c.lat_max), 0.5 * (c.lon_min + c.lon_max)] for c in self.quadrants],
            dtype=float,
        )

        self.zones = zones
        self.zones_map = {z.zone_id: z for z in self.zones}
        self.zone_quadrants: dict[int, list[Quadrant]] = {z.zone_id: [] for z in self.zones}
        for c in self.quadrants:
            if c.zone_id in self.zone_quadrants:
                self.zone_quadrants[c.zone_id].append(c)

        self.street_network = street_network
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
        self.hourly_preds_traffic_hubs: dict[int, np.ndarray] = {}
        self.hourly_dists_traffic_hubs: dict[int, np.ndarray] = {}

        if nodes_raw and edges_raw:
            self.node_coords = np.array([[n[0], n[1]] for n in nodes_raw], dtype=float)
            self.node_quadrants = np.array([n[2] for n in nodes_raw], dtype=int)
            self.node_zones = np.array([n[3] for n in nodes_raw], dtype=int)
            self.num_nodes = len(nodes_raw)

            edge_arr = np.array(edges_raw, dtype=float)
            u_idx = edge_arr[:, 0].astype(int)
            v_idx = edge_arr[:, 1].astype(int)
            lengths = edge_arr[:, 2]
            speeds = edge_arr[:, 3]
            flood_flags = edge_arr[:, 5].astype(int)
            self.edge_u_idx = u_idx
            self.edge_v_idx = v_idx
            self.edge_lengths = lengths
            self.edge_base_speeds = speeds
            self.edge_quadrants = edge_arr[:, 4].astype(int)
            self.edge_flood_flags = flood_flags

            rows = np.concatenate([u_idx, v_idx])
            cols = np.concatenate([v_idx, u_idx])
            dists = np.concatenate([lengths, lengths])
            dists_flood = np.concatenate([
                lengths * np.where(flood_flags == 1, 15.0, 1.0),
                lengths * np.where(flood_flags == 1, 15.0, 1.0),
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
            self.edge_u_idx = np.empty(0, dtype=int)
            self.edge_v_idx = np.empty(0, dtype=int)
            self.edge_lengths = np.empty(0, dtype=float)
            self.edge_base_speeds = np.empty(0, dtype=float)
            self.edge_quadrants = np.empty(0, dtype=int)
            self.edge_flood_flags = np.empty(0, dtype=int)

        # Precompute OD gravity pairs & matrices
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
                    w_map.get(zo.zone_id, (1.5, 1.5))[0] * w_map.get(zd.zone_id, (1.5, 1.5))[1]
                    for zo, zd in self.od_pairs
                ],
                dtype=float,
            ) / (zone_dists_arr ** beta)
            self.od_regime_probs[regime_name] = raw_w / raw_w.sum()

            mean_push = float(np.mean([w_map.get(z.zone_id, (1.5, 1.5))[0] for z in self.zones]))
            self.regime_origin_push_factor[regime_name] = {
                z.zone_id: round(w_map.get(z.zone_id, (1.5, 1.5))[0] / mean_push, 3) for z in self.zones
            }

        # Operations Research: Official physical maintenance workshops distributed across Managua
        self.workshops: list[MaintenanceWorkshop] = []
        raw_workshops = [
            (1, "Centro Automotriz Carretera Norte", 8, 62, 12.152, -86.218, 4),
            (2, "Taller Central MoviGo Bolonia", 6, 49, 12.132, -86.282, 4),
            (3, "AutoServicio Masaya MoviGo", 1, 18, 12.102, -86.242, 3),
        ]
        for wid, wname, zid, qid, wlat, wlon, bays in raw_workshops:
            wnode = 0
            if len(self.node_coords) > 0:
                dists_sq = (self.node_coords[:, 0] - wlat) ** 2 + (self.node_coords[:, 1] - wlon) ** 2
                wnode = int(np.argmin(dists_sq))
            self.workshops.append(
                MaintenanceWorkshop(
                    workshop_id=wid,
                    name=wname,
                    zone_id=zid,
                    quadrant_id=qid,
                    node_id=wnode,
                    latitude=wlat,
                    longitude=wlon,
                    capacity_bays=bays,
                )
            )

    def find_closest_workshop(self, lat: float, lon: float) -> MaintenanceWorkshop:
        """Find the spatially closest official maintenance workshop."""
        return min(
            self.workshops,
            key=lambda w: haversine_km(lat, lon, w.latitude, w.longitude),
        )

    def sample_origin_destination_zones(
        self, hour: int, dow: int, rng: np.random.Generator
    ) -> tuple[UrbanZone, UrbanZone]:
        """Sample (origin_zone, destination_zone) from the active time-of-day Gravity OD matrix."""
        regime = get_gravity_regime_name(hour, dow)
        probs = self.od_regime_probs[regime]
        pair_idx = int(rng.choice(len(self.od_pairs), p=probs))
        return self.od_pairs[pair_idx]

    def sample_street_coordinate(
        self, zone: UrbanZone, rng: np.random.Generator
    ) -> tuple[float, float, int, bool, int]:
        """Sample a GPS coordinate strictly on a drivable street within an active square quadrant."""
        candidate_quads = self.zone_quadrants.get(zone.zone_id) or self.quadrants
        quad_list = [q for q in candidate_quads if len(self.quadrant_streets.get(q.quadrant_id, [])) > 0]
        if not quad_list:
            quad_list = [q for q in self.quadrants if len(self.quadrant_streets.get(q.quadrant_id, [])) > 0]
        if not quad_list:
            quad_list = candidate_quads

        q_idx = int(rng.integers(0, len(quad_list)))
        quad = quad_list[q_idx]

        segs = self.quadrant_streets.get(quad.quadrant_id)
        flags = self.quadrant_flood_flags.get(quad.quadrant_id)
        q_node_idxs = self.quad_node_indices.get(str(quad.quadrant_id), [])

        if segs is not None and len(segs) > 0:
            idx = int(rng.integers(0, len(segs)))
            lat1, lon1, lat2, lon2 = segs[idx]
            t = float(rng.uniform(0.0, 1.0))
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
                hub_idx = self.hub_node_indices[
                    self.qid_to_hub_idx.get(quad.quadrant_id, 0)
                ]
                best_node = hub_idx if len(self.node_coords) > hub_idx else 0
            else:
                best_node = 0
            return lat, lon, quad.quadrant_id, is_flood_street, best_node

        clat = round(0.5 * (quad.lat_min + quad.lat_max), 6)
        clon = round(0.5 * (quad.lon_min + quad.lon_max), 6)
        return clat, clon, quad.quadrant_id, (quad.flood_risk == "critico"), 0

    def snap_to_nearest_street_and_quadrant(
        self,
        target_lat: float,
        target_lon: float,
        fallback_zone: UrbanZone,
        rng: np.random.Generator,
    ) -> tuple[float, float, int, int]:
        """Snap an arbitrary waypoint coordinate onto the nearest real street inside a square quadrant."""
        d2 = (self.quadrants_centers[:, 0] - target_lat) ** 2 + (
            self.quadrants_centers[:, 1] - target_lon
        ) ** 2
        nearest_q_idx = int(np.argmin(d2))
        quad = self.quadrants[nearest_q_idx]
        segs = self.quadrant_streets.get(quad.quadrant_id)
        if segs is not None and len(segs) > 0:
            seg_idx = int(rng.integers(0, len(segs)))
            lat1, lon1, lat2, lon2 = segs[seg_idx]
            t = float(rng.uniform(0.15, 0.85))
            lat = round(float(np.clip(lat1 + t * (lat2 - lat1), quad.lat_min, quad.lat_max)), 6)
            lon = round(float(np.clip(lon1 + t * (lon2 - lon1), quad.lon_min, quad.lon_max)), 6)
            return lat, lon, quad.zone_id, quad.quadrant_id

        lat, lon, qid, _, _ = self.sample_street_coordinate(fallback_zone, rng)
        return lat, lon, fallback_zone.zone_id, qid

    def update_hourly_traffic(
        self,
        hour: Any,
        quadrant_congestions: np.ndarray | dict[int, float],
    ) -> None:
        """Dynamically compute and cache traffic-aware Dijkstra hub predecessor matrices for the given hour.

        Uses the Unified Cost Function:
        cost = (length / effective_speed) * flood_penalty
        where effective_speed = max(5.0, base_speed / quadrant_congestion).
        """
        if self.num_nodes == 0 or len(self.hub_node_indices) == 0:
            return
        if hour in self.hourly_preds_traffic_hubs:
            return

        # Cap cache size to 24 hourly tables to keep RAM usage lean (~17 MB per matrix)
        if len(self.hourly_preds_traffic_hubs) >= 24:
            oldest_key = next(iter(self.hourly_preds_traffic_hubs))
            self.hourly_preds_traffic_hubs.pop(oldest_key, None)
            self.hourly_dists_traffic_hubs.pop(oldest_key, None)

        if isinstance(quadrant_congestions, dict):
            cong_map = quadrant_congestions
            edge_congs = np.array(
                [cong_map.get(int(q), 1.0) for q in self.edge_quadrants], dtype=float
            )
        else:
            cong_arr = np.asarray(quadrant_congestions, dtype=float)
            q_indices = np.clip(self.edge_quadrants - 1, 0, len(cong_arr) - 1)
            edge_congs = cong_arr[q_indices]

        eff_speeds = np.maximum(5.0, self.edge_base_speeds / np.maximum(1.0, edge_congs))
        travel_times = self.edge_lengths / eff_speeds
        flood_penalties = np.where(self.edge_flood_flags == 1, 15.0, 1.0)
        costs = travel_times * flood_penalties

        rows = np.concatenate([self.edge_u_idx, self.edge_v_idx])
        cols = np.concatenate([self.edge_v_idx, self.edge_u_idx])
        weights = np.concatenate([costs, costs])

        csr_traffic = csr_matrix((weights, (rows, cols)), shape=(self.num_nodes, self.num_nodes))
        self.hourly_preds_traffic_hubs[hour] = HourlyTrafficPredsCache(self, hour, csr_traffic)
        self.hourly_dists_traffic_hubs[hour] = HourlyTrafficDistsCache(self, hour, csr_traffic)

    def get_osm_route(
        self,
        origin_node_idx: int,
        dest_node_idx: int,
        origin_qid: int,
        dest_qid: int,
        is_flood_aware: bool = False,
        is_traffic_aware: bool = False,
        hour: int | None = None,
        is_perturbed: bool = False,
        rng: np.random.Generator | None = None,
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
        if is_traffic_aware and hour is not None and hour in self.hourly_preds_traffic_hubs:
            preds = self.hourly_preds_traffic_hubs[hour][h_idx]
        elif is_flood_aware:
            preds = self.preds_flood_hubs[h_idx]
        else:
            preds = self.preds_norm_hubs[h_idx]

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
        a = np.sin(dp / 2.0) ** 2 + math.cos(0.0) * np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
        dists = 2.0 * 6371.0 * np.arcsin(np.minimum(1.0, np.sqrt(a)))
        raw_km = float(np.sum(dists))

        if rng is not None:
            circuity = (
                float(rng.uniform(1.08, 1.22))
                if is_perturbed
                else float(rng.uniform(1.02, 1.06))
            )
        else:
            circuity = 1.15 if is_perturbed else 1.04
        route_km = round(max(0.65, max(raw_km * circuity, hav * 1.15)), 2)
        return path_nodes, route_km

    def is_route_affected_by_overflow(
        self,
        path_nodes: list[int],
        overflow_quads: set[int] | None = None,
    ) -> bool:
        """Check if any node or segment in path_nodes is inside an overflowing cauce quadrant."""
        if not overflow_quads or not path_nodes or len(self.node_quadrants) == 0:
            return False
        path_q = self.node_quadrants[path_nodes]
        return bool(np.any(np.isin(path_q, list(overflow_quads))))

    def estimate_distance_and_duration(
        self,
        lat_o: float,
        lon_o: float,
        lat_d: float,
        lon_d: float,
        congestion_idx: float,
        rng: np.random.Generator,
        effective_water_mm: float = 0.0,
        flood_affected_route: bool = False,
        raw_route_km: float | None = None,
        is_suboptimal: bool = False,
        is_cauce_overflow: bool = False,
    ) -> tuple[float, float, bool]:
        """Calculate road distance and duration from real OpenStreetMap route trajectory with flood/traffic physics."""
        hav_km = haversine_km(lat_o, lon_o, lat_d, lon_d)

        if raw_route_km is not None and raw_route_km > 0.0:
            base_km = raw_route_km
        else:
            base_km = max(0.65, hav_km * 1.25)

        subopt = bool(is_suboptimal or flood_affected_route or is_cauce_overflow or (rng.random() < 0.16))
        if is_cauce_overflow:
            # Severe detour around overflowing cauce corridor / impassable vados
            detour_factor = float(rng.uniform(1.25, 1.58))
        elif flood_affected_route:
            detour_factor = float(rng.uniform(1.15, 1.45))
        elif subopt:
            detour_factor = float(rng.uniform(1.10, 1.28))
        else:
            detour_factor = float(rng.uniform(1.02, 1.08))

        dist_km = round(max(0.65, max(base_km * detour_factor, hav_km * 1.15)), 2)

        if is_cauce_overflow:
            # Crawling speed through floodwaters or detoured chokepoints
            effective_speed_kmh = float(rng.uniform(4.5, 9.0))
        elif flood_affected_route:
            effective_speed_kmh = float(rng.uniform(6.5, 13.0))
        else:
            rain_speed_penalty = 1.0 + 0.022 * effective_water_mm
            effective_speed_kmh = max(8.5, 32.0 / (congestion_idx * rain_speed_penalty))

        base_delay = 3.0 if is_cauce_overflow else 1.0
        duration_min = round(
            max(2.5, (dist_km / effective_speed_kmh) * 60.0 + float(rng.uniform(base_delay, base_delay + 3.0))),
            2,
        )
        return dist_km, duration_min, subopt
