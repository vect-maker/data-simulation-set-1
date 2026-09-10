"""CLI interface for MoviGo Synthetic Data Simulation Engine (Managua, Nicaragua)."""

import argparse
import json
import logging
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from data_sim.core.reporting import (
    render_operational_table,
    render_statistical_table,
    render_math_optimization_table,
)
from movigo_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    RAW_DATA_DIR,
    POSTGRES_SCHEMA,
)
from movigo_sim.weather import (
    get_movigo_weather_series,
    fetch_movigo_weather_archive,
)
from movigo_sim.generator import MoviGoSimulationEngine
from movigo_sim.enrichment import MoviGoSemanticEnricher
from movigo_sim.exporter import (
    export_movigo_to_csv,
    export_movigo_to_sql_dump,
    compute_movigo_simulation_summary,
)
from movigo_sim.pipeline import load_movigo_to_postgres

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("movigo_sim")


def display_movigo_rich_summary(summary: dict):
    """Render comprehensive multi-pillar academic report for MoviGo."""
    # 1. Operational Metrics
    averages = summary["trip_averages"]
    corrs = summary["continuous_correlations"]
    chi_res = summary["chi_square_test_payment_method_vs_stratum"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"

    ops_rows = [
        ("Caso de Estudio", summary["case_name"]),
        ("Área Urbana", summary["city"]),
        ("Rango de Fechas", f"{summary['date_range'][0]} a {summary['date_range'][1]}"),
        ("Total Solicitudes de Viaje", f"{summary['total_trips']:,}"),
        ("Viajes Completados", f"{summary['completed_trips']:,}"),
        ("Viajes Cancelados", f"{summary['canceled_trips']:,} ({summary['cancellation_rate_pct']}%)"),
        ("Ingreso Bruto Total", f"C$ {summary['total_gross_revenue_nio']:,.2f} NIO"),
        ("Promedios (Tarifa / Distancia / Duración)", f"C$ {averages['fare_nio']} | {averages['distance_km']} km | {averages['duration_minutes']} min"),
        ("Multiplicador Dinámico Medio", f"{averages['surge_multiplier']:.2f}x"),
        ("Correlación Lluvia y Congestión", f"Lluvia (r): {corrs['rain_vs_daily_demand']:.4f} | Congestión (r): {corrs['congestion_vs_daily_demand']:.4f}"),
        ("Ji-Cuadrado (Pago vs Estrato)", f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}"),
    ]
    render_operational_table("MoviGo: Resumen de Operaciones y Movilidad Urbana (Managua 2024)", ops_rows, border_style="magenta")

    # 2. Estadística II: Regresión y Supuestos OLS
    if "estadistica_ii" in summary:
        est = summary["estadistica_ii"]
        render_statistical_table(
            "Estadística II: Regresión Lluvia vs Demanda y Pruebas de Hipótesis",
            est.get("validacion_supuestos", est.get("validacion_supuestos_ols", {})),
            est.get("bateria_pruebas_hipotesis", []),
            border_style="magenta",
        )

    # 3. Métodos Numéricos & Optimización
    if "metodos_numericos" in summary and "optimizacion" in summary:
        num = summary["metodos_numericos"]
        opt = summary["optimizacion"]
        eq = num.get("equilibrio_mercado_raices", {})
        elast = num.get("diferenciacion_numerica_elasticidad", {})
        hung = opt.get("algoritmo_hungaro_despacho", {})
        dijk = opt.get("ruta_mas_corta_red_vial", {})

        math_rows = [
            ("Raíces (Multiplicador de Equilibrio)", f"Bisección: {eq.get('multiplicador_optimo_biseccion')}x | Newton: {eq.get('multiplicador_optimo_newton')}x ({eq.get('interpretacion')})"),
            ("Diferenciación (Elasticidad Tarifa)", f"ε_p({elast.get('multiplicador_evaluado')}x) = {elast.get('elasticidad_precio_demanda')} -> {elast.get('clasificacion')}"),
            ("Asignación Conductores (Húngaro)", f"Tiempo Total Espera: {hung.get('tiempo_total_espera_minutos')} min | Ahorro Medio: {hung.get('ahorro_promedio_por_viaje_min')} min/viaje"),
            ("Ruta Más Corta (Dijkstra Managua)", f"{dijk.get('origen')} -> {dijk.get('destino')} | {dijk.get('distancia_optima_km')} km ({dijk.get('tiempo_viaje_condicion_normal_min')} min despejado / {dijk.get('tiempo_viaje_congestion_lluvia_min')} min lluvia)"),
        ]
        render_math_optimization_table("Métodos Numéricos & Optimización Prescriptiva", math_rows, border_style="cyan")


def run_generation(days=None, seed=42, live_llm=False, load_db=False, schema=POSTGRES_SCHEMA, output_dir=None):
    """Programmatic entry point for MoviGo simulation generation."""
    weather_df, clima_records = get_movigo_weather_series()
    if days and days < len(weather_df):
        weather_df = weather_df.head(days)
        clima_records = clima_records[:days]

    engine = MoviGoSimulationEngine(random_seed=seed)
    viajes, telemetria = engine.run_simulation(weather_df)

    enricher = MoviGoSemanticEnricher(
        templates=engine.templates,
        use_llm=live_llm,
        random_seed=seed,
    )
    viajes = enricher.enrich_trips(viajes)

    csv_dir = Path(output_dir) if output_dir else CSV_ARTIFACTS_DIR
    csv_files = export_movigo_to_csv(
        zonas=engine.zonas,
        usuarios=engine.usuarios,
        conductores=engine.conductores,
        campanas=engine.campanas,
        clima=clima_records,
        viajes=viajes,
        telemetria=telemetria,
        output_dir=csv_dir,
    )
    sql_file = export_movigo_to_sql_dump(csv_files)
    summary = compute_movigo_simulation_summary(
        zonas=engine.zonas,
        viajes=viajes,
        clima=clima_records,
        campanas=engine.campanas,
    )

    if load_db:
        load_movigo_to_postgres(
            zonas=engine.zonas,
            usuarios=engine.usuarios,
            conductores=engine.conductores,
            campanas=engine.campanas,
            clima=clima_records,
            viajes=viajes,
            telemetria=telemetria,
            schema_name=schema,
        )

    return summary


def run_inspection():
    """Programmatic entry point for inspecting summary."""
    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    if not summary_path.exists():
        console.print(f"[red]Error: Summary file {summary_path} not found. Run 'generate' first.[/red]")
        sys.exit(1)

    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)
    display_movigo_rich_summary(summary)


