"""Physical world environment for MoviGo simulation.

Manages the Managua urban environment:
- OpenStreetMap dense street network topology (nodes, edges, CSR matrices).
- Dijkstra shortest path and weather-aware route reconstruction.
- Origin-Destination Gravity Model regimes across the 12 urban zones and 92 quadrants.
- Real coordinate sampling, street snapping, and flood/traffic physics.
"""

from __future__ import annotations

import math
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
        quad_list = self.zone_quadrants.get(zone.zone_id) or self.quadrants
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

    def get_osm_route(
        self,
        origin_node_idx: int,
        dest_node_idx: int,
        origin_qid: int,
        dest_qid: int,
        is_flood_aware: bool = False,
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
    ) -> tuple[float, float, bool]:
        """Calculate road distance and duration from real OpenStreetMap route trajectory with flood/traffic physics."""
        hav_km = haversine_km(lat_o, lon_o, lat_d, lon_d)

        if raw_route_km is not None and raw_route_km > 0.0:
            base_km = raw_route_km
        else:
            base_km = max(0.65, hav_km * 1.25)

        subopt = bool(is_suboptimal or flood_affected_route or (rng.random() < 0.16))
        if flood_affected_route:
            detour_factor = float(rng.uniform(1.15, 1.45))
        elif subopt:
            detour_factor = float(rng.uniform(1.10, 1.28))
        else:
            detour_factor = float(rng.uniform(1.02, 1.08))

        dist_km = round(max(0.65, max(base_km * detour_factor, hav_km * 1.15)), 2)

        if flood_affected_route:
            effective_speed_kmh = float(rng.uniform(5.5, 12.0))
        else:
            rain_speed_penalty = 1.0 + 0.022 * effective_water_mm
            effective_speed_kmh = max(8.5, 32.0 / (congestion_idx * rain_speed_penalty))

        duration_min = round(
            max(2.5, (dist_km / effective_speed_kmh) * 60.0 + float(rng.uniform(1.0, 3.0))),
            2,
        )
        return dist_km, duration_min, subopt
