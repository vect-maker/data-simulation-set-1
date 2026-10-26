"""Generate deterministic spatial & population seeds and LLM catalog seeds for MoviGo (standardized English 3NF schema).

Seed directories are strictly separated by provenance:
1. src/movigo_sim/seeds/deterministic/:
   - urban_zones.json (12 Managua urban zones, 100% deterministic code function)
   - quadrants.json (92 contiguous ~0.88 km x 0.88 km square quadrants, 100% deterministic code function)
   - managua_street_network.json (OpenStreetMap drivable streets indexed per square quadrant)
   - users.json (800 passenger profiles, 100% deterministic code function)
   - drivers.json (150 driver profiles, 100% deterministic code function)
   - vehicles.json (150 vehicle profiles linked 1:1 to drivers, 100% deterministic code function)
2. src/movigo_sim/seeds/llm/:
   - incentive_campaigns.json (12 Knapsack bonus campaigns via Gemini API)
   - semantic_templates.json (cancellation reasons and trip comments via Gemini API)
"""

import argparse
import sys
from pathlib import Path
from pydantic import BaseModel, Field
from rich.panel import Panel

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

from movigo_sim.config import DETERMINISTIC_SEEDS_DIR, LLM_SEEDS_DIR, SEEDS_DIR, SIMULATION_SEED
from movigo_sim.models import IncentiveCampaign
from movigo_sim.spatial import generate_deterministic_spatial_seeds
from scripts.common import (
    console,
    tracker,
    get_gemini_client,
    generate_structured_data,
    save_json_file,
)

DEFAULT_SEEDS_DIR = SEEDS_DIR


class MoviGoSemanticTemplates(BaseModel):
    cancellation_reasons: list[str] = Field(description="Lista representativa de motivos de cancelación en Managua")
    driver_cancellation_reasons: list[str] = Field(description="Motivos realistas de cancelación por parte del conductor en Managua (tráfico, lluvias, cauces, pinchazos)")
    user_cancellation_reasons: list[str] = Field(description="Motivos realistas de cancelación por parte del pasajero (demora, cambio de ruta, tomó caponera)")
    trip_comments: list[str] = Field(description="Reseñas y comentarios del pasajero sobre el servicio, vehículo y tarifa")


class CampaignCatalog(BaseModel):
    campaigns: list[IncentiveCampaign]


class MoviGoSeedBundle(BaseModel):
    """Consolidated schema to generate non-spatial LLM catalogs in a single API request."""
    campaigns: list[IncentiveCampaign]
    semantic_templates: MoviGoSemanticTemplates


def run_deterministic_spatial_generation(
    det_dir: Path = DETERMINISTIC_SEEDS_DIR,
    fetch_osm: bool = False,
    dry_run: bool = False,
    seed: int = SIMULATION_SEED,
):
    """Run 100% deterministic code functions to build urban_zones.json, quadrants.json, managua_street_network.json, users.json, drivers.json, and vehicles.json."""
    console.print(Panel.fit(
        f"[bold cyan]MoviGo - Generación Determinista de Geometría y Catálogos (seed={seed})[/bold cyan]\n"
        f"[white]Destino: {det_dir}[/white]",
        border_style="cyan",
    ))
    zones, quadrants, net = generate_deterministic_spatial_seeds(
        output_dir=det_dir,
        fetch_osm=fetch_osm,
        dry_run=dry_run,
        seed=seed,
    )
    console.print(
        f"[bold green]✓ Semillas deterministas generadas:[/bold green] "
        f"{len(zones)} urban_zones, {len(quadrants)} quadrants, 800 users, 150 drivers, 150 vehicles y "
        f"{len(net.get('quadrant_streets', {}))} celdas viales indexadas en [cyan]{det_dir}[/cyan]."
    )