def run_loading(schema=POSTGRES_SCHEMA):
    """Programmatic entry point for loading to PostgreSQL."""
    engine = MoviGoSimulationEngine(42)
    weather_df, clima_records = get_movigo_weather_series()
    viajes, telemetria = engine.run_simulation(weather_df)
    enricher = MoviGoSemanticEnricher(engine.templates)
    viajes = enricher.enrich_trips(viajes)

    load_movigo_to_postgres(
        zonas=engine.zonas,
        usuarios=engine.usuarios,
        conductores=engine.conductores,
        campanas=engine.campanas,
        clima=clima_records,
        viajes=viajes,
        telemetria=telemetria,
        schema_name=schema,
    )


def cmd_generate(args):
    """CLI handler for generate."""
    console.print(Panel.fit(
        "[bold magenta]MoviGo Synthetic Data Simulation[/bold magenta]\n"
        "[cyan]Urban Mobility and Algorithmic Dispatch Engine (Managua, Nicaragua)[/cyan]",
        border_style="magenta"
    ))
    summary = run_generation(
        days=args.days,
        seed=args.seed,
        live_llm=args.live_llm,
        load_db=args.load_db,
        schema=args.schema,
        output_dir=args.output_dir,
    )
    display_movigo_rich_summary(summary)


def cmd_load(args):
    """CLI handler for load."""
    run_loading(schema=args.schema)
    console.print(f"[bold green]Data loaded into PostgreSQL schema '{args.schema}'.[/bold green]")


def cmd_inspect(args):
    """CLI handler for inspect."""
    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    if not summary_path.exists():
        console.print(f"[red]Error: Summary file {summary_path} not found. Run 'generate' first.[/red]")
        sys.exit(1)

    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)

    if getattr(args, "json", False):
        console.print_json(data=summary)
    else:
        display_movigo_rich_summary(summary)


def cmd_fetch_weather(args):
    """CLI handler for fetch-weather."""
    console.print("[bold cyan]Fetching weather & traffic series from Open-Meteo API for Managua...[/bold cyan]")
    fetch_movigo_weather_archive(force_refresh=True)
    console.print(f"[bold green]✓ Successfully fetched and saved weather to {RAW_DATA_DIR / 'clima_managua_movigo_2024.json'}[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        prog="movigo-sim",
        description="MoviGo Synthetic Data Simulation CLI (Managua, Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 urban rides & telemetry facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate")
    gen_parser.add_argument("--refresh-weather", action="store_true", help="Force refresh weather from Open-Meteo")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for trip reviews")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(CSV_ARTIFACTS_DIR), help="Output directory for CSVs")
    gen_parser.set_defaults(func=cmd_generate)

    # fetch-weather
    weather_parser = subparsers.add_parser("fetch-weather", help="Fetch fresh weather data from Open-Meteo API")
    weather_parser.set_defaults(func=cmd_fetch_weather)

    # load
    load_parser = subparsers.add_parser("load", help="Load data into PostgreSQL via dlt")
    load_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL schema")
    load_parser.set_defaults(func=cmd_load)

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect simulation metrics and statistical tests")
    inspect_parser.add_argument("--json", action="store_true", help="Output raw JSON instead of tables")
    inspect_parser.set_defaults(func=cmd_inspect)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
