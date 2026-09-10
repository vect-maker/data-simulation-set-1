"""CLI interface for Antojitos Express Synthetic Data Simulation Engine."""

import argparse
import json
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
    table_ops = Table(title="Antojitos Express: Métricas Operativas y Demanda (2024)", style="cyan")
    table_ops.add_column("Métrica", style="bold white")
    table_ops.add_column("Valor", style="green")

    table_ops.add_row("Ciudad / Mercado", summary["city"])
    table_ops.add_row("Rango de Fechas", f"{summary['date_range'][0]} a {summary['date_range'][1]}")
    table_ops.add_row("Total Órdenes Generadas", f"{summary['total_orders']:,}")
    table_ops.add_row("Total Líneas de Detalle", f"{summary['total_line_items']:,}")
    table_ops.add_row("Ingreso Bruto Total", f"C$ {summary['total_revenue_nio']:,.2f}")
    table_ops.add_row("Órdenes Entregadas", f"{summary['delivered_orders']:,}")
    table_ops.add_row("Órdenes Canceladas", f"{summary['canceled_orders']:,} ({summary['cancellation_rate_pct']}%)")
    table_ops.add_row("Órdenes Diarias (Media / Min / Max)", f"{summary['daily_orders_mean']} / {summary['daily_orders_min']} / {summary['daily_orders_max']}")
    table_ops.add_row("Correlación Lluvia-Demanda (r)", f"{summary['weather_order_correlation']:.4f}")

    chi_res = summary["chi_square_test_zone_vs_category"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"
    table_ops.add_row("Ji-Cuadrado (Zona vs Categoría)", f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}")
    console.print("\n", table_ops)

    # 2. Estadística II: Regresión y Supuestos OLS
    if "estadistica_ii" in summary:
        est = summary["estadistica_ii"]
        table_reg = Table(title="Estadística II: Supuestos OLS y Pruebas de Hipótesis", style="magenta")
        table_reg.add_column("Análisis / Test", style="bold white")
        table_reg.add_column("Estadístico / Diagnóstico", style="yellow")
        table_reg.add_column("Resultado / Conclusión", style="green")

        sup = est.get("validacion_supuestos", {})
        norm = sup.get("normalidad_residuos", {})
        table_reg.add_row("Normalidad Residuos (Shapiro)", f"W = {norm.get('estadistico_w')}, p = {norm.get('p_valor')}", "Cumple Gauss-Markov" if norm.get('cumple_supuesto') else "Aceptable para n grande")

        homo = sup.get("homocedasticidad", {})
        table_reg.add_row("Homocedasticidad (Breusch-Pagan)", f"LM = {homo.get('estadistico_lm')}, p = {homo.get('p_valor')}", "Varianza residual constante" if homo.get('cumple_supuesto') else "Heterocedasticidad leve")

        dw = sup.get("independencia_errores", {})
        table_reg.add_row("Autocorrelación (Durbin-Watson)", f"DW = {dw.get('estadistico_dw')}", dw.get('diagnostico', 'N/A'))

        for h in est.get("bateria_pruebas_hipotesis", []):
            table_reg.add_row(f"Hipótesis: {h['id']}", f"p-valor = {h['p_valor']:.4e}", h['conclusion'])

        console.print("\n", table_reg)

    # 3. Métodos Numéricos & Optimización
    if "metodos_numericos" in summary and "optimizacion" in summary:
        num = summary["metodos_numericos"]
        opt = summary["optimizacion"]

        table_math = Table(title="Métodos Numéricos & Optimización Prescriptiva", style="green")
        table_math.add_column("Pilar / Modelo", style="bold white")
        table_math.add_column("Solución Numérica / Prescriptiva", style="cyan")

        raices = num.get("ecuaciones_no_lineales_raices", {})
        table_math.add_row("Raíces (Punto Equilibrio Cocina)", f"Bisección: {raices.get('raiz_biseccion_ordenes')} órdenes | Newton: {raices.get('raiz_newton_raphson_ordenes')} órdenes | Óptimo q*={raices.get('q_optimo_maximo_beneficio')}")

        elast = num.get("diferenciacion_numerica_elasticidad", {})
        table_math.add_row("Diferenciación (Elasticidad)", f"ε_p({elast.get('precio_evaluado_nio')} NIO) = {elast.get('elasticidad_precio_demanda')} -> {elast.get('clasificacion')}")

        integ = num.get("integración_numerica_demanda", num.get("integracion_numerica_demanda", {}))
        table_math.add_row("Integración Numérica (Simpson)", f"Simpson: {integ.get('integral_regla_simpson_compuesta')} | Real: {integ.get('suma_discreta_real')} (Error: {integ.get('error_relativo_simpson_pct')}%)")

        pl = opt.get("programacion_lineal_simplex", {})
        table_math.add_row("Programación Lineal (Simplex)", f"Margen Máx: C$ {pl.get('margen_maximo_nio'):,.2f} | Precios Sombra: {pl.get('precios_sombra_restricciones')}")

        hung = opt.get("algoritmo_hungaro_asignacion", {})
        table_math.add_row("Asignación Couriers (Húngaro)", f"Tiempo global óptimo de respuesta: {hung.get('tiempo_total_minutos')} minutos ({hung.get('matriz_dimension')})")

        console.print("\n", table_math, "\n")


def cmd_generate(args):
    """Run full synthetic data generation pipeline."""
    console.print(Panel.fit(
        "[bold cyan]Antojitos Express Synthetic Data Simulation[/bold cyan]\n"
        "[green]Managua, Nicaragua - Academic Data Pipeline Engine[/green]",
        border_style="cyan"
    ))

    # 1. Weather series
    with console.status("[bold yellow]Fetching/loading 2024 Managua weather from Open-Meteo..."):
        weather_df, clima_records = get_daily_weather_series(force_refresh=args.refresh_weather)
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
            repartidores=engine.repartidores,
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

    display_rich_summary(summary)


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

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    if getattr(args, "json", False):
        console.print_json(data=summary)
    else:
        display_rich_summary(summary)


def cmd_fetch_weather(args):
    """Fetch/generate fresh weather series from Open-Meteo API and save to cache."""
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
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate (default: full year 366)")
    gen_parser.add_argument("--refresh-weather", action="store_true", help="Force refresh weather from Open-Meteo API")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for dynamic enrichment")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(CSV_ARTIFACTS_DIR), help="Output directory for CSVs")
    gen_parser.set_defaults(func=cmd_generate)

    # fetch-weather
    weather_parser = subparsers.add_parser("fetch-weather", help="Fetch/generate fresh weather data from Open-Meteo API")
    weather_parser.set_defaults(func=cmd_fetch_weather)

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
    inspect_parser.add_argument("--json", action="store_true", help="Output raw JSON instead of tables")
    inspect_parser.set_defaults(func=cmd_inspect)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
