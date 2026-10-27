"""Deterministic spatial, street-network, and population catalog builder for MoviGo (Managua, Nicaragua).

Encapsulates 100% reproducible, code-driven generation of:
- urban_zones.json (12 Managua urban pricing and mobility zones)
- quadrants.json (92 contiguous ~0.88 km x 0.88 km square grid cells grouped by zone_id)
- managua_street_network.json (OpenStreetMap drivable street segments indexed per zone and per square quadrant)
- users.json (800 registered passenger profiles with realistic registration dates and payment preferences)
- drivers.json (150 registered driver profiles with ratings, acceptance rates, and statuses)
- vehicles.json (150 1:1 vehicles registered in Managua with service tiers and M-XXXXXX plates)
"""

import json
import logging
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import numpy as np
import requests

from movigo_sim.config import DETERMINISTIC_SEEDS_DIR, SIMULATION_SEED
from movigo_sim.models import DrainageChannel, Driver, Quadrant, UrbanZone, User, Vehicle

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

def extract_osm_waterways(
    raw_osm_elements: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], np.ndarray, list[dict[str, Any]]]:
    """Extract authentic OpenStreetMap waterways, vector LineString features, and line segments.

    Returns:
    - features: list of GeoJSON Feature dicts with LineString geometry and OSM tags.
    - seg_arr: np.ndarray of shape (S, 4) [y1, x1, y2, x2] in km projected space.
    - seg_meta: list of dicts with name, waterway_type, osm_id, is_named.
    """
    raw_nodes = {
        el["id"]: (round(el["lat"], 6), round(el["lon"], 6))
        for el in raw_osm_elements
        if el.get("type") == "node"
    }
    water_ways = [
        el for el in raw_osm_elements
        if el.get("type") == "way" and "waterway" in el.get("tags", {})
    ]

    features: list[dict[str, Any]] = []
    seg_list: list[tuple[float, float, float, float]] = []
    seg_meta: list[dict[str, Any]] = []

    for w in water_ways:
        tags = w.get("tags", {})
        osm_name = tags.get("name")
        w_nodes = w.get("nodes", [])
        coords = [raw_nodes[nid] for nid in w_nodes if nid in raw_nodes]
        if len(coords) < 2:
            continue
        default_name = osm_name or f"Canal de Drenaje Pluvial #{w['id']}"

        # GeoJSON uses [lon, lat]
        geo_coords = [[c[1], c[0]] for c in coords]
        features.append({
            "type": "Feature",
            "id": w["id"],
            "geometry": {"type": "LineString", "coordinates": geo_coords},
            "properties": {
                "osm_id": w["id"],
                "name": default_name,
                "waterway": tags.get("waterway", "drain"),
                "is_named": bool(osm_name),
            },
        })

        for k in range(len(coords) - 1):
            lat1, lon1 = coords[k]
            lat2, lon2 = coords[k + 1]
            seg_list.append((lat1 * 111.0, lon1 * 108.5, lat2 * 111.0, lon2 * 108.5))
            seg_meta.append({
                "name": default_name,
                "waterway": tags.get("waterway", "drain"),
                "osm_id": w["id"],
                "is_named": bool(osm_name),
            })

    seg_arr = np.array(seg_list, dtype=float) if seg_list else np.empty((0, 4), dtype=float)
    return features, seg_arr, seg_meta


