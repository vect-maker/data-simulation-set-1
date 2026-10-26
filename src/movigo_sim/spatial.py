"""Deterministic spatial & street-network builder for MoviGo (Managua, Nicaragua).

Encapsulates 100% reproducible, code-driven generation of:
- urban_zones.json (12 Managua urban pricing and mobility zones)
- quadrants.json (92 contiguous ~0.88 km x 0.88 km square grid cells grouped by zone_id)
- managua_street_network.json (OpenStreetMap drivable street segments indexed per zone and per square quadrant)
"""

import json
import logging
import math
from pathlib import Path
from typing import Any
import numpy as np
import requests

from movigo_sim.config import DETERMINISTIC_SEEDS_DIR
from movigo_sim.models import Quadrant, UrbanZone

logger = logging.getLogger(__name__)

# Canonical deterministic specification of Managua's 12 urban pricing zones
CANONICAL_URBAN_ZONES: list[dict[str, Any]] = [
    {
        "zone_id": 1,
        "zone_name": "Villa Fontana",
        "socioeconomic_stratum": "alto",
        "latitude": 12.115,
        "longitude": -86.255,
        "coverage_radius_km": 2.5,
        "base_flag_drop_fare": 70.0,
    },
    {
        "zone_id": 2,
        "zone_name": "Las Colinas",
        "socioeconomic_stratum": "alto",
        "latitude": 12.105,
        "longitude": -86.242,
        "coverage_radius_km": 3.0,
        "base_flag_drop_fare": 75.0,
    },
    {
        "zone_id": 3,
        "zone_name": "Santo Domingo",
        "socioeconomic_stratum": "alto",
        "latitude": 12.1,
        "longitude": -86.23,
        "coverage_radius_km": 2.8,
        "base_flag_drop_fare": 80.0,
    },
    {
        "zone_id": 4,
        "zone_name": "Los Robles",
        "socioeconomic_stratum": "medio",
        "latitude": 12.128,
        "longitude": -86.265,
        "coverage_radius_km": 2.0,
        "base_flag_drop_fare": 55.0,
    },
    {
        "zone_id": 5,
        "zone_name": "Altamira",
        "socioeconomic_stratum": "medio",
        "latitude": 12.133,
        "longitude": -86.25,
        "coverage_radius_km": 2.0,
        "base_flag_drop_fare": 50.0,
    },
    {
        "zone_id": 6,
        "zone_name": "Bolonia",
        "socioeconomic_stratum": "medio",
        "latitude": 12.145,
        "longitude": -86.28,
        "coverage_radius_km": 2.2,
        "base_flag_drop_fare": 55.0,
    },
    {
        "zone_id": 7,
        "zone_name": "Bello Horizonte",
        "socioeconomic_stratum": "medio",
        "latitude": 12.138,
        "longitude": -86.22,
        "coverage_radius_km": 3.5,
        "base_flag_drop_fare": 48.0,
    },
    {
        "zone_id": 8,
        "zone_name": "Linda Vista",
        "socioeconomic_stratum": "medio",
        "latitude": 12.155,
        "longitude": -86.3,
        "coverage_radius_km": 3.0,
        "base_flag_drop_fare": 50.0,
    },
    {
        "zone_id": 9,
        "zone_name": "Metrocentro / Eje Corporativo UCA",
        "socioeconomic_stratum": "comercial",
        "latitude": 12.12,
        "longitude": -86.27,
        "coverage_radius_km": 1.5,
        "base_flag_drop_fare": 60.0,
    },
    {
        "zone_id": 10,
        "zone_name": "Ciudad Jardín",
        "socioeconomic_stratum": "popular",
        "latitude": 12.14,
        "longitude": -86.258,
        "coverage_radius_km": 2.0,
        "base_flag_drop_fare": 40.0,
    },
    {
        "zone_id": 11,
        "zone_name": "Mercado Oriental",
        "socioeconomic_stratum": "popular",
        "latitude": 12.135,
        "longitude": -86.245,
        "coverage_radius_km": 2.5,
        "base_flag_drop_fare": 35.0,
    },
    {
        "zone_id": 12,
        "zone_name": "Mercado Roberto Huembes",
        "socioeconomic_stratum": "popular",
        "latitude": 12.125,
        "longitude": -86.238,
        "coverage_radius_km": 2.5,
        "base_flag_drop_fare": 38.0,
    },
]

