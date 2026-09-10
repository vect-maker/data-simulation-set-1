"""CLI interface for Antojitos Express Synthetic Data Simulation Engine."""

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
from antojitos_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    RAW_DATA_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST,
    POSTGRES_SCHEMA,
)
from antojitos_sim.weather import get_daily_weather_series, fetch_open_meteo_archive, start_mock_api_server
from antojitos_sim.generator import AntojitosSimulationEngine
from antojitos_sim.enrichment import SemanticEnricher
from antojitos_sim.exporter import export_to_csv, export_to_sql_dump, compute_simulation_summary
from antojitos_sim.pipeline import load_simulation_to_postgres

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("antojitos_sim")


def display_rich_summary(summary: dict):
    """Render comprehensive multi-pillar academic report using Rich tables."""
    # 1. General Operational Metrics
    chi_res = summary["chi_square_test_zone_vs_category"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"

    ops_rows = [
        ("Ciudad / Mercado", summary["city"]),
        ("Rango de Fechas", f"{summary['date_range'][0]} a {summary['date_range'][1]}"),
        ("Total Órdenes Generadas", f"{summary['total_orders']:,}"),
        ("Total Líneas de Detalle", f"{summary['total_line_items']:,}"),
        ("Ingreso Bruto Total", f"C$ {summary['total_revenue_nio']:,.2f}"),
        ("Órdenes Entregadas", f"{summary['delivered_orders']:,}"),
        ("Órdenes Canceladas", f"{summary['canceled_orders']:,} ({summary['cancellation_rate_pct']}%)"),
        ("Órdenes Diarias (Media / Min / Max)", f"{summary['daily_orders_mean']} / {summary['daily_orders_min']} / {summary['daily_orders_max']}"),
        ("Correlación Lluvia-Demanda (r)", f"{summary['weather_order_correlation']:.4f}"),
        ("Ji-Cuadrado (Zona vs Categoría)", f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}"),
    ]
    render_operational_table("Antojitos Express: Métricas Operativas y Demanda (2024)", ops_rows, border_style="cyan")

    # 2. Estadística II: Regresión y Supuestos OLS
    if "estadistica_ii" in summary:
        est = summary["estadistica_ii"]
        render_statistical_table(
            "Estadística II: Supuestos OLS y Pruebas de Hipótesis",
            est.get("validacion_supuestos", {}),
            est.get("bateria_pruebas_hipotesis", []),
            border_style="magenta",
        )

    # 3. Métodos Numéricos & Optimización
    if "metodos_numericos" in summary and "optimizacion" in summary:
        num = summary["metodos_numericos"]
        opt = summary["optimizacion"]
        raices = num.get("ecuaciones_no_lineales_raices", {})
        elast = num.get("diferenciacion_numerica_elasticidad", {})
        integ = num.get("integración_numerica_demanda", num.get("integracion_numerica_demanda", {}))
        pl = opt.get("programacion_lineal_simplex", {})
        hung = opt.get("algoritmo_hungaro_asignacion", {})

        math_rows = [
            ("Raíces (Punto Equilibrio Cocina)", f"Bisección: {raices.get('raiz_biseccion_ordenes')} órdenes | Newton: {raices.get('raiz_newton_raphson_ordenes')} órdenes | Óptimo q*={raices.get('q_optimo_maximo_beneficio')}"),
            ("Diferenciación (Elasticidad)", f"ε_p({elast.get('precio_evaluado_nio')} NIO) = {elast.get('elasticidad_precio_demanda')} -> {elast.get('clasificacion')}"),
            ("Integración Numérica (Simpson)", f"Simpson: {integ.get('integral_regla_simpson_compuesta')} | Real: {integ.get('suma_discreta_real')} (Error: {integ.get('error_relativo_simpson_pct')}%)"),
            ("Programación Lineal (Simplex)", f"Margen Máx: C$ {pl.get('margen_maximo_nio'):,.2f} | Precios Sombra: {pl.get('precios_sombra_restricciones')}"),
            ("Asignación Couriers (Húngaro)", f"Tiempo global óptimo de respuesta: {hung.get('tiempo_total_minutos')} minutos ({hung.get('matriz_dimension')})"),
        ]
        render_math_optimization_table("Métodos Numéricos & Optimización Prescriptiva", math_rows, border_style="green")


def run_generation(days=None, seed=42, live_llm=False, load_db=False, schema=POSTGRES_SCHEMA, output_dir=None):
    """Programmatic entry point for Antojitos simulation generation."""
    weather_df, clima_records = get_daily_weather_series()
    if days and days < len(weather_df):
        weather_df = weather_df.head(days)
        clima_records = clima_records[:days]

    engine = AntojitosSimulationEngine(random_seed=seed)
    orders, details = engine.run_simulation(weather_df)

    enricher = SemanticEnricher(templates=engine.semantic_templates, use_llm=live_llm, random_seed=seed)
    orders = enricher.enrich_orders(orders)

    csv_dir = Path(output_dir) if output_dir else CSV_ARTIFACTS_DIR
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
        repartidores=engine.repartidores,
    )

    if load_db:
        load_simulation_to_postgres(
            zonas=engine.zonas,
            repartidores=engine.repartidores,
            categorias=engine.categorias,
            platillos=engine.platillos,
            promociones=engine.promociones,
            clima=clima_records,
            ordenes=orders,
            detalles=details,
            schema_name=schema,
        )

    return summary