def build_deterministic_drainage_channels(
    raw_osm_elements: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build authentic 3NF drainage channel records derived directly from OpenStreetMap hydrography."""
    if raw_osm_elements is None:
        cache_path = DETERMINISTIC_SEEDS_DIR / "managua_osm_raw.json"
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                raw_osm_elements = json.load(f)
        else:
            raw_osm_elements = []

    raw_nodes = {
        el["id"]: (round(el["lat"], 6), round(el["lon"], 6))
        for el in raw_osm_elements
        if el.get("type") == "node"
    }
    from collections import defaultdict
    corridors: dict[str, list[Any]] = defaultdict(list)

    for el in raw_osm_elements:
        if el.get("type") == "way" and "waterway" in el.get("tags", {}):
            tags = el.get("tags", {})
            name = tags.get("name")
            coords = [raw_nodes[nid] for nid in el.get("nodes", []) if nid in raw_nodes]
            if len(coords) >= 2 and name:
                corridors[name].append((el["id"], coords, tags))

    vulnerability_rules = {
        "Cauce Oriental": "critico",
        "Cauce Occidental": "critico",
        "Interceptora Tiscapa": "alto",
        "Cauce Cuajachillo": "alto",
        "Cauce Pochocuape": "alto",
        "Cauce Altamira": "medio",
        "Cauce Camino de Bolas": "medio",
        "Cauce Santo Domingo": "medio",
        "Túnel Interceptor Santo Domingo": "medio",
        "Cauce Las Cuarezmas": "medio",
        "Cauce Los Cuarezmas": "medio",
        "Cauce Cuarezmas Oeste": "medio",
        "Quebrada de Pochocuape": "bajo",
        "Canal Desague Agua Pluviales Sta María de la Victoria": "bajo",
    }

    channels: list[dict[str, Any]] = []
    chan_id = 1
    for name, ways in sorted(corridors.items(), key=lambda x: len(x[1]), reverse=True):
        all_pts = [pt for w in ways for pt in w[1]]
        c_lat = round(float(np.mean([p[0] for p in all_pts])), 6)
        c_lon = round(float(np.mean([p[1] for p in all_pts])), 6)
        tot_len = sum(
            haversine_km(w[1][k][0], w[1][k][1], w[1][k + 1][0], w[1][k + 1][1])
            for w in ways
            for k in range(len(w[1]) - 1)
        )
        best_z = min(
            CANONICAL_URBAN_ZONES,
            key=lambda z: haversine_km(c_lat, c_lon, z["latitude"], z["longitude"]),
        )
        vuln = vulnerability_rules.get(name, "medio")
        flow_dir = "Sur a Norte (hacia Lago Xolotlán)" if c_lat > 12.11 else "Suroeste a Noreste (cuenca media-alta)"

        channels.append({
            "channel_id": chan_id,
            "channel_name": name,
            "zone_id": best_z["zone_id"],
            "latitude": c_lat,
            "longitude": c_lon,
            "critical_radius_km": round(max(0.40, min(1.20, tot_len * 0.15)), 2),
            "vulnerability_level": vuln,
            "flow_direction": flow_dir,
        })
        chan_id += 1

    return channels

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

HIGHWAY_BASE_SPEEDS: dict[str, float] = {
    "motorway": 55.0,
    "motorway_link": 45.0,
    "trunk": 50.0,
    "trunk_link": 40.0,
    "primary": 45.0,
    "primary_link": 35.0,
    "secondary": 38.0,
    "secondary_link": 30.0,
    "tertiary": 30.0,
    "tertiary_link": 25.0,
    "residential": 22.0,
    "unclassified": 24.0,
}

HIGHWAY_CLASSES = sorted(list(DRIVABLE_HIGHWAY_TYPES))
HW_TO_IDX = {hw: i for i, hw in enumerate(HIGHWAY_CLASSES)}


def clip_segment_liang_barsky(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> tuple[float, float, float, float] | None:
    """Exact Liang-Barsky parametric 2D line clipping to an axis-aligned bounding box.

    Guarantees that the clipped segment is strictly collinear with the raw OpenStreetMap way
    with zero geometric bending or artificial axis clamping.
    """
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    p = [-dlat, dlat, -dlon, dlon]
    q = [lat1 - lat_min, lat_max - lat1, lon1 - lon_min, lon_max - lon1]
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return None
        else:
            t = qi / pi
            if pi < 0:
                if t > u2:
                    return None
                if t > u1:
                    u1 = t
            else:
                if t < u1:
                    return None
                if t < u2:
                    u2 = t
    if u1 > u2:
        return None
    c_lat1 = round(lat1 + u1 * dlat, 6)
    c_lon1 = round(lon1 + u1 * dlon, 6)
    c_lat2 = round(lat1 + u2 * dlat, 6)
    c_lon2 = round(lon1 + u2 * dlon, 6)
    return (c_lat1, c_lon1, c_lat2, c_lon2)

NICARAGUAN_FIRST_NAMES = [
    "Carlos", "Juan Carlos", "María Elena", "Alejandro", "Roberto", "Luis Fernando",
    "Ana Patricia", "José Miguel", "Ernesto", "Claudia", "Francisco Javier", "Rosaura",
    "Marcos Antonio", "Daniela", "Oscar Danilo", "Karla Vanessa", "Mauricio", "Brenda Lisseth",
    "Ramón Emilio", "Tatiana Alejandra", "Gabriela", "Humberto", "Sofía", "Ricardo",
    "Valeria", "Denis", "Xiomara", "Byron", "Marisol", "Jairo", "Yaoska", "Bismarck",
    "Kenia", "Rigoberto", "Xochilt", "Bayardo", "Arlen", "Eddy", "Indiana", "Melvin",
    "Scarleth", "Lester", "Massiel", "Wilber", "Heydi", "Noel", "Karelia", "Álvaro",
    "Meyling", "Donald", "Fabiola", "Reynaldo", "wendy", "Oswaldo", "Marbely", "Silvio",
    "Verónica", "abner", "Ligia", "Gustavo", "Auxiliadora", "Marvin", "Yahoska", "Milton",
]

NICARAGUAN_SURNAMES = [
    "Mendoza", "Pérez", "Ruiz", "Gutiérrez", "Sánchez", "Gómez", "Morales", "Rizo",
    "Jirón", "Orozco", "López", "Vado", "Téllez", "Bermúdez", "Mairena", "Urbina",
    "Sequeira", "Centeno", "Duarte", "Pineda", "Solís", "Chamorro", "Montenegro", "Argüello",
    "Blandón", "Zeledón", "Membreño", "Rostrán", "Gadea", "Palacios", "Picado", "Talavera",
    "Altamirano", "vanegas", "Larios", "Calero", "Narváez", "Espinoza", "Jarquín", "Sobalvarro",
    "Salmerón", "Cajina", "Baltodano", "Alemán", "Guadamuz", "Corea", "Lacayo", "Bolaños",
]

VEHICLE_CATALOG_BY_TIER: dict[str, list[str]] = {
    "movigo_estandar": [
        "Toyota Yaris",
        "Hyundai Grand i10",
        "Kia Rio",
        "Suzuki Alto",
        "Chevrolet Spark",
        "Kia Picanto",
    ],
    "movigo_comfort": [
        "Suzuki Dzire",
        "Nissan Versa",
        "Toyota Corolla",
        "Hyundai Accent",
        "Honda City",
    ],
    "movigo_moto": [
        "Honda CB125F",
        "Yamaha YBR125",
        "Bajaj Pulsar 150",
        "Suzuki GN125",
        "Genesis HJ125",
    ],
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


def build_deterministic_users(seed: int = SIMULATION_SEED, count: int = 800) -> list[dict[str, Any]]:
    """Deterministically generate 800 passenger profiles with realistic registration dates and payment methods."""
    rng = np.random.default_rng(seed + 101)
    users: list[dict[str, Any]] = []
    payment_methods = ["efectivo", "tarjeta", "billetera_digital"]
    payment_probs = [0.42, 0.35, 0.23]

    pre_2024_start = date(2022, 1, 1)
    pre_2024_days = (date(2023, 12, 31) - pre_2024_start).days
    in_2024_start = date(2024, 1, 1)
    in_2024_days = (date(2024, 11, 15) - in_2024_start).days

    first_names = [n.title() for n in NICARAGUAN_FIRST_NAMES]
    surnames = [s.title() for s in NICARAGUAN_SURNAMES]

    for uid in range(1, count + 1):
        fn = first_names[int(rng.integers(0, len(first_names)))]
        sn1 = surnames[int(rng.integers(0, len(surnames)))]
        sn2 = surnames[int(rng.integers(0, len(surnames)))]
        name = f"{fn} {sn1} {sn2}" if rng.random() < 0.45 else f"{fn} {sn1}"

        prefix = "8" if rng.random() < 0.72 else "7"
        mid = 100 + ((uid * 37 + int(rng.integers(0, 900))) % 900)
        tail = 1000 + ((uid * 73 + int(rng.integers(0, 9000))) % 9000)
        phone = f"+505 {prefix}{mid:03d}-{tail:04d}"

        pm = str(rng.choice(payment_methods, p=payment_probs))
        rating = round(float(np.clip(rng.normal(4.76, 0.18), 3.85, 5.00)), 2)

        # 75% registered prior to 2024-01-01, 25% onboarded progressively during 2024
        if uid <= int(count * 0.75):
            reg_date = pre_2024_start + timedelta(days=int(rng.integers(0, pre_2024_days + 1)))
        else:
            reg_date = in_2024_start + timedelta(days=int(rng.integers(0, in_2024_days + 1)))

        users.append(
            {
                "user_id": uid,
                "name": name,
                "phone": phone,
                "preferred_payment_method": pm,
                "average_rating": rating,
                "registration_date": reg_date.isoformat(),
            }
        )

    return users


def build_deterministic_drivers_and_vehicles(
    seed: int = SIMULATION_SEED, count: int = 150
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministically generate 150 drivers and 150 1:1 vehicles registered in Managua."""
    rng = np.random.default_rng(seed + 202)
    drivers: list[dict[str, Any]] = []
    vehicles: list[dict[str, Any]] = []

    first_names = [n.title() for n in NICARAGUAN_FIRST_NAMES]
    surnames = [s.title() for s in NICARAGUAN_SURNAMES]

    statuses = ["activo", "en_viaje", "desconectado", "inactivo"]
    status_probs = [0.65, 0.15, 0.10, 0.10]

    service_tiers = ["movigo_estandar", "movigo_comfort", "movigo_moto"]
    tier_probs = [0.60, 0.22, 0.18]

    for did in range(1, count + 1):
        fn = first_names[int(rng.integers(0, len(first_names)))]
        sn1 = surnames[int(rng.integers(0, len(surnames)))]
        sn2 = surnames[int(rng.integers(0, len(surnames)))]
        name = f"{fn} {sn1} {sn2}" if rng.random() < 0.50 else f"{fn} {sn1}"

        status = str(rng.choice(statuses, p=status_probs))
        rating = round(float(np.clip(rng.normal(4.78, 0.16), 4.20, 4.99)), 2)
        acceptance = round(float(np.clip(rng.normal(88.5, 6.5), 68.0, 99.5)), 2)

        drivers.append(
            {
                "driver_id": did,
                "name": name,
                "average_rating": rating,
                "acceptance_rate_pct": acceptance,
                "status": status,
            }
        )

        tier = str(rng.choice(service_tiers, p=tier_probs))
        models = VEHICLE_CATALOG_BY_TIER[tier]
        v_model = str(models[int(rng.integers(0, len(models)))])
        if tier == "movigo_comfort":
            v_year = int(rng.integers(2019, 2025))
        elif tier == "movigo_moto":
            v_year = int(rng.integers(2020, 2025))
        else:
            v_year = int(rng.integers(2015, 2024))

        plate_num = 100000 + did * 5179 + int(rng.integers(10, 999))
        plate = f"M-{plate_num % 900000 + 100000:06d}"

        vehicles.append(
            {
                "vehicle_id": did,
                "driver_id": did,
                "service_type": tier,
                "vehicle_model": v_model,
                "vehicle_year": v_year,
                "license_plate": plate,
            }
        )

    return drivers, vehicles


def fetch_or_load_osm_raw_elements(
    output_dir: Path, fetch_osm: bool = False
) -> list[dict[str, Any]]:
    """Fetch complete OSM street elements for Managua across a 3x3 tiled grid or load from local cache."""
    cache_path = output_dir / "managua_osm_raw.json"
    if not fetch_osm and cache_path.exists():
        logger.info(f"Loading cached raw OSM elements from {cache_path}...")
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    logger.info("Fetching complete drivable street network from OpenStreetMap API v0.6 for Managua...")
    elements: list[dict[str, Any]] = []
    seen_ids: set[tuple[str, int]] = set()

    lat_min, lat_max = 12.086, 12.166
    lon_min, lon_max = -86.316, -86.204
    ny, nx = 3, 3
    dlat = (lat_max - lat_min) / ny
    dlon = (lon_max - lon_min) / nx

    import time

    for j in range(ny):
        for i in range(nx):
            b_lat0 = round(lat_min + j * dlat, 5)
            b_lat1 = round(lat_min + (j + 1) * dlat, 5)
            b_lon0 = round(lon_min + i * dlon, 5)
            b_lon1 = round(lon_min + (i + 1) * dlon, 5)
            bbox = f"{b_lon0},{b_lat0},{b_lon1},{b_lat1}"
            url = f"https://api.openstreetmap.org/api/0.6/map.json?bbox={bbox}"
            try:
                resp = requests.get(
                    url, headers={"User-Agent": "cs-datos-simulations/1.0"}, timeout=30
                )
                if resp.status_code == 200:
                    for el in resp.json().get("elements", []):
                        key = (el.get("type"), el.get("id"))
                        if key not in seen_ids:
                            seen_ids.add(key)
                            elements.append(el)
            except Exception as exc:
                logger.warning(f"Warning fetching OSM tile {bbox}: {exc}")
            time.sleep(1.0)

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(elements, f)
    logger.info(f"Saved {len(elements)} raw OSM elements to {cache_path}.")
    return elements


def build_deterministic_quadrants_and_dense_osm_graph(
    zones: list[dict[str, Any]],
    raw_osm_elements: list[dict[str, Any]],
    canonical_quadrants: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deterministically build or load the 92 contiguous square Quadrants and index the dense routable OSM street graph."""
    from collections import defaultdict, deque

    # 1. Parse raw nodes and filter drivable ways
    raw_nodes = {
        el["id"]: (round(el["lat"], 6), round(el["lon"], 6))
        for el in raw_osm_elements
        if el.get("type") == "node"
    }
    drivable_ways = [
        el
        for el in raw_osm_elements
        if el.get("type") == "way"
        and el.get("tags", {}).get("highway") in DRIVABLE_HIGHWAY_TYPES
    ]

    # Extract authentic OpenStreetMap waterways for real physical distance calculations
    waterway_features, waterway_seg_arr, waterway_seg_meta = extract_osm_waterways(raw_osm_elements)
    has_waterways = waterway_seg_arr.shape[0] > 0
    if has_waterways:
        y1_w = waterway_seg_arr[:, 0]
        x1_w = waterway_seg_arr[:, 1]
        y2_w = waterway_seg_arr[:, 2]
        x2_w = waterway_seg_arr[:, 3]
        dx_w = x2_w - x1_w
        dy_w = y2_w - y1_w
        len_sq_w = dx_w * dx_w + dy_w * dy_w
        len_sq_w[len_sq_w == 0] = 1e-9

    # 2. Define or load the 92 Quadrants (~0.88 km x 0.88 km square cells)
    quad_bounds: dict[int, tuple[float, float, float, float]] = {}

    if canonical_quadrants is not None and len(canonical_quadrants) > 0:
        quadrants = [dict(q) for q in canonical_quadrants]
        for q in quadrants:
            quad_bounds[q["quadrant_id"]] = (
                float(q["lat_min"]),
                float(q["lat_max"]),
                float(q["lon_min"]),
                float(q["lon_max"]),
            )
            # Dynamically compute real flood risk and canal proximity from authentic OSM waterways
            if has_waterways:
                clat = 0.5 * (float(q["lat_min"]) + float(q["lat_max"]))
                clon = 0.5 * (float(q["lon_min"]) + float(q["lon_max"]))
                py_q = clat * 111.0
                px_q = clon * 108.5
                t_q = np.clip(((px_q - x1_w) * dx_w + (py_q - y1_w) * dy_w) / len_sq_w, 0.0, 1.0)
                dists_q = np.hypot(px_q - (x1_w + t_q * dx_w), py_q - (y1_w + t_q * dy_w))
                min_idx = int(np.argmin(dists_q))
                min_d = float(dists_q[min_idx])
                near_meta = waterway_seg_meta[min_idx]
                alt = int(q.get("mean_altitude_masl", 120))
                if (min_d <= 0.40 and alt <= 85) or (min_d <= 0.22 and near_meta["is_named"]):
                    q["flood_risk"] = "critico"
                elif min_d <= 0.75:
                    q["flood_risk"] = "alto"
                elif min_d <= 1.30:
                    q["flood_risk"] = "medio"
                else:
                    q["flood_risk"] = "bajo"
                q["main_drainage_channels"] = near_meta["name"]
    else:
        cell_size = 0.008
        lon_grid = np.round(np.arange(-86.316, -86.204, cell_size), 6)
        lat_grid = np.round(np.arange(12.086, 12.166, cell_size), 6)
        ny = len(lat_grid)
        nx = len(lon_grid)

        active = np.zeros((ny, nx), dtype=bool)
        dense_pts = np.array([raw_nodes[nid] for nid in raw_nodes])

        for j, lat0 in enumerate(lat_grid):
            for i, lon0 in enumerate(lon_grid):
                lat1 = round(float(lat0 + cell_size), 6)
                lon1 = round(float(lon0 + cell_size), 6)
                clat = 0.5 * (lat0 + lat1)
                clon = 0.5 * (lon0 + lon1)
                in_cell = (
                    (dense_pts[:, 1] >= lon0)
                    & (dense_pts[:, 1] <= lon1)
                    & (dense_pts[:, 0] >= lat0)
                    & (dense_pts[:, 0] <= lat1)
                )
                min_d = min(haversine_km(clat, clon, z["latitude"], z["longitude"]) for z in zones)
                if np.sum(in_cell) >= 3 and min_d <= 2.15:
                    active[j, i] = True

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

        quadrants = []
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

                if has_waterways:
                    py_q = clat * 111.0
                    px_q = clon * 108.5
                    t_q = np.clip(((px_q - x1_w) * dx_w + (py_q - y1_w) * dy_w) / len_sq_w, 0.0, 1.0)
                    dists_q = np.hypot(px_q - (x1_w + t_q * dx_w), py_q - (y1_w + t_q * dy_w))
                    min_idx = int(np.argmin(dists_q))
                    min_d = float(dists_q[min_idx])
                    near_meta = waterway_seg_meta[min_idx]
                    if (min_d <= 0.40 and alt_masl <= 85) or (min_d <= 0.22 and near_meta["is_named"]):
                        risk = "critico"
                    elif min_d <= 0.75:
                        risk = "alto"
                    elif min_d <= 1.30:
                        risk = "medio"
                    else:
                        risk = "bajo"
                    cauce_desc = near_meta["name"]
                else:
                    risk = "medio"
                    cauce_desc = "Canal de Drenaje Pluvial Managua"

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
                quad_bounds[cell_id] = (lat0_f, lat1_f, lon0_f, lon1_f)
                cell_id += 1

    # 3. Filter nodes strictly inside the 92 quadrants
    node_to_quad: dict[int, tuple[int, int]] = {}
    for nid, (lat, lon) in raw_nodes.items():
        for q in quadrants:
            if (
                q["lat_min"] <= lat <= q["lat_max"]
                and q["lon_min"] <= lon <= q["lon_max"]
            ):
                node_to_quad[nid] = (q["quadrant_id"], q["zone_id"])
                break

    # 4. Extract Largest Strongly Connected Component (LSCC) strictly within the 92 quadrants
    adj = defaultdict(set)
    for w in drivable_ways:
        nids = w.get("nodes", [])
        for k in range(len(nids) - 1):
            u, v = nids[k], nids[k + 1]
            if u in node_to_quad and v in node_to_quad:
                adj[u].add(v)
                adj[v].add(u)

    visited = set()
    comps = []
    for n in adj:
        if n not in visited:
            comp = []
            q = deque([n])
            visited.add(n)
            while q:
                curr = q.popleft()
                comp.append(curr)
                for nxt in adj[curr]:
                    if nxt not in visited:
                        visited.add(nxt)
                        q.append(nxt)
            comps.append(comp)

    if not comps:
        raise ValueError("No connected drivable components found in OSM data inside the 92 quadrants.")

    largest_nodes = sorted(list(max(comps, key=len)))
    node_to_idx = {nid: i for i, nid in enumerate(largest_nodes)}

    # 5. Build node records strictly conforming to quadrant bounds
    node_records: list[list[Any]] = []
    q_node_indices: dict[str, list[int]] = {str(q["quadrant_id"]): [] for q in quadrants}

    for idx, nid in enumerate(largest_nodes):
        lat, lon = raw_nodes[nid]
        assigned_qid, assigned_zid = node_to_quad[nid]
        node_records.append([lat, lon, assigned_qid, assigned_zid])
        q_node_indices[str(assigned_qid)].append(idx)

    # 5. Build unique graph edges with road class, base speed, length, and flood flag
    edge_records: list[list[Any]] = []
    seen_edges: set[tuple[int, int]] = set()
    arterials: list[list[float]] = []

    for w in drivable_ways:
        hw = w.get("tags", {}).get("highway", "residential")
        base_spd = HIGHWAY_BASE_SPEEDS.get(hw, 25.0)
        hw_idx = HW_TO_IDX.get(hw, 0)
        nids = w.get("nodes", [])
        for k in range(len(nids) - 1):
            u, v = nids[k], nids[k + 1]
            if u in node_to_idx and v in node_to_idx:
                iu, iv = node_to_idx[u], node_to_idx[v]
                pair = (min(iu, iv), max(iu, iv))
                lat1, lon1 = raw_nodes[u]
                lat2, lon2 = raw_nodes[v]
                d = round(haversine_km(lat1, lon1, lat2, lon2), 4)
                if d < 0.001:
                    d = 0.001
                mlat = 0.5 * (lat1 + lat2)
                mlon = 0.5 * (lon1 + lon2)
                if has_waterways:
                    py_e = mlat * 111.0
                    px_e = mlon * 108.5
                    t_e = np.clip(((px_e - x1_w) * dx_w + (py_e - y1_w) * dy_w) / len_sq_w, 0.0, 1.0)
                    dists_e = np.hypot(px_e - (x1_w + t_e * dx_w), py_e - (y1_w + t_e * dy_w))
                    is_fl = int(np.min(dists_e) <= 0.050)
                else:
                    is_fl = 0
                eqid = node_records[iu][2]
                if pair not in seen_edges:
                    seen_edges.add(pair)
                    edge_records.append([iu, iv, d, base_spd, eqid, is_fl, hw_idx])
                    if hw in {"trunk", "primary", "secondary", "tertiary"}:
                        arterials.append([lat1, lon1, lat2, lon2])

    # 6. Build Liang-Barsky clipped quadrant streets for realistic on-street trip endpoints
    quadrant_streets: dict[str, list[list[float]]] = {}
    quadrant_flood_flags: dict[str, list[int]] = {}

    for q in quadrants:
        qid = q["quadrant_id"]
        lat0_f, lat1_f, lon0_f, lon1_f = quad_bounds[qid]
        margin = 0.0001
        cell_segs = []
        cell_flags = []

        # Find all edges touching this quadrant or crossing it
        q_edge_candidates = []
        for iu, iv, d, base_spd, eqid, is_fl, hw_idx in edge_records:
            lat1, lon1 = node_records[iu][0], node_records[iu][1]
            lat2, lon2 = node_records[iv][0], node_records[iv][1]
            if (
                min(lat1, lat2) <= lat1_f
                and max(lat1, lat2) >= lat0_f
                and min(lon1, lon2) <= lon1_f
                and max(lon1, lon2) >= lon0_f
            ):
                clipped = clip_segment_liang_barsky(
                    lat1,
                    lon1,
                    lat2,
                    lon2,
                    lat0_f + margin,
                    lat1_f - margin,
                    lon0_f + margin,
                    lon1_f - margin,
                )
                if clipped is not None:
                    c1, c2, c3, c4 = clipped
                    if haversine_km(c1, c2, c3, c4) >= 0.005:
                        cell_segs.append([c1, c2, c3, c4])
                        cell_flags.append(
                            1 if (is_fl or q["flood_risk"] == "critico") else 0
                        )

        quadrant_streets[str(qid)] = cell_segs[:120]
        quadrant_flood_flags[str(qid)] = cell_flags[:120]

    # 7. Select 1 representative hub intersection node per quadrant for fast corridor routing
    quad_hubs: dict[str, int] = {}
    for q in quadrants:
        qid = q["quadrant_id"]
        clat = 0.5 * (q["lat_min"] + q["lat_max"])
        clon = 0.5 * (q["lon_min"] + q["lon_max"])
        indices = q_node_indices[str(qid)]
        if indices:
            best_idx = min(
                indices,
                key=lambda i: (node_records[i][0] - clat) ** 2
                + (node_records[i][1] - clon) ** 2,
            )
            quad_hubs[str(qid)] = best_idx
        else:
            quad_hubs[str(qid)] = 0

    enriched_network = {
        "nodes": node_records,
        "edges": edge_records,
        "quadrant_node_indices": q_node_indices,
        "quad_hubs": quad_hubs,
        "quadrant_streets": quadrant_streets,
        "quadrant_flood_flags": quadrant_flood_flags,
        "arterials": arterials[:1500],
        "waterways": waterway_features,
    }
    return quadrants, enriched_network


def generate_deterministic_spatial_seeds(
    output_dir: Path = DETERMINISTIC_SEEDS_DIR,
    fetch_osm: bool = False,
    dry_run: bool = False,
    seed: int = SIMULATION_SEED,
) -> tuple[list[UrbanZone], list[Quadrant], dict[str, Any]]:
    """Deterministically generate and save urban_zones.json, quadrants.json, managua_street_network.json, users.json, drivers.json, and vehicles.json."""
    zones_dicts = build_deterministic_urban_zones()
    raw_osm = fetch_or_load_osm_raw_elements(output_dir=output_dir, fetch_osm=fetch_osm)

    quad_file = output_dir / "quadrants.json"
    canonical_quads = None
    if quad_file.exists():
        try:
            with open(quad_file, encoding="utf-8") as f:
                canonical_quads = json.load(f)
        except Exception:
            canonical_quads = None

    quadrants_dicts, enriched_net = build_deterministic_quadrants_and_dense_osm_graph(
        zones_dicts, raw_osm, canonical_quadrants=canonical_quads
    )
    users_dicts = build_deterministic_users(seed=seed, count=800)
    drivers_dicts, vehicles_dicts = build_deterministic_drivers_and_vehicles(
        seed=seed, count=150
    )
    drainage_dicts = build_deterministic_drainage_channels(raw_osm_elements=raw_osm)

    zones_models = [UrbanZone(**z) for z in zones_dicts]
    quadrants_models = [Quadrant(**q) for q in quadrants_dicts]
    _ = [User(**u) for u in users_dicts]
    _ = [Driver(**d) for d in drivers_dicts]
    _ = [Vehicle(**v) for v in vehicles_dicts]
    _ = [DrainageChannel(**c) for c in drainage_dicts]

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "urban_zones.json", "w", encoding="utf-8") as f:
            json.dump(zones_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "quadrants.json", "w", encoding="utf-8") as f:
            json.dump(quadrants_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "drainage_channels.json", "w", encoding="utf-8") as f:
            json.dump(drainage_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "users.json", "w", encoding="utf-8") as f:
            json.dump(users_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "drivers.json", "w", encoding="utf-8") as f:
            json.dump(drivers_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "vehicles.json", "w", encoding="utf-8") as f:
            json.dump(vehicles_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "managua_street_network.json", "w", encoding="utf-8") as f:
            json.dump(enriched_net, f, separators=(",", ":"))

    return zones_models, quadrants_models, enriched_net
