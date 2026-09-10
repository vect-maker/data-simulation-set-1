"""Generate authentic synthetic catalog seeds for Cooperativa El Volcán using Gemini API.

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

from volcan_sim.models import (
    Finca,
    VariedadCafe,
    Beneficio,
    CuadrillaCorte,
    SubastaEspecial,
)
from scripts.common import (
    console,
    tracker,
    get_gemini_client,
    generate_structured_data,
    save_json_file,
)

DEFAULT_SEEDS_DIR = BASE_DIR / "src" / "volcan_sim" / "seeds"


# Pydantic Container Schemas
class TastingNotesTemplates(BaseModel):
    notas_catacion_altas: List[str] = Field(description="Notas de cata SCAA para lotes de especialidad sobresalientes (88+ pts, perfil Cup of Excellence)")
    notas_catacion_medias: List[str] = Field(description="Notas de cata SCAA para cafés de alta calidad de origen (85 a 87.9 pts)")
    notas_estandar: List[str] = Field(description="Notas de cata SCAA para cafés de especialidad balanceados (80 a 84.9 pts)")
    defectos_proceso: List[str] = Field(description="Defectos o anomalías técnicas de fermentación o secado")
    observaciones_proceso: List[str] = Field(description="Observaciones técnicas de procesamiento en beneficio")


class FincaCatalog(BaseModel):
    fincas: List[Finca]


class VariedadCatalog(BaseModel):
    variedades: List[VariedadCafe]


class BeneficioCatalog(BaseModel):
    beneficios: List[Beneficio]


class CuadrillaCatalog(BaseModel):
    cuadrillas: List[CuadrillaCorte]


class SubastaCatalog(BaseModel):
    subastas: List[SubastaEspecial]


class VolcanSeedBundle(BaseModel):
    """Consolidated schema to generate all dimensional catalogs in a single API request."""
    fincas: List[Finca]
    variedades: List[VariedadCafe]
    beneficios: List[Beneficio]
    cuadrillas: List[CuadrillaCorte]
    subastas: List[SubastaEspecial]
    tasting_notes: TastingNotesTemplates


def generate_volcan_bundle(seeds_dir: Path, dry_run: bool = False):
    """Generate all dimensional catalogs for Cooperativa El Volcán in 1 single Gemini API call."""
    client = get_gemini_client()
    console.print(Panel.fit(
        "[bold green]Cooperativa El Volcán - Generación Consolidada (1 sola llamada API)[/bold green]\n"
        "[cyan]Zonas Cafetaleras de Altura de Nicaragua (Optimizado para Free Tier)[/cyan]",
        border_style="green"
    ))

    prompt = """
    Genera el catálogo dimensional completo para Cooperativa El Volcán (café de especialidad en Nicaragua):
    1. fincas (exactamente 30): id_finca enteros del 1 al 30, id_productor enteros del 1 al 30 en terruños tradicionales:
       - Jinotega (12 fincas): Pantasma, El Cuá, Datanlí, Yalí. Altitud 1150-1450 msnm.
       - Matagalpa (8 fincas): Selva Negra, Yasica Sur, San Ramón. Altitud 980-1350 msnm.
       - Nueva Segovia - Dipilto (6 fincas): Dipilto, Mozonte, Jalapa. Altitud 1350-1680 msnm.
       - Madriz (4 fincas): San Juan del Río Coco, Telpaneca. Altitud 1050-1280 msnm.
    2. variedades (exactamente 7): id_variedad enteros del 1 al 7 arábicas tradicionales (Geisha, Pacamara, Bourbon, Maragogipe, Caturra, Catuaí Rojo, Catuaí Amarillo).
    3. beneficios (exactamente 5): id_beneficio enteros del 1 al 5 (1: Húmedo El Volcán Pantasma, 2: Húmedo Selva Negra, 3: Húmedo Cordillera de Dipilto, 4: Húmedo Somoto Río Coco, 5: Beneficio Seco Central Sébaco).
    4. cuadrillas (exactamente 12): id_cuadrilla enteros del 1 al 12 cuadrillas tradicionales de 12-35 cortadores.
    5. subastas (exactamente 12): id_subasta enteros del 1 al 12 micro-lotes para subasta internacional Knapsack año 2024, puntajes 87.5-92.5 SCAA (id_lote en null).
    6. tasting_notes: descriptores sensoriales SCAA (notas_catacion_altas 88+, notas_catacion_medias 85-87.9, notas_estandar 80-84.9, defectos_proceso, observaciones_proceso).
    """

    console.print("[yellow]⏳ Solicitando paquete dimensional consolidado a Gemini...[/yellow]")
    bundle: VolcanSeedBundle = generate_structured_data(client, prompt, VolcanSeedBundle)

    save_json_file([f.model_dump() for f in bundle.fincas], seeds_dir / "fincas_nicaragua.json", dry_run)
    save_json_file([v.model_dump() for v in bundle.variedades], seeds_dir / "variedades_cafe.json", dry_run)
    save_json_file([b.model_dump() for b in bundle.beneficios], seeds_dir / "beneficios.json", dry_run)
    save_json_file([c.model_dump() for c in bundle.cuadrillas], seeds_dir / "cuadrillas.json", dry_run)
    save_json_file([s.model_dump(mode="json") for s in bundle.subastas], seeds_dir / "subastas_knapsack.json", dry_run)
    save_json_file(bundle.tasting_notes.model_dump(), seeds_dir / "tasting_notes.json", dry_run)

    console.print("\n[bold green]✓ Todos los catálogos de Cooperativa El Volcán generados y guardados con 1 sola llamada API.[/bold green]")
    tracker.print_status()


def generate_volcan_granular(seeds_dir: Path, target: str = "all", dry_run: bool = False):
    """Generate individual or sequential catalogs (uses multiple API requests)."""
    client = get_gemini_client()
    console.print(Panel.fit(
        f"[bold green]Cooperativa El Volcán - Generación Granular (Target: {target.upper()})[/bold green]",
        border_style="green"
    ))

    if target in ("all", "fincas"):
        console.print("[yellow]Generando Fincas Cafetaleras (30)...[/yellow]")
        prompt = "Genera exactamente 30 fincas cafetaleras de Nicaragua con id_finca enteros del 1 al 30 e id_productor enteros del 1 al 30 en Jinotega, Matagalpa, Nueva Segovia (Dipilto) y Madriz."
        data = generate_structured_data(client, prompt, FincaCatalog)
        save_json_file([f.model_dump() for f in data.fincas], seeds_dir / "fincas_nicaragua.json", dry_run)

    if target in ("all", "variedades"):
        console.print("[yellow]Generando Variedades de Café (7)...[/yellow]")
        prompt = "Genera 7 variedades botánicas con id_variedad enteros del 1 al 7: Geisha, Pacamara, Bourbon, Maragogipe, Caturra, Catuaí Rojo, Catuaí Amarillo."
        data = generate_structured_data(client, prompt, VariedadCatalog)
        save_json_file([v.model_dump() for v in data.variedades], seeds_dir / "variedades_cafe.json", dry_run)

    if target in ("all", "beneficios"):
        console.print("[yellow]Generando Beneficios de Café (5)...[/yellow]")
        prompt = "Genera 5 beneficios de café con id_beneficio enteros del 1 al 5: Pantasma, Selva Negra, Dipilto, Somoto Río Coco, y Beneficio Seco Central Sébaco."
        data = generate_structured_data(client, prompt, BeneficioCatalog)
        save_json_file([b.model_dump() for b in data.beneficios], seeds_dir / "beneficios.json", dry_run)

    if target in ("all", "cuadrillas"):
        console.print("[yellow]Generando Cuadrillas de Corte (12)...[/yellow]")
        prompt = "Genera 12 cuadrillas de cortadores con id_cuadrilla enteros del 1 al 12 con 12-35 jornaleros."
        data = generate_structured_data(client, prompt, CuadrillaCatalog)
        save_json_file([c.model_dump() for c in data.cuadrillas], seeds_dir / "cuadrillas.json", dry_run)

    if target in ("all", "subastas"):
        console.print("[yellow]Generando Micro-lotes para Subasta Knapsack (12)...[/yellow]")
        prompt = "Genera 12 micro-lotes para subasta internacional con id_subasta enteros del 1 al 12 año 2024."
        data = generate_structured_data(client, prompt, SubastaCatalog)
        save_json_file([s.model_dump(mode="json") for s in data.subastas], seeds_dir / "subastas_knapsack.json", dry_run)

    if target in ("all", "tasting"):
        console.print("[yellow]Generando Notas de Cata SCAA...[/yellow]")
        prompt = "Genera notas de cata SCAA para cafés de alta calidad, defectos de proceso y registros técnicos."
        data = generate_structured_data(client, prompt, TastingNotesTemplates)
        save_json_file(data.model_dump(), seeds_dir / "tasting_notes.json", dry_run)

    tracker.print_status()


def generate_volcan_seeds(seeds_dir: Path, target: str = "all", granular: bool = False, dry_run: bool = False):
    """Main entry point: defaults to bundled generation for quota economy."""
    if granular or target != "all":
        generate_volcan_granular(seeds_dir=seeds_dir, target=target, dry_run=dry_run)
    else:
        generate_volcan_bundle(seeds_dir=seeds_dir, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="Generar semillas sintéticas para Cooperativa El Volcán con Gemini API")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_SEEDS_DIR), help="Directorio destino para guardar semillas JSON")
    parser.add_argument("--target", type=str, choices=["all", "fincas", "variedades", "beneficios", "cuadrillas", "subastas", "tasting"], default="all")
    parser.add_argument("--granular", action="store_true", help="Usa llamadas API separadas por entidad en vez de 1 llamada consolidada")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta sin sobreescribir archivos JSON")
    args = parser.parse_args()

    generate_volcan_seeds(Path(args.output_dir), target=args.target, granular=args.granular, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