CANONICAL_ZONAS_URBANAS = CANONICAL_URBAN_ZONES

# Real-world hydrological flood & cauce bottlenecks in Managua
FLOOD_HOTSPOTS: list[dict[str, Any]] = [
    {"name": "Cauce Oriental / Gancho de Camino", "lat": 12.1425, "lon": -86.2480, "radius_km": 0.95},
    {"name": "Puente El Paraisito / Ciudad Jardín", "lat": 12.1390, "lon": -86.2540, "radius_km": 0.75},
    {"name": "Paso a Desnivel Rubenia / Cauce El Dorado", "lat": 12.1295, "lon": -86.2355, "radius_km": 0.90},
    {"name": "Rotonda La Virgen / Cauce Bello Horizonte", "lat": 12.1395, "lon": -86.2185, "radius_km": 1.00},
    {"name": "Pista El Mayoreo / Sabana Grande", "lat": 12.1340, "lon": -86.2080, "radius_km": 0.90},
    {"name": "Cauce Occidental / Linda Vista Sur", "lat": 12.1495, "lon": -86.2925, "radius_km": 0.90},
    {"name": "Rotonda Centroamérica / Pista Juan Pablo II", "lat": 12.1190, "lon": -86.2650, "radius_km": 0.70},
]

ZONE_CAUCES: dict[int, str] = {
    1: "Cauce Central Villa Fontana / Club Terraza",
    2: "Cuenca Sur Las Colinas / Carretera a Masaya Km 8",
    3: "Cabecera Sierras de Santo Domingo / Las Sierritas",
    4: "Eje Pista Juan Pablo II / Los Robles",
    5: "Cauce Altamira / Pista Suburbana",
    6: "Canal Pluvial Bolonia / Plaza España",
    7: "Cauce Bello Horizonte / Rotonda La Virgen / Pista El Mayoreo",
    8: "Cauce Occidental / Linda Vista / Gadala Maria",
    9: "Rotonda Rubén Darío / Rotonda Centroamérica / Eje UCA",
    10: "Cauce Oriental / Puente El Paraisito / Ciudad Jardín",
    11: "Colector Cauce Oriental / Gancho de Camino / Mercado Oriental",
    12: "Cauce El Dorado / Paso a Desnivel Rubenia / Roberto Huembes",
}