def run_inspection():
    """Programmatic entry point for inspecting summary."""
    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    if not summary_path.exists():
        console.print(f"[red]Error: Summary file {summary_path} not found. Run 'generate' first.[/red]")
        sys.exit(1)

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
    display_rich_summary(summary)


def run_loading(schema=POSTGRES_SCHEMA):
    """Programmatic entry point for loading to PostgreSQL."""
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
        schema_name=schema,
    )


def cmd_generate(args):
    """CLI handler for generate."""
    console.print(Panel.fit(
        "[bold cyan]Antojitos Express Synthetic Data Simulation[/bold cyan]\n"
        "[green]Managua, Nicaragua - Academic Data Pipeline Engine[/green]",
        border_style="cyan"
    ))
    summary = run_generation(
        days=args.days,
        seed=args.seed,
        live_llm=args.live_llm,
        load_db=args.load_db,
        schema=args.schema,
        output_dir=args.output_dir,
    )
    display_rich_summary(summary)


def cmd_load(args):
    """CLI handler for load."""
    run_loading(schema=args.schema)
    console.print(f"[bold green]Data loaded into PostgreSQL schema '{args.schema}'.[/bold green]")


def cmd_mock_api(args):
    """CLI handler for mock-api."""
    start_mock_api_server(host=args.host, port=args.port)


def cmd_inspect(args):
    """CLI handler for inspect."""
    summary_path = ARTIFACTS_DIR / "simulation_summary.json"
    if not summary_path.exists():
        console.print(f"[red]Error: Summary file {summary_path} not found. Run 'generate' first.[/red]")
        sys.exit(1)

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    if getattr(args, "json", False):
        console.print_json(data=summary)
    else:
        display_rich_summary(summary)


def cmd_fetch_weather(args):
    """CLI handler for fetch-weather."""
    console.print("[bold cyan]Fetching weather series from Open-Meteo Archive API...[/bold cyan]")
    fetch_open_meteo_archive(force_refresh=True)
    console.print(f"[bold green]✓ Successfully fetched and saved weather to {RAW_DATA_DIR / 'clima_managua_2024.json'}[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        prog="antojitos-sim",
        description="Antojitos Express Synthetic Data Simulation CLI (Managua, Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 synthetic data facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate")
    gen_parser.add_argument("--refresh-weather", action="store_true", help="Force refresh weather from Open-Meteo API")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for dynamic enrichment")
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

    # mock-api
    mock_parser = subparsers.add_parser("mock-api", help="Serve Open-Meteo mock HTTP endpoint")
    mock_parser.add_argument("--host", type=str, default=MOCK_API_HOST, help="Host to bind")
    mock_parser.add_argument("--port", type=int, default=MOCK_API_PORT, help="Port to listen on")
    mock_parser.set_defaults(func=cmd_mock_api)

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect simulation metrics and statistical tests")
    inspect_parser.add_argument("--json", action="store_true", help="Output raw JSON instead of tables")
    inspect_parser.set_defaults(func=cmd_inspect)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
