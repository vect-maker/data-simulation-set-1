"""CLI interface for MoviGo Ride-Hailing Simulation Engine (Managua)."""

import argparse
import logging
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from movigo_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST,
    POSTGRES_SCHEMA,
)
from movigo_sim.weather import get_movigo_weather_series, start_movigo_mock_api_server
from movigo_sim.generator import MoviGoSimulationEngine
from movigo_sim.enrichment import MoviGoSemanticEnricher
from movigo_sim.exporter import export_movigo_to_csv, export_movigo_to_sql_dump, compute_movigo_simulation_summary
from movigo_sim.pipeline import load_movigo_to_postgres

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("movigo_sim")


def cmd_generate(args):
    """Run full MoviGo simulation pipeline."""
    console.print(Panel.fit(
        "[bold magenta]MoviGo - Simulación de Transporte por Aplicación[/bold magenta]\n"
        "[yellow]Área Urbana de Managua, Nicaragua - Pipeline de Movilidad[/yellow]",
        border_style="magenta"
    ))

    # 1. Weather series
    with console.status("[bold yellow]Fetching/loading Managua weather & traffic from Open-Meteo..."):
        weather_df, clima_records = get_movigo_weather_series()
        if args.days and args.days < len(weather_df):
            weather_df = weather_df.head(args.days)
            clima_records = clima_records[:args.days]

    console.print(f"[green]✓[/green] Weather & traffic series ready: [bold]{len(weather_df)}[/bold] days (2024).")

    # 2. Simulation engine
    with console.status(f"[bold yellow]Running ride-hailing simulation (seed={args.seed})..."):
        engine = MoviGoSimulationEngine(random_seed=args.seed)
        viajes, telemetria = engine.run_simulation(weather_df)

    console.print(
        f"[green]✓[/green] Generated: [bold]{len(viajes):,}[/bold] ride requests, "
        f"[bold]{len(telemetria):,}[/bold] driver telemetry pings."
    )

    # 3. Semantic enrichment
    with console.status("[bold yellow]Enriching cancellation reasons..."):
        enricher = MoviGoSemanticEnricher(
            templates=engine.templates,
            use_llm=args.live_llm,
            random_seed=args.seed,
        )
        viajes = enricher.enrich_trips(viajes)

    console.print("[green]✓[/green] Semantic enrichment completed.")

    # 4. Artifact exports
    with console.status("[bold yellow]Exporting CSVs and PostgreSQL SQL dump..."):
        csv_dir = Path(args.output_dir) if args.output_dir else CSV_ARTIFACTS_DIR
        csv_files = export_movigo_to_csv(
            zonas=engine.zonas,
            usuarios=engine.usuarios,
            conductores=engine.conductores,
            viajes=viajes,
            telemetria=telemetria,
            campanas=engine.campanas,
            clima=clima_records,
            output_dir=csv_dir,
        )
        sql_file = export_movigo_to_sql_dump(csv_files)
        summary = compute_movigo_simulation_summary(
            zonas=engine.zonas,
            viajes=viajes,
            clima=clima_records,
            campanas=engine.campanas,
        )

    console.print(f"[green]✓[/green] CSV artifacts exported to: [bold]{csv_dir}[/bold]")
    console.print(f"[green]✓[/green] SQL script generated: [bold]{sql_file}[/bold]")

    # 5. Optional dlt load
    if args.load_db:
        with console.status(f"[bold yellow]Loading dataset into PostgreSQL via dlt ({args.schema})..."):
            load_movigo_to_postgres(
                zonas=engine.zonas,
                usuarios=engine.usuarios,
                conductores=engine.conductores,
                viajes=viajes,
                telemetria=telemetria,
                campanas=engine.campanas,
                clima=clima_records,
                schema_name=args.schema,
            )
        console.print(f"[green]✓[/green] Successfully loaded into PostgreSQL schema '[bold]{args.schema}[/bold]'!")

    # Display summary table
    table = Table(title="MoviGo - Simulation Summary (Managua 2024)", style="magenta")
    table.add_column("Metric", style="bold white")
    table.add_column("Value", style="cyan")

    table.add_row("Case Name", summary["case_name"])
    table.add_row("City / Urban Area", summary["city"])
    table.add_row("Date Range", f"{summary['date_range'][0]} to {summary['date_range'][1]}")
    table.add_row("Total Ride Requests", f"{summary['total_trips']:,}")
    table.add_row("Completed Rides", f"{summary['completed_trips']:,}")
    table.add_row("Canceled Rides", f"{summary['canceled_trips']:,} ({summary['cancellation_rate_pct']}%)")
    table.add_row("Gross Revenue", f"C$ {summary['total_gross_revenue_nio']:,.2f} NIO")

    averages = summary["trip_averages"]
    table.add_row("Avg Fare / Distance / Duration", f"C$ {averages['fare_nio']} | {averages['distance_km']} km | {averages['duration_minutes']} min")
    table.add_row("Avg Surge Multiplier", f"{averages['surge_multiplier']:.2f}x")

    corrs = summary["continuous_correlations"]
    table.add_row("Rain & Congestion Demand Correlation", f"Rain (r): {corrs['rain_vs_daily_demand']:.4f} | Congestion (r): {corrs['congestion_vs_daily_demand']:.4f}")

    chi_res = summary["chi_square_test_payment_method_vs_stratum"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"
    table.add_row(
        "Chi-Square Test (Payment Method vs Stratum)",
        f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}"
    )

    knap = summary["knapsack_incentive_campaigns"]
    table.add_row(
        "Knapsack Incentive Campaigns",
        f"{knap['total_campaigns']} campañas | Cost: C$ {knap['total_budget_cost_nio']:,.0f} | Return: {knap['total_expected_driver_hours']:,.0f} hrs conexión"
    )

    console.print("\n", table, "\n")


def cmd_load(args):
    """Load MoviGo dataset into PostgreSQL via dlt."""
    console.print("[bold cyan]Running dlt pipeline load for MoviGo...[/bold cyan]")
    engine = MoviGoSimulationEngine(42)
    weather_df, clima_records = get_movigo_weather_series()
    viajes, telemetria = engine.run_simulation(weather_df)
    enricher = MoviGoSemanticEnricher(engine.templates)
    viajes = enricher.enrich_trips(viajes)

    load_movigo_to_postgres(
        zonas=engine.zonas,
        usuarios=engine.usuarios,
        conductores=engine.conductores,
        viajes=viajes,
        telemetria=telemetria,
        campanas=engine.campanas,
        clima=clima_records,
        schema_name=args.schema,
    )
    console.print(f"[bold green]Data loaded into PostgreSQL schema '{args.schema}'.[/bold green]")


def cmd_mock_api(args):
    """Run Mock Open-Meteo Weather & Traffic API server for student ingesta.sh scripts."""
    start_movigo_mock_api_server(host=args.host, port=args.port)


def cmd_inspect(args):
    """Inspect MoviGo simulation metrics and statistical properties."""
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
        prog="movigo-sim",
        description="MoviGo Synthetic Ride-Hailing Simulation CLI (Managua, Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 ride-hailing facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Days to simulate (default: 366)")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for dynamic enrichment")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(CSV_ARTIFACTS_DIR), help="Output directory for CSVs")
    gen_parser.set_defaults(func=cmd_generate)

    # load
    load_parser = subparsers.add_parser("load", help="Load ride data into PostgreSQL via dlt")
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
