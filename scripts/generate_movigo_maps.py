"""Deterministic script to download OpenStreetMap tiles and render thematic maps for MoviGo.

Generates 4 publication-quality cartographic maps covering the Municipio de Managua:
1. map_01_managua_basemap.png (Basemap with Distritos I-VII & municipal landmarks)
2. map_02_mapped_streets.png (Basemap with mapped OpenStreetMap street network)
3. map_03_water_affected_zones.png (Basemap with cauces and hydrological flood risk tiers)
4. map_04_quadrants_by_zone.png (Basemap with 298 quadrants colored by urban pricing zone)

Ensures 100% reproducibility across environments with local tile caching.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
import numpy as np
from PIL import Image
import requests
from rich.console import Console
from rich.panel import Panel

console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

from movigo_sim.config import ARTIFACTS_DIR, DETERMINISTIC_SEEDS_DIR

DEFAULT_MAPS_DIR = ARTIFACTS_DIR / "spatial" / "maps"
DEFAULT_TILE_CACHE_DIR = BASE_DIR / "data" / "cache" / "tiles"

# Official Municipio de Managua expanded bounding box with buffer
LON_MIN, LON_MAX = -86.350, -86.130
LAT_MIN, LAT_MAX = 12.030, 12.185


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    """Convert WGS84 lat/lon to OpenStreetMap slippy tile numbers."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def num2deg(xtile: int, ytile: int, zoom: int) -> tuple[float, float]:
    """Convert OpenStreetMap slippy tile numbers to NW corner WGS84 coordinates."""
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def download_and_stitch_tiles(
    cache_dir: Path,
    zoom: int = 13,
    force_download: bool = False,
) -> tuple[Image.Image, list[float]]:
    """Download and stitch OpenStreetMap tiles covering Managua with local caching."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    x0, y0 = deg2num(LAT_MAX, LON_MIN, zoom)
    x1, y1 = deg2num(LAT_MIN, LON_MAX, zoom)
    x_min, x_max = min(x0, x1), max(x0, x1)
    y_min, y_max = min(y0, y1), max(y0, y1)

    width = (x_max - x_min + 1) * 256
    height = (y_max - y_min + 1) * 256
    stitched_img = Image.new("RGB", (width, height), (242, 242, 240))

    headers = {"User-Agent": "MoviGoAcademicSim/1.0 (contact: repo-admin@data-simulation.local)"}

    lat_top, lon_left = num2deg(x_min, y_min, zoom)
    lat_bottom, lon_right = num2deg(x_max + 1, y_max + 1, zoom)
    extent = [lon_left, lon_right, lat_bottom, lat_top]

    total_tiles = (x_max - x_min + 1) * (y_max - y_min + 1)
    console.print(f"[dim]Stitching {total_tiles} OSM tiles (zoom={zoom}) from ({x_min},{y_min}) to ({x_max},{y_max})...[/dim]")

    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tile_path = cache_dir / f"osm_{zoom}_{x}_{y}.png"
            if not force_download and tile_path.exists():
                try:
                    tile = Image.open(tile_path)
                except Exception:
                    tile = None
            else:
                tile = None

            if tile is None:
                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                try:
                    resp = requests.get(url, headers=headers, timeout=12)
                    if resp.status_code == 200:
                        tile_bytes = resp.content
                        with open(tile_path, "wb") as f:
                            f.write(tile_bytes)
                        tile = Image.open(io.BytesIO(tile_bytes))
                    else:
                        tile = Image.new("RGB", (256, 256), (240, 240, 240))
                except Exception as exc:
                    console.print(f"[yellow]Warning downloading tile ({x},{y}): {exc}[/yellow]")
                    tile = Image.new("RGB", (256, 256), (240, 240, 240))
                time.sleep(0.04)

            px = (x - x_min) * 256
            py = (y - y_min) * 256
            stitched_img.paste(tile, (px, py))

    return stitched_img, extent


def setup_figure(
    basemap_img: Image.Image,
    extent: list[float],
    title: str,
) -> tuple[plt.Figure, plt.Axes]:
    """Initialize a standardized matplotlib canvas with the basemap."""
    fig, ax = plt.subplots(figsize=(15, 10), dpi=220)
    ax.imshow(basemap_img, extent=extent, interpolation="bilinear", alpha=0.92)
    ax.set_xlim(LON_MIN, LON_MAX)
    ax.set_ylim(LAT_MIN, LAT_MAX)
    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)
    ax.set_xlabel("Longitud Oeste (WGS84)", fontsize=11)
    ax.set_ylabel("Latitud Norte (WGS84)", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.45)
    return fig, ax


def render_map_1_basemap(
    basemap_img: Image.Image,
    extent: list[float],
    output_path: Path,
):
    """Plot 1: Clean Managua municipal basemap with districts and reference landmarks."""
    fig, ax = setup_figure(
        basemap_img,
        extent,
        "Mapa Base del Municipio de Managua (Distritos I al VII y Límites)",
    )

    district_labels = [
        ("DISTRITO I\n(Centro / Financiero)", 12.126, -86.270),
        ("DISTRITO II\n(Noroeste / Costas)", 12.152, -86.302),
        ("DISTRITO III\n(Suroeste / Carretera Sur)", 12.105, -86.305),
        ("DISTRITO IV\n(Norte-Centro / Oriental)", 12.145, -86.262),
        ("DISTRITO V\n(Sur-Centro / Carretera a Masaya)", 12.095, -86.235),
        ("DISTRITO VI\n(Noreste / Aeropuerto / Mayoreo)", 12.142, -86.195),
        ("DISTRITO VII\n(Sureste / Sabana Grande)", 12.122, -86.185),
    ]
    for label, lat, lon in district_labels:
        ax.annotate(
            label,
            (lon, lat),
            fontsize=8.5,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.35",
                facecolor="#ffffcc",
                alpha=0.92,
                edgecolor="#b8860b",
                linewidth=1.2,
            ),
        )

    landmarks = [
        ("Lago Xolotlán (Lago de Managua)", 12.176, -86.270),
        ("Aeropuerto Augusto C. Sandino (MGA)", 12.141, -86.170),
        ("Mercado El Mayoreo", 12.138, -86.202),
        ("Mercado Oriental", 12.148, -86.265),
        ("Metrocentro", 12.1265, -86.2665),
        ("Esquipulas (km 11-14 C. Masaya)", 12.062, -86.220),
        ("Nejapa / C. Sur", 12.095, -86.315),
    ]
    for name, lat, lon in landmarks:
        ax.plot(lon, lat, marker="o", markersize=6, color="#b22222", markeredgecolor="white", markeredgewidth=1)
        ax.annotate(
            name,
            (lon, lat),
            fontsize=7.5,
            ha="left",
            va="center",
            xytext=(6, 3),
            textcoords="offset points",
            bbox=dict(boxstyle="square,pad=0.15", facecolor="white", alpha=0.85, edgecolor="gray", linewidth=0.5),
        )

    info_text = (
        "Municipio de Managua (ALMA)\n"
        "Cobertura Metropolina: Distritos I, II, III, IV, V, VI, VII\n"
        "Extensión: 12.030°N a 12.185°N | -86.350°W a -86.130°W (~410 km²)"
    )
    ax.text(
        0.02,
        0.03,
        info_text,
        transform=ax.transAxes,
        fontsize=9.5,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#333333"),
    )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def render_map_2_streets(
    basemap_img: Image.Image,
    extent: list[float],
    net: dict[str, Any],
    output_path: Path,
):
    """Plot 2: Mapped street network from OpenStreetMap."""
    fig, ax = setup_figure(
        basemap_img,
        extent,
        "Red Vial Mapeada del Municipio de Managua (OpenStreetMap)",
    )

    lines_residential = []
    for qid, segs in net.get("quadrant_streets", {}).items():
        for s in segs:
            lines_residential.append([(s[1], s[0]), (s[3], s[2])])

    lines_arterial = []
    for a in net.get("arterials", []):
        lines_arterial.append([(a[1], a[0]), (a[3], a[2])])

    lc_res = LineCollection(lines_residential, colors="#377eb8", linewidths=0.6, alpha=0.55, label="Calles y Vías Locales")
    lc_art = LineCollection(lines_arterial, colors="#e41a1c", linewidths=1.3, alpha=0.85, label="Arterias Metropolitanas")
    ax.add_collection(lc_res)
    ax.add_collection(lc_art)

    info_text = (
        f"Red Vial Total Mapeada\n"
        f"Nodos Conectados (LSCC): {len(net.get('nodes', [])):,}\n"
        f"Segmentos Viales Indexados: {len(lines_residential):,}\n"
        f"Arterias Metropolitanas: {len(lines_arterial):,}"
    )
    ax.text(
        0.02,
        0.03,
        info_text,
        transform=ax.transAxes,
        fontsize=9.5,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#333333"),
    )
    ax.legend(loc="upper right", framealpha=0.92, fontsize=10)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def render_map_3_water(
    basemap_img: Image.Image,
    extent: list[float],
    quadrants: list[dict[str, Any]],
    net: dict[str, Any],
    channels: list[dict[str, Any]],
    output_path: Path,
):
    """Plot 3: Waterways, cauces, and flood risk zones."""
    fig, ax = setup_figure(
        basemap_img,
        extent,
        "Red Hidrográfica de Cauces y Riesgo de Anegamiento Pluvial",
    )

    risk_colors = {
        "critico": ("#e41a1c", 0.40, "Riesgo Crítico (Desborde Frecuente)"),
        "alto": ("#ff7f00", 0.30, "Riesgo Alto (Anegamiento Rápido)"),
        "medio": ("#ffff33", 0.20, "Riesgo Medio (Acumulación Parcial)"),
        "bajo": ("#4daf4a", 0.10, "Riesgo Bajo (Buen Drenaje)"),
    }

    for risk_tier in ["bajo", "medio", "alto", "critico"]:
        patches_list = []
        color, alpha, lbl = risk_colors[risk_tier]
        matching = [q for q in quadrants if q.get("flood_risk") == risk_tier]
        for q in matching:
            rect = patches.Rectangle(
                (q["lon_min"], q["lat_min"]),
                q["lon_max"] - q["lon_min"],
                q["lat_max"] - q["lat_min"],
                linewidth=0.5,
                edgecolor=color,
                facecolor=color,
                alpha=alpha,
            )
            patches_list.append(rect)
        pc = PatchCollection(patches_list, match_original=True, label=f"{lbl} ({len(matching)} celdas)")
        ax.add_collection(pc)

    waterway_lines = []
    for feat in net.get("waterways", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            waterway_lines.append(coords)

    lc_water = LineCollection(
        waterway_lines,
        colors="#084594",
        linewidths=1.8,
        alpha=0.9,
        zorder=6,
        label=f"Cauces y Canales de Drenaje ({len(waterway_lines)} tramos)",
    )
    ax.add_collection(lc_water)

    for c in channels:
        if c.get("vulnerability_level") in ("critico", "alto"):
            ax.plot(c["longitude"], c["latitude"], marker="^", markersize=7, color="#084594", markeredgecolor="white", zorder=7)
            ax.annotate(
                c["channel_name"],
                (c["longitude"], c["latitude"]),
                fontsize=7.5,
                fontweight="bold",
                color="#084594",
                ha="center",
                va="bottom",
                xytext=(0, 4),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.88, edgecolor="#084594", linewidth=0.8),
            )

    info_text = (
        f"Hidrología Urbana y Drenaje Pluvial\n"
        f"Corredores Principales: {len(channels)} cauces nombrados\n"
        f"Tramos Fluviales Vectoriales: {len(waterway_lines):,}\n"
        f"Cuadrantes Críticos: {len([q for q in quadrants if q.get('flood_risk') == 'critico'])} | "
        f"Altos: {len([q for q in quadrants if q.get('flood_risk') == 'alto'])}"
    )
    ax.text(
        0.02,
        0.03,
        info_text,
        transform=ax.transAxes,
        fontsize=9.5,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#333333"),
    )
    ax.legend(loc="upper right", framealpha=0.92, fontsize=8.5)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def render_map_4_quadrants(
    basemap_img: Image.Image,
    extent: list[float],
    quadrants: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    output_path: Path,
):
    """Plot 4: 298 quadrants colored by their parent urban zone."""
    fig, ax = setup_figure(
        basemap_img,
        extent,
        f"Malla de {len(quadrants)} Cuadrantes (~880m x 880m) Coloreados por Zona Urbana (Managua)",
    )

    cmap = matplotlib.colormaps["turbo"].resampled(len(zones))
    zone_color_map = {z["zone_id"]: cmap(i) for i, z in enumerate(zones)}

    quad_patches = []
    face_colors = []
    for q in quadrants:
        rect = patches.Rectangle(
            (q["lon_min"], q["lat_min"]),
            q["lon_max"] - q["lon_min"],
            q["lat_max"] - q["lat_min"],
            linewidth=0.8,
            edgecolor="#333333",
        )
        quad_patches.append(rect)
        face_colors.append(zone_color_map.get(q["zone_id"], (0.5, 0.5, 0.5, 0.5)))

    pc4 = PatchCollection(quad_patches, facecolors=face_colors, edgecolors="#333333", linewidths=0.7, alpha=0.58)
    ax.add_collection(pc4)

    for z in zones:
        zc = zone_color_map[z["zone_id"]]
        ax.scatter(z["longitude"], z["latitude"], s=95, color=zc, edgecolors="black", linewidth=1.5, zorder=8)
        short_name = z["zone_name"].split("/")[0].strip()
        ax.annotate(
            f"Z{z['zone_id']}: {short_name}",
            (z["longitude"], z["latitude"]),
            fontsize=7.0,
            fontweight="bold",
            ha="center",
            va="bottom",
            zorder=9,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.88, edgecolor="black", linewidth=0.8),
        )

    info_text = (
        f"Malla Espacial de Managua (3NF)\n"
        f"Total Cuadrantes: {len(quadrants)} (~0.88 km × 0.88 km)\n"
        f"Zonas Urbanas Canónicas: {len(zones)}\n"
        f"Distritos Cubiertos: Distrito I al VII"
    )
    ax.text(
        0.02,
        0.03,
        info_text,
        transform=ax.transAxes,
        fontsize=9.5,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.92, edgecolor="#333333"),
    )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)


def generate_all_maps(
    output_dir: Path = DEFAULT_MAPS_DIR,
    cache_dir: Path = DEFAULT_TILE_CACHE_DIR,
    zoom: int = 13,
    force_download: bool = False,
) -> dict[str, Path]:
    """Orchestrate downloading/stitching tiles and rendering all 4 thematic maps."""
    console.print(Panel.fit(
        f"[bold cyan]MoviGo - Generación Cartográfica y Descarga de Teselas OSM[/bold cyan]\n"
        f"[white]Destino:[/white] [green]{output_dir}[/green]\n"
        f"[white]Caché de Teselas:[/white] [yellow]{cache_dir}[/yellow]",
        border_style="cyan",
    ))

    # 1. Download/stitch basemap
    basemap_img, extent = download_and_stitch_tiles(
        cache_dir=cache_dir,
        zoom=zoom,
        force_download=force_download,
    )

    # Save basemap tile to output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    basemap_tile_path = output_dir / "managua_basemap_tile.png"
    basemap_img.save(basemap_tile_path)
    console.print(f"[bold green]✓[/bold green] Mapa base ensamblado: {basemap_tile_path}")

    # 2. Load deterministic seeds
    with open(DETERMINISTIC_SEEDS_DIR / "urban_zones.json", encoding="utf-8") as f:
        zones = json.load(f)
    with open(DETERMINISTIC_SEEDS_DIR / "quadrants.json", encoding="utf-8") as f:
        quadrants = json.load(f)
    with open(DETERMINISTIC_SEEDS_DIR / "managua_street_network.json", encoding="utf-8") as f:
        net = json.load(f)
    with open(DETERMINISTIC_SEEDS_DIR / "drainage_channels.json", encoding="utf-8") as f:
        channels = json.load(f)

    # 3. Generate Maps
    p1 = output_dir / "map_01_managua_basemap.png"
    render_map_1_basemap(basemap_img, extent, p1)
    console.print(f"[bold green]✓[/bold green] Mapa 1 generado: {p1}")

    p2 = output_dir / "map_02_mapped_streets.png"
    render_map_2_streets(basemap_img, extent, net, p2)
    console.print(f"[bold green]✓[/bold green] Mapa 2 generado: {p2}")

    p3 = output_dir / "map_03_water_affected_zones.png"
    render_map_3_water(basemap_img, extent, quadrants, net, channels, p3)
    console.print(f"[bold green]✓[/bold green] Mapa 3 generado: {p3}")

    p4 = output_dir / "map_04_quadrants_by_zone.png"
    render_map_4_quadrants(basemap_img, extent, quadrants, zones, p4)
    console.print(f"[bold green]✓[/bold green] Mapa 4 generado: {p4}")

    return {
        "basemap": basemap_tile_path,
        "map_1": p1,
        "map_2": p2,
        "map_3": p3,
        "map_4": p4,
    }


def main():
    parser = argparse.ArgumentParser(description="Descarga teselas OSM y genera los 4 mapas temáticos de MoviGo.")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_MAPS_DIR), help="Directorio de salida para los mapas PNG")
    parser.add_argument("--cache-dir", type=str, default=str(DEFAULT_TILE_CACHE_DIR), help="Directorio de caché local de teselas OSM")
    parser.add_argument("--zoom", type=int, default=13, help="Nivel de zoom de las teselas OSM (default=13)")
    parser.add_argument("--force-download", action="store_true", help="Forzar re-descarga de teselas ignorando caché local")
    args = parser.parse_args()

    generate_all_maps(
        output_dir=Path(args.output_dir),
        cache_dir=Path(args.cache_dir),
        zoom=args.zoom,
        force_download=args.force_download,
    )


if __name__ == "__main__":
    main()