DRIVABLE_HIGHWAY_TYPES = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two WGS84 coordinates."""
    r_earth = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * r_earth * math.asin(min(1.0, math.sqrt(a)))


def build_deterministic_urban_zones() -> list[dict[str, Any]]:
    """Return a deep copy of the 12 canonical Managua urban zones."""
    return [dict(z) for z in CANONICAL_URBAN_ZONES]


build_deterministic_zonas_urbanas = build_deterministic_urban_zones


def fetch_osm_street_network_for_zones(zones: list[dict[str, Any]]) -> dict[str, Any]:
    """Fetch real drivable street segments from OpenStreetMap API v0.6 for all 12 Managua zones."""
    zone_segments: dict[str, list[list[float]]] = {}
    arterials: list[list[float]] = []
    rng = np.random.default_rng(42)

    for z in zones:
        zid = str(z["zone_id"])
        lat_c = z["latitude"]
        lon_c = z["longitude"]
        r_deg = min(0.015, (z["coverage_radius_km"] / 111.0) * 0.85)
        bbox = f"{lon_c - r_deg:.5f},{lat_c - r_deg:.5f},{lon_c + r_deg:.5f},{lat_c + r_deg:.5f}"
        url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={bbox}"
        resp = requests.get(url, headers={"User-Agent": "cs-datos-simulations/1.0"}, timeout=25)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])

        nodes = {el["id"]: (el["lat"], el["lon"]) for el in elements if el.get("type") == "node"}
        segs = []
        for el in elements:
            if el.get("type") == "way":
                hw = el.get("tags", {}).get("highway")
                if hw in DRIVABLE_HIGHWAY_TYPES:
                    nids = el.get("nodes", [])
                    for k in range(len(nids) - 1):
                        if nids[k] in nodes and nids[k + 1] in nodes:
                            lat1, lon1 = nodes[nids[k]]
                            lat2, lon2 = nodes[nids[k + 1]]
                            seg = [round(lat1, 6), round(lon1, 6), round(lat2, 6), round(lon2, 6)]
                            segs.append(seg)
                            if hw in {"trunk", "primary", "secondary", "tertiary"}:
                                arterials.append(seg)

        if len(segs) > 450:
            idxs = sorted(rng.choice(len(segs), size=450, replace=False))
            segs = [segs[i] for i in idxs]
        zone_segments[zid] = segs

    if len(arterials) > 1500:
        idxs = sorted(rng.choice(len(arterials), size=1500, replace=False))
        arterials = [arterials[i] for i in idxs]

    return {"zones": zone_segments, "arterials": arterials}


def build_deterministic_quadrants_and_street_index(
    zones: list[dict[str, Any]],
    base_network: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deterministically build the 92 contiguous square Quadrants and index all street segments."""
    all_segs = []
    for zid, segs in base_network.get("zones", {}).items():
        for seg in segs:
            all_segs.append(seg)
    for seg in base_network.get("arterials", []):
        all_segs.append(seg)

    unique_segs = list({tuple(round(float(x), 6) for x in s) for s in all_segs})
    unique_segs.sort()

    dense_pts = []
    for lat1, lon1, lat2, lon2 in unique_segs:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            dense_pts.append((lon1 + t * (lon2 - lon1), lat1 + t * (lat2 - lat1)))
    dense_pts_arr = np.array(dense_pts)

    cell_size = 0.008  # ~0.88 km x 0.88 km square grid cells
    lon_grid = np.round(np.arange(-86.316, -86.204, cell_size), 6)
    lat_grid = np.round(np.arange(12.086, 12.166, cell_size), 6)

    ny = len(lat_grid)
    nx = len(lon_grid)
    active = np.zeros((ny, nx), dtype=bool)

    for j, lat0 in enumerate(lat_grid):
        for i, lon0 in enumerate(lon_grid):
            lat1 = round(float(lat0 + cell_size), 6)
            lon1 = round(float(lon0 + cell_size), 6)
            clat = 0.5 * (lat0 + lat1)
            clon = 0.5 * (lon0 + lon1)
            in_cell = (
                (dense_pts_arr[:, 0] >= lon0)
                & (dense_pts_arr[:, 0] <= lon1)
                & (dense_pts_arr[:, 1] >= lat0)
                & (dense_pts_arr[:, 1] <= lat1)
            )
            min_d = min(haversine_km(clat, clon, z["latitude"], z["longitude"]) for z in zones)
            if np.sum(in_cell) >= 3 and min_d <= 2.15:
                active[j, i] = True

    # Fill interior pockets with >= 3 active orthogonal neighbors so the city grid has zero holes
    for _ in range(2):
        for j in range(1, ny - 1):
            for i in range(1, nx - 1):
                if not active[j, i]:
                    nbrs = (
                        int(active[j - 1, i])
                        + int(active[j + 1, i])
                        + int(active[j, i - 1])
                        + int(active[j, i + 1])
                    )
                    if nbrs >= 3:
                        active[j, i] = True

    quadrants: list[dict[str, Any]] = []
    quadrant_streets: dict[str, list[list[float]]] = {}
    quadrant_flood_flags: dict[str, list[int]] = {}
    cell_id = 1

    for j, lat0 in enumerate(lat_grid):
        for i, lon0 in enumerate(lon_grid):
            if not active[j, i]:
                continue
            lat0_f = round(float(lat0), 6)
            lat1_f = round(float(lat0 + cell_size), 6)
            lon0_f = round(float(lon0), 6)
            lon1_f = round(float(lon0 + cell_size), 6)
            clat = round(0.5 * (lat0_f + lat1_f), 6)
            clon = round(0.5 * (lon0_f + lon1_f), 6)

            best_z = min(
                zones,
                key=lambda z: haversine_km(clat, clon, z["latitude"], z["longitude"])
                / (z["coverage_radius_km"] ** 0.35),
            )
            zid = int(best_z["zone_id"])
            zname = str(best_z["zone_name"])

            norm_south = max(0.0, min(1.0, (12.164 - clat) / (12.164 - 12.086)))
            alt_masl = int(round(46.0 + 195.0 * (norm_south ** 1.38)))

            nearest_hotspot = min(
                FLOOD_HOTSPOTS, key=lambda h: haversine_km(clat, clon, h["lat"], h["lon"])
            )
            dist_hotspot = haversine_km(clat, clon, nearest_hotspot["lat"], nearest_hotspot["lon"])

            if dist_hotspot <= nearest_hotspot["radius_km"] * 0.78 or (
                alt_masl <= 66 and zid in (7, 10, 11)
            ):
                risk = "critico"
                cauce_desc = nearest_hotspot["name"]
            elif dist_hotspot <= nearest_hotspot["radius_km"] * 1.25 or alt_masl <= 82:
                risk = "alto"
                cauce_desc = nearest_hotspot["name"] if dist_hotspot <= 1.2 else ZONE_CAUCES[zid]
            elif alt_masl <= 135:
                risk = "medio"
                cauce_desc = ZONE_CAUCES[zid]
            else:
                risk = "bajo"
                cauce_desc = ZONE_CAUCES[zid]

            code = f"Q{cell_id:02d}-Z{zid:02d}"
            name = f"{zname} - Cuadrante Q{cell_id:02d} (F{j+1}C{i+1})"

            quadrants.append(
                {
                    "quadrant_id": cell_id,
                    "zone_id": zid,
                    "quadrant_code": code,
                    "quadrant_name": name,
                    "grid_row": int(j),
                    "grid_col": int(i),
                    "lat_min": lat0_f,
                    "lat_max": lat1_f,
                    "lon_min": lon0_f,
                    "lon_max": lon1_f,
                    "mean_altitude_masl": alt_masl,
                    "flood_risk": risk,
                    "main_drainage_channels": cauce_desc,
                }
            )

            cell_segs = []
            cell_flags = []
            for s_lat1, s_lon1, s_lat2, s_lon2 in unique_segs:
                mlat = 0.5 * (s_lat1 + s_lat2)
                mlon = 0.5 * (s_lon1 + s_lon2)
                if (lat0_f <= mlat <= lat1_f) and (lon0_f <= mlon <= lon1_f):
                    c_lat1 = round(min(max(s_lat1, lat0_f + 0.0001), lat1_f - 0.0001), 6)
                    c_lon1 = round(min(max(s_lon1, lon0_f + 0.0001), lon1_f - 0.0001), 6)
                    c_lat2 = round(min(max(s_lat2, lat0_f + 0.0001), lat1_f - 0.0001), 6)
                    c_lon2 = round(min(max(s_lon2, lon0_f + 0.0001), lon1_f - 0.0001), 6)
                    is_fl = any(
                        haversine_km(mlat, mlon, h["lat"], h["lon"]) <= h["radius_km"]
                        for h in FLOOD_HOTSPOTS
                    )
                    cell_segs.append([c_lat1, c_lon1, c_lat2, c_lon2])
                    cell_flags.append(1 if (is_fl or risk == "critico") else 0)

            if len(cell_segs) < 3:
                sorted_nearby = sorted(
                    unique_segs,
                    key=lambda s: (0.5 * (s[0] + s[2]) - clat) ** 2
                    + (0.5 * (s[1] + s[3]) - clon) ** 2,
                )[:8]
                for s_lat1, s_lon1, s_lat2, s_lon2 in sorted_nearby:
                    dlat = s_lat2 - s_lat1
                    dlon = s_lon2 - s_lon1
                    c_lat1 = round(
                        min(max(clat - 0.35 * dlat, lat0_f + 0.0005), lat1_f - 0.0005), 6
                    )
                    c_lon1 = round(
                        min(max(clon - 0.35 * dlon, lon0_f + 0.0005), lon1_f - 0.0005), 6
                    )
                    c_lat2 = round(
                        min(max(clat + 0.35 * dlat, lat0_f + 0.0005), lat1_f - 0.0005), 6
                    )
                    c_lon2 = round(
                        min(max(clon + 0.35 * dlon, lon0_f + 0.0005), lon1_f - 0.0005), 6
                    )
                    cell_segs.append([c_lat1, c_lon1, c_lat2, c_lon2])
                    cell_flags.append(1 if risk in ("critico", "alto") else 0)

            quadrant_streets[str(cell_id)] = cell_segs[:120]
            quadrant_flood_flags[str(cell_id)] = cell_flags[:120]
            cell_id += 1

    zone_flood_flags: dict[str, list[int]] = {}
    for zid, segs in base_network.get("zones", {}).items():
        flags = []
        for seg in segs:
            mlat = 0.5 * (seg[0] + seg[2])
            mlon = 0.5 * (seg[1] + seg[3])
            is_fl = any(
                haversine_km(mlat, mlon, h["lat"], h["lon"]) <= h["radius_km"]
                for h in FLOOD_HOTSPOTS
            )
            flags.append(1 if is_fl else 0)
        zone_flood_flags[zid] = flags

    enriched_network = {
        "zones": base_network.get("zones", {}),
        "arterials": base_network.get("arterials", []),
        "zone_flood_flags": zone_flood_flags,
        "quadrant_streets": quadrant_streets,
        "quadrant_flood_flags": quadrant_flood_flags,
    }
    return quadrants, enriched_network


