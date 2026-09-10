"""CLI interface for Cooperativa El Volcán Coffee Simulation Engine."""

import argparse
import logging
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from volcan_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST,
    POSTGRES_SCHEMA,
)
from volcan_sim.weather import get_coffee_weather_series, start_volcan_mock_api_server
from volcan_sim.generator import VolcanSimulationEngine
from volcan_sim.enrichment import VolcanSemanticEnricher
from volcan_sim.exporter import export_volcan_to_csv, export_volcan_to_sql_dump, compute_volcan_simulation_summary
from volcan_sim.pipeline import load_volcan_to_postgres

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("volcan_sim")


def cmd_generate(args):
    """Run full coffee simulation pipeline."""
    console.print(Panel.fit(
        "[bold green]Cooperativa El Volcán - Simulación Cafetalera[/bold green]\n"
        "[cyan]Zonas Cafetaleras de Nicaragua (Jinotega, Matagalpa, Dipilto, Madriz)[/cyan]",
        border_style="green"
    ))

    # 1. Weather series
    with console.status("[bold yellow]Fetching/loading Jinotega agro-weather from Open-Meteo..."):
        weather_df, clima_records = get_coffee_weather_series()
        if args.days and args.days < len(weather_df):
            weather_df = weather_df.head(args.days)
            clima_records = clima_records[:args.days]

    console.print(f"[green]✓[/green] Agro-weather ready: [bold]{len(weather_df)}[/bold] days (2024).")

    # 2. Simulation engine
    with console.status(f"[bold yellow]Running agricultural simulation (seed={args.seed})..."):
        engine = VolcanSimulationEngine(random_seed=args.seed)
        lotes, procesos, subastas, embarques = engine.run_simulation(weather_df)

    console.print(
        f"[green]✓[/green] Generated: [bold]{len(lotes):,}[/bold] harvest lots, "
        f"[bold]{len(procesos):,}[/bold] milling stages, [bold]{len(embarques):,}[/bold] export shipments."
    )

    # 3. Semantic enrichment
    with console.status("[bold yellow]Enriching with SCAA cupping notes and observations..."):
        enricher = VolcanSemanticEnricher(
            templates=engine.notes_templates,
            use_llm=args.live_llm,
            random_seed=args.seed,
        )
        lotes, procesos = enricher.enrich_lots_and_processes(lotes, procesos)

    console.print("[green]✓[/green] SCAA cupping notes enriched.")

    # 4. Artifact exports
    with console.status("[bold yellow]Exporting CSVs and PostgreSQL SQL dump..."):
        csv_dir = Path(args.output_dir) if args.output_dir else CSV_ARTIFACTS_DIR
        csv_files = export_volcan_to_csv(
            fincas=engine.fincas,
            variedades=engine.variedades,
            beneficios=engine.beneficios,
            cuadrillas=engine.cuadrillas,
            lotes=lotes,
            procesos=procesos,
            subastas=subastas,
            embarques=embarques,
            clima=clima_records,
            output_dir=csv_dir,
        )
        sql_file = export_volcan_to_sql_dump(csv_files)
        summary = compute_volcan_simulation_summary(
            fincas=engine.fincas,
            variedades=engine.variedades,
            lotes=lotes,
            embarques=embarques,
            subastas=subastas,
        )

    console.print(f"[green]✓[/green] CSV artifacts exported to: [bold]{csv_dir}[/bold]")
    console.print(f"[green]✓[/green] SQL script generated: [bold]{sql_file}[/bold]")

    # 5. Optional dlt load
    if args.load_db:
        with console.status(f"[bold yellow]Loading dataset into PostgreSQL via dlt ({args.schema})..."):
            load_volcan_to_postgres(
                fincas=engine.fincas,
                variedades=engine.variedades,
                beneficios=engine.beneficios,
                cuadrillas=engine.cuadrillas,
                lotes=lotes,
                procesos=procesos,
                subastas=subastas,
                embarques=embarques,
                clima=clima_records,
                schema_name=args.schema,
            )
        console.print(f"[green]✓[/green] Successfully loaded into PostgreSQL schema '[bold]{args.schema}[/bold]'!")

    # Display summary table
    table = Table(title="Cooperativa El Volcán - Simulation Summary (2024)", style="green")
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="cyan")

    table.add_row("Case Name", summary["case_name"])
    table.add_row("Coffee Regions", ", ".join(summary["coffee_regions"]))
    table.add_row("Export Gateway", summary["export_port"])
    table.add_row("Total Participating Farms", f"{summary['total_farms']}")
    table.add_row("Total Harvested Lots", f"{summary['total_harvest_lots']:,}")
    table.add_row("Cherry Harvested", f"{summary['total_cherry_harvested_kg']:,.2f} kg")
    table.add_row("Green Coffee Exported", f"{summary['total_green_coffee_exported_qq']:,.2f} qq")
    table.add_row("Gross Export Revenue", f"USD ${summary['total_export_revenue_usd']:,.2f}")

    scaa_stats = summary["scaa_cupping_scores"]
    table.add_row(
        "SCAA Cupping Score (Avg / Min / Max)",
        f"{scaa_stats['mean']} / {scaa_stats['min']} / {scaa_stats['max']}"
    )
    table.add_row("Altitude vs SCAA Correlation (r)", f"{scaa_stats['correlation_with_altitude']:.4f}")

    chi_res = summary["chi_square_test_variety_vs_region"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"
    table.add_row(
        "Chi-Square Test (Variety vs Region)",
        f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}"
    )

    knap = summary["knapsack_auction_micro_lots"]
    table.add_row(
        "Knapsack Auction Micro-lots",
        f"{knap['total_lots']} lotes | {knap['total_weight_qq']} qq | Cost: ${knap['total_certification_cost_usd']:,.0f} | Return: ${knap['total_expected_return_usd']:,.0f}"
    )

    console.print("\n", table, "\n")


