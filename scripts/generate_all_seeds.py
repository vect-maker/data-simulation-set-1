"""Master runner script to generate authentic catalog seeds for all simulations using Gemini API.

Optimized for Google Gemini Free Tier limits:
- Bundled Mode (Default): Only 1 consolidated API request per case (3 requests total for the entire project).
- Automatic Inter-case Rate Pacing (12s delay) to stay well under 5 Requests Per Minute (RPM).
- Quota Tracker to monitor daily request budget.
"""

import argparse
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

from scripts.common import tracker
from scripts.generate_antojitos_seeds import generate_antojitos_seeds, DEFAULT_SEEDS_DIR as ANTOJITOS_SEEDS_DIR
from scripts.generate_volcan_seeds import generate_volcan_seeds, DEFAULT_SEEDS_DIR as VOLCAN_SEEDS_DIR
from scripts.generate_movigo_seeds import generate_movigo_seeds, DEFAULT_SEEDS_DIR as MOVIGO_SEEDS_DIR

console = Console()


def run_generators(case: str = "all", granular: bool = False, dry_run: bool = False, inter_delay: float = 12.0):
    """Run specified seed generators with rate pacing."""
    start_time = time.time()

    mode_label = "GRANULAR (Múltiples llamadas)" if granular else "BUNDLED CONSOLIDADO (1 llamada por caso)"
    console.print(Panel.fit(
        "[bold cyan]Synthetic Data Simulation - Master Gemini Seed Generator[/bold cyan]\n"
        f"[yellow]Modo:[/yellow] {mode_label} | [yellow]Caso:[/yellow] [bold green]{case.upper()}[/bold green]\n"
        f"[white]Optimizado para cuota gratuita de Gemini (Rate Limit 5 RPM / 20 RPD)[/white]",
        border_style="cyan"
    ))

    generators = []
    if case in ("all", "antojitos"):
        generators.append(("Antojitos Express", generate_antojitos_seeds, ANTOJITOS_SEEDS_DIR))
    if case in ("all", "volcan"):
        generators.append(("Cooperativa El Volcán", generate_volcan_seeds, VOLCAN_SEEDS_DIR))
    if case in ("all", "movigo"):
        generators.append(("MoviGo", generate_movigo_seeds, MOVIGO_SEEDS_DIR))

    for idx, (name, func, path) in enumerate(generators, 1):
        console.rule(f"[bold blue][{idx}/{len(generators)}] Generando catálogo: {name}[/bold blue]")
        try:
            func(seeds_dir=path, granular=granular, dry_run=dry_run)
        except Exception as e:
            console.print(f"[bold red]✗ Falló la generación para {name}: {e}[/bold red]")
            raise e

        # Inter-case delay to avoid 5 RPM rate limit if there are more cases remaining
        if idx < len(generators) and inter_delay > 0:
            console.print(f"[dim]⏳ Pausa preventiva de {inter_delay:.0f}s para cumplir límite de 5 RPM...[/dim]")
            time.sleep(inter_delay)

    elapsed = time.time() - start_time
    console.print(Panel.fit(
        f"[bold green]✓ Generación completada con éxito en {elapsed:.1f}s[/bold green]\n"
        f"[white]Peticiones realizadas: [/white][bold cyan]{tracker.requests_made}[/bold cyan] | "
        f"[white]Uso de cuota diaria estimada: [/white][bold green]{(tracker.requests_made / tracker.daily_limit) * 100:.1f}%[/bold green]",
        border_style="green"
    ))


def main():
    parser = argparse.ArgumentParser(description="Generar semillas sintéticas con Gemini para los casos del proyecto")
    parser.add_argument(
        "--case",
        type=str,
        choices=["all", "antojitos", "volcan", "movigo"],
        default="all",
        help="Caso específico a generar o 'all' para todos (default: all)",
    )
    parser.add_argument(
        "--granular",
        action="store_true",
        help="Usa llamadas API separadas por entidad en vez del paquete consolidado",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=12.0,
        help="Segundos de pausa preventiva entre casos para respetar límite de 5 RPM (default: 12.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta y muestra en consola sin sobreescribir archivos JSON",
    )
    args = parser.parse_args()
    run_generators(case=args.case, granular=args.granular, dry_run=args.dry_run, inter_delay=args.delay)


if __name__ == "__main__":
    main()