build_deterministic_cuadrantes_and_street_index = build_deterministic_quadrants_and_street_index


def generate_deterministic_spatial_seeds(
    output_dir: Path = DETERMINISTIC_SEEDS_DIR,
    fetch_osm: bool = False,
    dry_run: bool = False,
) -> tuple[list[UrbanZone], list[Quadrant], dict[str, Any]]:
    """Deterministically generate and save urban_zones.json, quadrants.json, and managua_street_network.json."""
    zones_dicts = build_deterministic_urban_zones()
    net_path = output_dir / "managua_street_network.json"

    if fetch_osm or not net_path.exists():
        logger.info("Fetching drivable street segments from OpenStreetMap API v0.6 for Managua...")
        base_net = fetch_osm_street_network_for_zones(zones_dicts)
    else:
        with open(net_path, encoding="utf-8") as f:
            base_net = json.load(f)

    quadrants_dicts, enriched_net = build_deterministic_quadrants_and_street_index(
        zones_dicts, base_net
    )

    zones_models = [UrbanZone(**z) for z in zones_dicts]
    quadrants_models = [Quadrant(**q) for q in quadrants_dicts]

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "urban_zones.json", "w", encoding="utf-8") as f:
            json.dump(zones_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "quadrants.json", "w", encoding="utf-8") as f:
            json.dump(quadrants_dicts, f, indent=2, ensure_ascii=False)
        with open(net_path, "w", encoding="utf-8") as f:
            json.dump(enriched_net, f, separators=(",", ":"))

    return zones_models, quadrants_models, enriched_net
