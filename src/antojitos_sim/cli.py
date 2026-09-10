"""CLI interface for Antojitos Express Synthetic Data Simulation Engine."""

import argparse
import logging
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from antojitos_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST,
    POSTGRES_SCHEMA,
)
from antojitos_sim.weather import get_daily_weather_series, start_mock_api_server
from antojitos_sim.generator import AntojitosSimulationEngine
from antojitos_sim.enrichment import SemanticEnricher
from antojitos_sim.exporter import export_to_csv, export_to_sql_dump, compute_simulation_summary
from antojitos_sim.pipeline import load_simulation_to_postgres

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("antojitos_sim")


def cmd_generate(args):
    """Run full synthetic data generation pipeline."""
    console.print(Panel.fit(
        "[bold cyan]Antojitos Express Synthetic Data Simulation[/bold cyan]\n"
        "[green]Managua, Nicaragua - Academic Data Pipeline Engine[/green]",
        border_style="cyan"
    ))

    # 1. Weather series
    with console.status("[bold yellow]Fetching/loading 2024 Managua weather from Open-Meteo..."):
        weather_df, clima_records = get_daily_weather_series()
        if args.days and args.days < len(weather_df):
            weather_df = weather_df.head(args.days)
            clima_records = clima_records[:args.days]

    console.print(f"[green]✓[/green] Weather series ready: [bold]{len(weather_df)}[/bold] days (2024).")

    # 2. Simulation engine
    with console.status(f"[bold yellow]Running numerical simulation (seed={args.seed})..."):
        engine = AntojitosSimulationEngine(random_seed=args.seed)
        orders, details = engine.run_simulation(weather_df)

    console.print(f"[green]✓[/green] Simulated: [bold]{len(orders):,}[/bold] orders, [bold]{len(details):,}[/bold] line items.")

    # 3. Semantic enrichment
    with console.status(f"[bold yellow]Applying semantic enrichment (live_llm={args.live_llm})..."):
        enricher = SemanticEnricher(
            templates=engine.semantic_templates,
            use_llm=args.live_llm,
            random_seed=args.seed,
        )
        orders = enricher.enrich_orders(orders)

    console.print("[green]✓[/green] Semantic enrichment completed.")

    # 4. Artifact exports
    with console.status("[bold yellow]Exporting CSVs and PostgreSQL SQL dump..."):
        csv_dir = Path(args.output_dir) if args.output_dir else CSV_ARTIFACTS_DIR
        csv_files = export_to_csv(
            zonas=engine.zonas,
            repartidores=engine.repartidores,
            categorias=engine.categorias,
            platillos=engine.platillos,
            promociones=engine.promociones,
            clima=clima_records,
            ordenes=orders,
            detalles=details,
            output_dir=csv_dir,
        )
        sql_file = export_to_sql_dump(csv_files)
        summary = compute_simulation_summary(
            ordenes=orders,
            detalles=details,
            clima=clima_records,
            platillos=engine.platillos,
            zonas=engine.zonas,
        )

    console.print(f"[green]✓[/green] CSV artifacts exported to: [bold]{csv_dir}[/bold]")
    console.print(f"[green]✓[/green] SQL script generated: [bold]{sql_file}[/bold]")

    # 5. Optional dlt load
    if args.load_db:
        with console.status(f"[bold yellow]Loading dataset into PostgreSQL via dlt ({args.schema})..."):
            load_simulation_to_postgres(
                zonas=engine.zonas,
                repartidores=engine.repartidores,
                categorias=engine.categorias,
                platillos=engine.platillos,
                promociones=engine.promociones,
                clima=clima_records,
                ordenes=orders,
                detalles=details,
                schema_name=args.schema,
            )
        console.print(f"[green]✓[/green] Successfully loaded into PostgreSQL schema '[bold]{args.schema}[/bold]'!")

    # Display summary table
    table = Table(title="Antojitos Express Simulation Summary (2024)", style="cyan")
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="green")

    table.add_row("City / Market", summary["city"])
    table.add_row("Date Range", f"{summary['date_range'][0]} to {summary['date_range'][1]}")
    table.add_row("Total Orders", f"{summary['total_orders']:,}")
    table.add_row("Total Line Items", f"{summary['total_line_items']:,}")
    table.add_row("Total Gross Revenue", f"C$ {summary['total_revenue_nio']:,.2f}")
    table.add_row("Delivered Orders", f"{summary['delivered_orders']:,}")
    table.add_row("Canceled Orders", f"{summary['canceled_orders']:,} ({summary['cancellation_rate_pct']}%)")
    table.add_row("Daily Orders (Avg / Min / Max)", f"{summary['daily_orders_mean']} / {summary['daily_orders_min']} / {summary['daily_orders_max']}")
    table.add_row("Rain-Demand Correlation (r)", f"{summary['weather_order_correlation']:.4f}")

    chi_res = summary["chi_square_test_zone_vs_category"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"
    table.add_row("Chi-Square Test (Zone vs Category)", f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}")

    console.print("\n", table, "\n")


def cmd_load(args):
    """Load pre-generated or fresh data into PostgreSQL."""
    console.print("[bold cyan]Running dlt pipeline load to PostgreSQL...[/bold cyan]")
    engine = AntojitosSimulationEngine(42)
    weather_df, clima_records = get_daily_weather_series()
    orders, details = engine.run_simulation(weather_df)
    enricher = SemanticEnricher(engine.semantic_templates)
    orders = enricher.enrich_orders(orders)

    load_simulation_to_postgres(
        zonas=engine.zonas,
        repartidores=engine.repartidores,
        categorias=engine.categorias,
        platillos=engine.platillos,
        promociones=engine.promociones,
        clima=clima_records,
        ordenes=orders,
        detalles=details,
        schema_name=args.schema,
    )
    console.print(f"[bold green]Data loaded into PostgreSQL schema '{args.schema}'.[/bold green]")


def cmd_mock_api(args):
    """Run Mock Open-Meteo API server for student ingesta.sh scripts."""
    start_mock_api_server(host=args.host, port=args.port)


def cmd_inspect(args):
    """Inspect generated simulation summary."""
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
        prog="antojitos-sim",
        description="Antojitos Express Synthetic Data Simulation CLI (Managua, Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 synthetic data facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate (default: full year 366)")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for dynamic enrichment")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(CSV_ARTIFACTS_DIR), help="Output directory for CSVs")
    gen_parser.set_defaults(func=cmd_generate)

    # load
    load_parser = subparsers.add_parser("load", help="Load data into PostgreSQL via dlt")
    load_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL schema")
    load_parser.set_defaults(func=cmd_load)

    # mock-api
    mock_parser = subparsers.add_parser("mock-api", help="Serve Open-Meteo mock HTTP endpoint for ingesta.sh")
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
