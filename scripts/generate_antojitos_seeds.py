"""Generate authentic synthetic catalog seeds for Antojitos Express using Gemini API.

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

from antojitos_sim.models import (
    CategoriaPlatillo,
    Platillo,
    Zona,
    Repartidor,
    Promocion,
)
from scripts.common import (
    console,
    tracker,
    get_gemini_client,
    generate_structured_data,
    save_json_file,
)

DEFAULT_SEEDS_DIR = BASE_DIR / "src" / "antojitos_sim" / "seeds"


# Pydantic Container Schemas
class SemanticTemplates(BaseModel):
    notas_entrega: List[str] = Field(description="Direcciones de entrega con puntos de referencia típicos de Managua")
    motivos_cancelacion: List[str] = Field(description="Motivos realistas de cancelación en delivery urbano de Managua")
    comentarios_retraso: List[str] = Field(description="Quejas realistas de clientes por retrasos o pedidos fríos")
    comentarios_exitosos: List[str] = Field(description="Comentarios positivos elogiando la gastronomía nicaragüense")


class CategoriaCatalog(BaseModel):
    categorias: List[CategoriaPlatillo]


class PlatilloCatalog(BaseModel):
    platillos: List[Platillo]


class ZonaCatalog(BaseModel):
    zonas: List[Zona]


class RepartidorCatalog(BaseModel):
    repartidores: List[Repartidor]


class PromocionCatalog(BaseModel):
    promociones: List[Promocion]


class AntojitosSeedBundle(BaseModel):
    """Consolidated schema to generate all dimensional catalogs in a single API request."""
    categorias: List[CategoriaPlatillo]
    platillos: List[Platillo]
    zonas: List[Zona]
    repartidores: List[Repartidor]
    promociones: List[Promocion]
    semantic_templates: SemanticTemplates


def generate_antojitos_bundle(seeds_dir: Path, dry_run: bool = False):
    """Generate all dimensional catalogs for Antojitos Express in 1 single Gemini API call."""
    client = get_gemini_client()
    console.print(Panel.fit(
        "[bold cyan]Antojitos Express - Generación Consolidada (1 sola llamada API)[/bold cyan]\n"
        "[green]Gastronomía y Geografía Urbana de Managua, Nicaragua (Optimizado para Free Tier)[/green]",
        border_style="cyan"
    ))

    prompt = """
    Genera el catálogo dimensional completo para una cocina fantasma (ghost kitchen) en Managua, Nicaragua:
    1. categorias (exactamente 5): id_categoria enteros del 1 al 5: 1 (Fritanga), 2 (Quesillos), 3 (Hamburguesas), 4 (Bebidas), 5 (Postres).
    2. platillos (exactamente 35): id_platillo enteros del 1 al 35, precios 50-380 NIO, id_categoria válido (1 a 5), recetas auténticas nicaragüenses (carne asada, chancho con yuca, quesillo, nacatamal, vigorón, cacao, chicha, Toña, pío V, etc.).
    3. zonas (exactamente 12): id_zona enteros del 1 al 12 en Managua (Los Robles, Altamira, Villa Fontana, Las Colinas, Bello Horizonte, Bolonia, Linda Vista, Santo Domingo, Carretera Sur, Ciudad Jardín, Centroamérica, Rubenia), latitud 12.10-12.16, longitud -86.32 a -86.20, distancia_km 1-16.
    4. repartidores (exactamente 25): id_repartidor enteros del 1 al 25, nombres nicas, moto (18+), bicicleta (3-4), auto (3-4), calificacion 4.10-4.95.
    5. promociones (exactamente 12): id_promocion enteros del 1 al 12 año 2024 para optimización de mochila (costo 2500-16000 NIO, retorno 6500-48000 NIO).
    6. semantic_templates: al menos 12 notas_entrega vernáculas de Managua (del portón de la UCA, de donde fue el cine Cabrera, etc.), 8 motivos_cancelacion, 8 comentarios_retraso, 8 comentarios_exitosos.
    """

    console.print("[yellow]⏳ Solicitando paquete dimensional consolidado a Gemini...[/yellow]")
    bundle: AntojitosSeedBundle = generate_structured_data(client, prompt, AntojitosSeedBundle)

    save_json_file([c.model_dump() for c in bundle.categorias], seeds_dir / "categorias_platillo.json", dry_run)
    save_json_file([p.model_dump() for p in bundle.platillos], seeds_dir / "platillos_managua.json", dry_run)
    save_json_file([z.model_dump() for z in bundle.zonas], seeds_dir / "zonas_managua.json", dry_run)
    save_json_file([r.model_dump() for r in bundle.repartidores], seeds_dir / "repartidores_managua.json", dry_run)
    save_json_file([p.model_dump(mode="json") for p in bundle.promociones], seeds_dir / "promociones_knapsack.json", dry_run)
    save_json_file(bundle.semantic_templates.model_dump(), seeds_dir / "semantic_templates.json", dry_run)

    console.print("\n[bold green]✓ Todos los catálogos de Antojitos Express generados y guardados con 1 sola llamada API.[/bold green]")
    tracker.print_status()


def generate_antojitos_granular(seeds_dir: Path, target: str = "all", dry_run: bool = False):
    """Generate individual or sequential catalogs (uses multiple API requests)."""
    client = get_gemini_client()
    console.print(Panel.fit(
        f"[bold cyan]Antojitos Express - Generación Granular (Target: {target.upper()})[/bold cyan]",
        border_style="cyan"
    ))

    if target in ("all", "categorias"):
        console.print("[yellow]Generando Categorías...[/yellow]")
        prompt = "Genera exactamente 5 categorías oficiales con id_categoria enteros del 1 al 5 (1: Fritanga, 2: Quesillos, 3: Hamburguesas, 4: Bebidas, 5: Postres) para delivery en Managua."
        data = generate_structured_data(client, prompt, CategoriaCatalog)
        save_json_file([c.model_dump() for c in data.categorias], seeds_dir / "categorias_platillo.json", dry_run)

    if target in ("all", "platillos"):
        console.print("[yellow]Generando Platillos (35)...[/yellow]")
        prompt = "Genera exactamente 35 platillos nicaragüenses con id_platillo enteros del 1 al 35, precios NIO 50-380 y categorías válidas (id_categoria enteros 1 a 5)."
        data = generate_structured_data(client, prompt, PlatilloCatalog)
        save_json_file([p.model_dump() for p in data.platillos], seeds_dir / "platillos_managua.json", dry_run)

    if target in ("all", "zonas"):
        console.print("[yellow]Generando Zonas Urbanas de Managua (12)...[/yellow]")
        prompt = "Genera 12 zonas de entrega de Managua con id_zona enteros del 1 al 12 con coordenadas reales respecto a Los Robles."
        data = generate_structured_data(client, prompt, ZonaCatalog)
        save_json_file([z.model_dump() for z in data.zonas], seeds_dir / "zonas_managua.json", dry_run)

    if target in ("all", "repartidores"):
        console.print("[yellow]Generando Repartidores (25)...[/yellow]")
        prompt = "Genera 25 repartidores para Managua con id_repartidor enteros del 1 al 25 con moto, bici o auto y calificaciones 4.10-4.95."
        data = generate_structured_data(client, prompt, RepartidorCatalog)
        save_json_file([r.model_dump() for r in data.repartidores], seeds_dir / "repartidores_managua.json", dry_run)

    if target in ("all", "promociones"):
        console.print("[yellow]Generando Promociones Knapsack (12)...[/yellow]")
        prompt = "Genera 12 promociones con id_promocion enteros del 1 al 12 año 2024 para optimización de mochila."
        data = generate_structured_data(client, prompt, PromocionCatalog)
        save_json_file([p.model_dump(mode="json") for p in data.promociones], seeds_dir / "promociones_knapsack.json", dry_run)

    if target in ("all", "templates"):
        console.print("[yellow]Generando Plantillas Semánticas...[/yellow]")
        prompt = "Genera direcciones vernáculas de Managua, motivos de cancelación, quejas y reseñas positivas."
        data = generate_structured_data(client, prompt, SemanticTemplates)
        save_json_file(data.model_dump(), seeds_dir / "semantic_templates.json", dry_run)

    tracker.print_status()


def generate_antojitos_seeds(seeds_dir: Path, target: str = "all", granular: bool = False, dry_run: bool = False):
    """Main entry point: defaults to bundled generation for quota economy."""
    if granular or target != "all":
        generate_antojitos_granular(seeds_dir=seeds_dir, target=target, dry_run=dry_run)
    else:
        generate_antojitos_bundle(seeds_dir=seeds_dir, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description="Generar semillas sintéticas para Antojitos Express con Gemini API")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_SEEDS_DIR), help="Directorio destino para guardar semillas JSON")
    parser.add_argument("--target", type=str, choices=["all", "categorias", "platillos", "zonas", "repartidores", "promociones", "templates"], default="all")
    parser.add_argument("--granular", action="store_true", help="Usa llamadas API separadas por entidad en vez de 1 llamada consolidada")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta sin sobreescribir archivos JSON")
    args = parser.parse_args()

    generate_antojitos_seeds(Path(args.output_dir), target=args.target, granular=args.granular, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