def generate_movigo_llm_bundle(
    llm_dir: Path = LLM_SEEDS_DIR,
    dry_run: bool = False,
    seed: int = SIMULATION_SEED,
):
    """Generate non-spatial LLM catalogs for MoviGo in 1 single Gemini API call into seeds/llm/."""
    client = get_gemini_client()
    console.print(Panel.fit(
        f"[bold magenta]MoviGo - Generación de Catálogos LLM (1 sola llamada API, seed={seed})[/bold magenta]\n"
        f"[yellow]Destino: {llm_dir}[/yellow]",
        border_style="magenta",
    ))

    prompt = """
    Genera el catálogo semántico y de campañas para MoviGo (app de movilidad urbana en Managua, Nicaragua):
    1. campaigns (exactamente 12): campaign_id enteros del 1 al 12 campañas de incentivos y bonos para optimización de mochila año 2024 (meta_viajes, hora_pico_lluvia, zona_alta_demanda).
    2. semantic_templates: cancellation_reasons, driver_cancellation_reasons, user_cancellation_reasons y trip_comments con vernáculo urbano de Managua.
    """

    console.print("[yellow]⏳ Solicitando paquete de catálogos LLM a Gemini...[/yellow]")
    bundle: MoviGoSeedBundle = generate_structured_data(client, prompt, MoviGoSeedBundle, seed=seed)

    llm_dir.mkdir(parents=True, exist_ok=True)
    save_json_file([c.model_dump(mode="json") for c in bundle.campaigns], llm_dir / "incentive_campaigns.json", dry_run)
    save_json_file(bundle.semantic_templates.model_dump(), llm_dir / "semantic_templates.json", dry_run)

    console.print(f"\n[bold green]✓ Catálogos LLM de MoviGo guardados en {llm_dir}.[/bold green]")
    tracker.print_status()


def generate_movigo_llm_granular(
    llm_dir: Path = LLM_SEEDS_DIR,
    target: str = "llm",
    dry_run: bool = False,
    seed: int = SIMULATION_SEED,
):
    """Generate individual LLM catalogs into seeds/llm/."""
    client = get_gemini_client()
    llm_dir.mkdir(parents=True, exist_ok=True)
    console.print(Panel.fit(
        f"[bold magenta]MoviGo - Generación Granular LLM (Target: {target.upper()}, seed={seed})[/bold magenta]",
        border_style="magenta",
    ))

    if target in ("all", "llm", "campaigns"):
        console.print("[yellow]Generando Incentive Campaigns (12)...[/yellow]")
        prompt = "Genera 12 campañas de incentivos con campaign_id enteros del 1 al 12 año 2024 para optimización de mochila."
        camp_data = generate_structured_data(client, prompt, CampaignCatalog, seed=seed)
        save_json_file([c.model_dump(mode="json") for c in camp_data.campaigns], llm_dir / "incentive_campaigns.json", dry_run)

    if target in ("all", "llm", "templates"):
        console.print("[yellow]Generando Semantic Templates...[/yellow]")
        prompt = "Genera motivos de cancelación y comentarios de pasajeros para ride-hailing en Managua."
        temp_data = generate_structured_data(client, prompt, MoviGoSemanticTemplates, seed=seed)
        save_json_file(temp_data.model_dump(), llm_dir / "semantic_templates.json", dry_run)

    tracker.print_status()


def generate_movigo_seeds(
    seeds_dir: Path = DEFAULT_SEEDS_DIR,
    target: str = "all",
    granular: bool = False,
    dry_run: bool = False,
    fetch_osm: bool = False,
    seed: int = SIMULATION_SEED,
):
    """Main entry point: routes deterministic targets to seeds/deterministic/ and LLM targets to seeds/llm/."""
    det_dir = seeds_dir / "deterministic"
    llm_dir = seeds_dir / "llm"

    if target in ("all", "deterministic"):
        run_deterministic_spatial_generation(det_dir=det_dir, fetch_osm=fetch_osm, dry_run=dry_run, seed=seed)

    if target == "deterministic":
        return

    if granular or target in ("campaigns", "templates"):
        generate_movigo_llm_granular(llm_dir=llm_dir, target=target, dry_run=dry_run, seed=seed)
    else:
        generate_movigo_llm_bundle(llm_dir=llm_dir, dry_run=dry_run, seed=seed)


def main():
    parser = argparse.ArgumentParser(description="Generar semillas deterministas y LLM para MoviGo")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_SEEDS_DIR), help="Directorio raíz de semillas (contiene deterministic/ y llm/)")
    parser.add_argument(
        "--target",
        type=str,
        choices=["all", "deterministic", "llm", "campaigns", "templates"],
        default="all",
        help="Objetivo a generar: 'deterministic' (geometría, calles, 800 users, 150 drivers/vehicles), 'llm' (campañas y plantillas Gemini), o 'all'",
    )
    parser.add_argument("--seed", type=int, default=SIMULATION_SEED, help="Semilla global de reproducibilidad")
    parser.add_argument("--fetch-osm", action="store_true", help="Re-descargar segmentos viales desde OpenStreetMap API v0.6")
    parser.add_argument("--granular", action="store_true", help="Usa llamadas API separadas por entidad LLM")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta sin sobreescribir archivos JSON")
    args = parser.parse_args()

    generate_movigo_seeds(
        Path(args.output_dir),
        target=args.target,
        granular=args.granular,
        dry_run=args.dry_run,
        fetch_osm=args.fetch_osm,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
