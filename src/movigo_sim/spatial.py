"""Deterministic spatial & street-network builder for MoviGo (Managua, Nicaragua).

Encapsulates 100% reproducible, code-driven generation of:
- zonas_urbanas.json (12 Managua urban pricing and mobility zones)
- cuadrantes.json (92 contiguous ~0.88 km x 0.88 km square grid cells grouped by id_zona)
- managua_street_network.json (OpenStreetMap drivable street segments indexed per zone and per square cuadrante)
"""

import json
import logging
import math
from pathlib import Path
from typing import Any
import numpy as np
import requests

from movigo_sim.config import DETERMINISTIC_SEEDS_DIR
from movigo_sim.models import Cuadrante, ZonaUrbana

logger = logging.getLogger(__name__)

# Canonical deterministic specification of Managua's 12 urban pricing zones
CANONICAL_ZONAS_URBANAS: list[dict[str, Any]] = [
    {
        "id_zona": 1,
        "nombre_zona": "Villa Fontana",
        "estrato_socioeconomico": "alto",
        "latitud": 12.115,
        "longitud": -86.255,
        "radio_cobertura_km": 2.5,
        "tarifa_base_bajada_bandera": 70.0,
    },
    {
        "id_zona": 2,
        "nombre_zona": "Las Colinas",
        "estrato_socioeconomico": "alto",
        "latitud": 12.105,
        "longitud": -86.242,
        "radio_cobertura_km": 3.0,
        "tarifa_base_bajada_bandera": 75.0,
    },
    {
        "id_zona": 3,
        "nombre_zona": "Santo Domingo",
        "estrato_socioeconomico": "alto",
        "latitud": 12.1,
        "longitud": -86.23,
        "radio_cobertura_km": 2.8,
        "tarifa_base_bajada_bandera": 80.0,
    },
    {
        "id_zona": 4,
        "nombre_zona": "Los Robles",
        "estrato_socioeconomico": "medio",
        "latitud": 12.128,
        "longitud": -86.265,
        "radio_cobertura_km": 2.0,
        "tarifa_base_bajada_bandera": 55.0,
    },
    {
        "id_zona": 5,
        "nombre_zona": "Altamira",
        "estrato_socioeconomico": "medio",
        "latitud": 12.133,
        "longitud": -86.25,
        "radio_cobertura_km": 2.0,
        "tarifa_base_bajada_bandera": 50.0,
    },
    {
        "id_zona": 6,
        "nombre_zona": "Bolonia",
        "estrato_socioeconomico": "medio",
        "latitud": 12.145,
        "longitud": -86.28,
        "radio_cobertura_km": 2.2,
        "tarifa_base_bajada_bandera": 55.0,
    },
    {
        "id_zona": 7,
        "nombre_zona": "Bello Horizonte",
        "estrato_socioeconomico": "medio",
        "latitud": 12.138,
        "longitud": -86.22,
        "radio_cobertura_km": 3.5,
        "tarifa_base_bajada_bandera": 48.0,
    },
    {
        "id_zona": 8,
        "nombre_zona": "Linda Vista",
        "estrato_socioeconomico": "medio",
        "latitud": 12.155,
        "longitud": -86.3,
        "radio_cobertura_km": 3.0,
        "tarifa_base_bajada_bandera": 50.0,
    },
    {
        "id_zona": 9,
        "nombre_zona": "Metrocentro / Eje Corporativo UCA",
        "estrato_socioeconomico": "comercial",
        "latitud": 12.12,
        "longitud": -86.27,
        "radio_cobertura_km": 1.5,
        "tarifa_base_bajada_bandera": 60.0,
    },
    {
        "id_zona": 10,
        "nombre_zona": "Ciudad Jardín",
        "estrato_socioeconomico": "popular",
        "latitud": 12.14,
        "longitud": -86.258,
        "radio_cobertura_km": 2.0,
        "tarifa_base_bajada_bandera": 40.0,
    },
    {
        "id_zona": 11,
        "nombre_zona": "Mercado Oriental",
        "estrato_socioeconomico": "popular",
        "latitud": 12.135,
        "longitud": -86.245,
        "radio_cobertura_km": 2.5,
        "tarifa_base_bajada_bandera": 35.0,
    },
    {
        "id_zona": 12,
        "nombre_zona": "Mercado Roberto Huembes",
        "estrato_socioeconomico": "popular",
        "latitud": 12.125,
        "longitud": -86.238,
        "radio_cobertura_km": 2.5,
        "tarifa_base_bajada_bandera": 38.0,
    },
]

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


def build_deterministic_zonas_urbanas() -> list[dict[str, Any]]:
    """Return a deep copy of the 12 canonical Managua urban zones."""
    return [dict(z) for z in CANONICAL_ZONAS_URBANAS]


def fetch_osm_street_network_for_zones(zonas: list[dict[str, Any]]) -> dict[str, Any]:
    """Fetch real drivable street segments from OpenStreetMap API v0.6 for all 12 Managua zones."""
    zone_segments: dict[str, list[list[float]]] = {}
    arterials: list[list[float]] = []
    rng = np.random.default_rng(42)

    for z in zonas:
        zid = str(z["id_zona"])
        lat_c = z["latitud"]
        lon_c = z["longitud"]
        r_deg = min(0.015, (z["radio_cobertura_km"] / 111.0) * 0.85)
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


