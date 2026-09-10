"""Generate authentic synthetic catalog seeds for MoviGo using Gemini API.

Supports both:
1. Bundled Mode (Default): Consolidates all catalogs into a single Gemini request (1 API call).
   Ideal for strict Free Tier quota budgeting (e.g. 20 requests/day).
2. Granular Mode: Allows generating individual targets or stepping through sequentially.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from rich.panel import Panel

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

from movigo_sim.models import (
    ZonaUrbana,
    Usuario,
    Conductor,
    CampanaIncentivo,
)
from scripts.common import (
    console,
    tracker,
    get_gemini_client,
    generate_structured_data,
    save_json_file,
)

DEFAULT_SEEDS_DIR = BASE_DIR / "src" / "movigo_sim" / "seeds"


# Pydantic Container Schemas
class MoviGoSemanticTemplates(BaseModel):
    motivos_cancelacion: List[str] = Field(description="Lista representativa de motivos de cancelación en Managua")
    motivos_cancelacion_conductor: List[str] = Field(description="Motivos realistas de cancelación por parte del conductor en Managua (tráfico, lluvias, cauces, pinchazos)")
    motivos_cancelacion_usuario: List[str] = Field(description="Motivos realistas de cancelación por parte del pasajero (demora, cambio de ruta, tomó caponera)")
    comentarios_viaje: List[str] = Field(description="Reseñas y comentarios del pasajero sobre el servicio, vehículo y tarifa")


class ZonaUrbanaCatalog(BaseModel):
    zonas: List[ZonaUrbana]


class UsuarioCatalog(BaseModel):
    usuarios: List[Usuario]


class ConductorCatalog(BaseModel):
    conductores: List[Conductor]


class CampanaCatalog(BaseModel):
    campanas: List[CampanaIncentivo]


class MoviGoSeedBundle(BaseModel):
    """Consolidated schema to generate all dimensional catalogs in a single API request."""
    zonas: List[ZonaUrbana]
    conductores: List[Conductor]
    usuarios: List[Usuario]
    campanas: List[CampanaIncentivo]
    semantic_templates: MoviGoSemanticTemplates


def generate_movigo_bundle(seeds_dir: Path, dry_run: bool = False):
    """Generate all dimensional catalogs for MoviGo in 1 single Gemini API call."""
    client = get_gemini_client()
    console.print(Panel.fit(
        "[bold magenta]MoviGo - Generación Consolidada (1 sola llamada API)[/bold magenta]\n"
        "[yellow]Movilidad Urbana y Ride-Hailing en Managua, Nicaragua (Optimizado para Free Tier)[/yellow]",
        border_style="magenta"
    ))

    prompt = """
    Genera el catálogo dimensional completo para MoviGo (app de movilidad urbana en Managua, Nicaragua):
    1. zonas (exactamente 12): id_zona enteros del 1 al 12 clasificadas por estrato socioeconómico:
       - alto: Villa Fontana, Las Colinas, Santo Domingo.
       - medio: Los Robles, Altamira, Bolonia, Bello Horizonte, Linda Vista.
       - comercial: Metrocentro / Eje Corporativo UCA.
       - popular: Ciudad Jardín, Mercado Oriental, Mercado Roberto Huembes.
       Coordenadas Managua (latitud 12.10-12.16, longitud -86.32 a -86.20).
    2. conductores (exactamente 20): id_conductor enteros del 1 al 20 con modelos populares en Nicaragua (Yaris, Grand i10, Dzire, Rio, Versa, CB125F), placas Managua 'M-123456', calificación 4.30-4.98.
    3. usuarios (exactamente 20): id_usuario enteros del 1 al 20 pasajeros frecuentes, teléfonos '+505 8xxx-xxxx', métodos de pago (efectivo, tarjeta, billetera_digital).
    4. campanas (exactamente 12): id_campana enteros del 1 al 12 campañas de incentivos y bonos para optimización de mochila año 2024 (meta_viajes, hora_pico_lluvia, zona_alta_demanda).
    5. semantic_templates: motivos_cancelacion, motivos_cancelacion_conductor, motivos_cancelacion_usuario y comentarios_viaje con vernáculo urbano de Managua.
    """

    console.print("[yellow]⏳ Solicitando paquete dimensional consolidado a Gemini...[/yellow]")
    bundle: MoviGoSeedBundle = generate_structured_data(client, prompt, MoviGoSeedBundle)

    save_json_file([z.model_dump() for z in bundle.zonas], seeds_dir / "zonas_urbanas.json", dry_run)
    save_json_file([c.model_dump() for c in bundle.conductores], seeds_dir / "conductores.json", dry_run)
    save_json_file([u.model_dump(mode="json") for u in bundle.usuarios], seeds_dir / "usuarios.json", dry_run)
    save_json_file([c.model_dump(mode="json") for c in bundle.campanas], seeds_dir / "campanas_incentivos.json", dry_run)
    save_json_file(bundle.semantic_templates.model_dump(), seeds_dir / "semantic_templates.json", dry_run)

    console.print("\n[bold green]✓ Todos los catálogos de MoviGo generados y guardados con 1 sola llamada API.[/bold green]")
    tracker.print_status()


def generate_movigo_granular(seeds_dir: Path, target: str = "all", dry_run: bool = False):
    """Generate individual or sequential catalogs (uses multiple API requests)."""
    client = get_gemini_client()
    console.print(Panel.fit(
        f"[bold magenta]MoviGo - Generación Granular (Target: {target.upper()})[/bold magenta]",
        border_style="magenta"
    ))

    if target in ("all", "zonas"):
        console.print("[yellow]Generando Cuadrantes Urbanos de Managua (12)...[/yellow]")
        prompt = "Genera 12 cuadrantes urbanos de Managua con id_zona enteros del 1 al 12 con estrato socioeconómico."
        data = generate_structured_data(client, prompt, ZonaUrbanaCatalog)
        save_json_file([z.model_dump() for z in data.zonas], seeds_dir / "zonas_urbanas.json", dry_run)

    if target in ("all", "conductores"):
        console.print("[yellow]Generando Conductores (20)...[/yellow]")
        prompt = "Genera 20 conductores de MoviGo con id_conductor enteros del 1 al 20 con vehículos comunes en Nicaragua y placas M-XXXXXX."
        data = generate_structured_data(client, prompt, ConductorCatalog)
        save_json_file([c.model_dump() for c in data.conductores], seeds_dir / "conductores.json", dry_run)

    if target in ("all", "usuarios"):
        console.print("[yellow]Generando Pasajeros Frecuentes (20)...[/yellow]")
        prompt = "Genera 20 pasajeros con id_usuario enteros del 1 al 20 con formato telefónico +505 y métodos de pago."
        data = generate_structured_data(client, prompt, UsuarioCatalog)
        save_json_file([u.model_dump(mode="json") for u in data.usuarios], seeds_dir / "usuarios.json", dry_run)

    if target in ("all", "campanas"):
        console.print("[yellow]Generando Campañas de Incentivos Knapsack (12)...[/yellow]")
        prompt = "Genera 12 campañas de incentivos con id_campana enteros del 1 al 12 año 2024 para optimización de mochila."
        data = generate_structured_data(client, prompt, CampanaCatalog)
        save_json_file([c.model_dump(mode="json") for c in data.campanas], seeds_dir / "campanas_incentivos.json", dry_run)

    if target in ("all", "templates"):
        console.print("[yellow]Generando Plantillas de Cancelación y Reseñas...[/yellow]")
        prompt = "Genera motivos de cancelación y comentarios de pasajeros para ride-hailing en Managua."
        data = generate_structured_data(client, prompt, MoviGoSemanticTemplates)
        save_json_file(data.model_dump(), seeds_dir / "semantic_templates.json", dry_run)

    tracker.print_status()


def generate_movigo_seeds(seeds_dir: Path, target: str = "all", granular: bool = False, dry_run: bool = False):
    """Main entry point: defaults to bundled generation for quota economy."""
    if granular or target != "all":
        generate_movigo_granular(seeds_dir=seeds_dir, target=target, dry_run=dry_run)
    else:
        generate_movigo_bundle(seeds_dir=seeds_dir, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="Generar semillas sintéticas para MoviGo con Gemini API")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_SEEDS_DIR), help="Directorio destino para guardar semillas JSON")
    parser.add_argument("--target", type=str, choices=["all", "zonas", "conductores", "usuarios", "campanas", "templates"], default="all")
    parser.add_argument("--granular", action="store_true", help="Usa llamadas API separadas por entidad en vez de 1 llamada consolidada")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta sin sobreescribir archivos JSON")
    args = parser.parse_args()

    generate_movigo_seeds(Path(args.output_dir), target=args.target, granular=args.granular, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