def cmd_load(args):
    """Load coffee dataset into PostgreSQL via dlt."""
    console.print("[bold cyan]Running dlt pipeline load for Cooperativa El Volcán...[/bold cyan]")
    engine = VolcanSimulationEngine(42)
    weather_df, clima_records = get_coffee_weather_series()
    lotes, procesos, subastas, embarques = engine.run_simulation(weather_df)
    enricher = VolcanSemanticEnricher(engine.notes_templates)
    lotes, procesos = enricher.enrich_lots_and_processes(lotes, procesos)

    load_volcan_to_postgres(
        fincas=engine.fincas,
        variedades=engine.variedades,
        beneficios=engine.beneficios,
        cuadrillas=engine.cuadrillas,
        lotes=lotes,
        procesos=procesos,
        subastas=subastas,
        embarques=embarques,
        clima=clima_records,
        schema_name=args.schema,
    )
    console.print(f"[bold green]Data loaded into PostgreSQL schema '{args.schema}'.[/bold green]")


def cmd_mock_api(args):
    """Run Mock Open-Meteo Agro-weather API server for student ingesta.sh scripts."""
    start_volcan_mock_api_server(host=args.host, port=args.port)


def cmd_inspect(args):
    """Inspect simulation metrics and statistical properties."""
    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    if not summary_path.exists():
        console.print(f"[red]Error: Summary file {summary_path} not found. Run 'generate' first.[/red]")
        sys.exit(1)

    import json
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    console.print_json(data=summary)


def main():
    parser = argparse.ArgumentParser(
        prog="volcan-sim",
        description="Cooperativa El Volcán Synthetic Coffee Simulation CLI (Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 coffee supply chain facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Days to simulate (default: 366)")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for dynamic enrichment")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(CSV_ARTIFACTS_DIR), help="Output directory for CSVs")
    gen_parser.set_defaults(func=cmd_generate)

    # load
    load_parser = subparsers.add_parser("load", help="Load coffee data into PostgreSQL via dlt")
    load_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL schema")
    load_parser.set_defaults(func=cmd_load)

    # mock-api
    mock_parser = subparsers.add_parser("mock-api", help="Serve Open-Meteo Jinotega mock HTTP endpoint for ingesta.sh")
    mock_parser.add_argument("--host", type=str, default=MOCK_API_HOST, help="Host to bind")
    mock_parser.add_argument("--port", type=int, default=MOCK_API_PORT, help="Port to listen on")
    mock_parser.set_defaults(func=cmd_mock_api)

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect simulation metrics and statistical tests")
    inspect_parser.set_defaults(func=cmd_inspect)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