def build_deterministic_cuadrantes_and_street_index(
    zonas: list[dict[str, Any]],
    base_network: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deterministically build the 92 contiguous square Cuadrantes and index all street segments."""
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
            min_d = min(haversine_km(clat, clon, z["latitud"], z["longitud"]) for z in zonas)
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

    cuadrantes: list[dict[str, Any]] = []
    cuadrante_streets: dict[str, list[list[float]]] = {}
    cuadrante_flood_flags: dict[str, list[int]] = {}
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
                zonas,
                key=lambda z: haversine_km(clat, clon, z["latitud"], z["longitud"])
                / (z["radio_cobertura_km"] ** 0.35),
            )
            zid = int(best_z["id_zona"])
            zname = str(best_z["nombre_zona"])

            norm_south = max(0.0, min(1.0, (12.164 - clat) / (12.164 - 12.086)))
            alt_msnm = int(round(46.0 + 195.0 * (norm_south ** 1.38)))

            nearest_hotspot = min(
                FLOOD_HOTSPOTS, key=lambda h: haversine_km(clat, clon, h["lat"], h["lon"])
            )
            dist_hotspot = haversine_km(clat, clon, nearest_hotspot["lat"], nearest_hotspot["lon"])

            if dist_hotspot <= nearest_hotspot["radius_km"] * 0.78 or (
                alt_msnm <= 66 and zid in (7, 10, 11)
            ):
                riesgo = "critico"
                cauce_desc = nearest_hotspot["name"]
            elif dist_hotspot <= nearest_hotspot["radius_km"] * 1.25 or alt_msnm <= 82:
                riesgo = "alto"
                cauce_desc = nearest_hotspot["name"] if dist_hotspot <= 1.2 else ZONE_CAUCES[zid]
            elif alt_msnm <= 135:
                riesgo = "medio"
                cauce_desc = ZONE_CAUCES[zid]
            else:
                riesgo = "bajo"
                cauce_desc = ZONE_CAUCES[zid]

            code = f"Q{cell_id:02d}-Z{zid:02d}"
            name = f"{zname} - Cuadrante Q{cell_id:02d} (F{j+1}C{i+1})"

            cuadrantes.append(
                {
                    "id_cuadrante": cell_id,
                    "id_zona": zid,
                    "codigo_cuadrante": code,
                    "nombre_cuadrante": name,
                    "fila_grid": int(j),
                    "columna_grid": int(i),
                    "lat_min": lat0_f,
                    "lat_max": lat1_f,
                    "lon_min": lon0_f,
                    "lon_max": lon1_f,
                    "altitud_media_msnm": alt_msnm,
                    "riesgo_inundacion": riesgo,
                    "cauces_principales": cauce_desc,
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
                    cell_flags.append(1 if (is_fl or riesgo == "critico") else 0)

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
                    cell_flags.append(1 if riesgo in ("critico", "alto") else 0)

            cuadrante_streets[str(cell_id)] = cell_segs[:120]
            cuadrante_flood_flags[str(cell_id)] = cell_flags[:120]
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
        "cuadrante_streets": cuadrante_streets,
        "cuadrante_flood_flags": cuadrante_flood_flags,
    }
    return cuadrantes, enriched_network


def generate_deterministic_spatial_seeds(
    output_dir: Path = DETERMINISTIC_SEEDS_DIR,
    fetch_osm: bool = False,
    dry_run: bool = False,
) -> tuple[list[ZonaUrbana], list[Cuadrante], dict[str, Any]]:
    """Deterministically generate and save zonas_urbanas.json, cuadrantes.json, and managua_street_network.json."""
    zonas_dicts = build_deterministic_zonas_urbanas()
    net_path = output_dir / "managua_street_network.json"

    if fetch_osm or not net_path.exists():
        logger.info("Fetching drivable street segments from OpenStreetMap API v0.6 for Managua...")
        base_net = fetch_osm_street_network_for_zones(zonas_dicts)
    else:
        with open(net_path, encoding="utf-8") as f:
            base_net = json.load(f)

    cuadrantes_dicts, enriched_net = build_deterministic_cuadrantes_and_street_index(
        zonas_dicts, base_net
    )

    zonas_models = [ZonaUrbana(**z) for z in zonas_dicts]
    cuadrantes_models = [Cuadrante(**c) for c in cuadrantes_dicts]

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "zonas_urbanas.json", "w", encoding="utf-8") as f:
            json.dump(zonas_dicts, f, indent=2, ensure_ascii=False)
        with open(output_dir / "cuadrantes.json", "w", encoding="utf-8") as f:
            json.dump(cuadrantes_dicts, f, indent=2, ensure_ascii=False)
        with open(net_path, "w", encoding="utf-8") as f:
            json.dump(enriched_net, f, separators=(",", ":"))

    return zonas_models, cuadrantes_models, enriched_net
