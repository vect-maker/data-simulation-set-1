"""CLI interface for MoviGo Synthetic Data Simulation Engine (Managua, Nicaragua)."""

import argparse
import json
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
    RAW_DATA_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST,
    POSTGRES_SCHEMA,
)
from movigo_sim.weather import (
    get_movigo_weather_series,
    fetch_movigo_weather_archive,
    start_movigo_mock_api_server,
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
    table_ops = Table(title="MoviGo: Resumen de Operaciones y Movilidad Urbana (Managua 2024)", style="magenta")
    table_ops.add_column("Métrica", style="bold white")
    table_ops.add_column("Valor", style="cyan")

    table_ops.add_row("Caso de Estudio", summary["case_name"])
    table_ops.add_row("Área Urbana", summary["city"])
    table_ops.add_row("Rango de Fechas", f"{summary['date_range'][0]} a {summary['date_range'][1]}")
    table_ops.add_row("Total Solicitudes de Viaje", f"{summary['total_trips']:,}")
    table_ops.add_row("Viajes Completados", f"{summary['completed_trips']:,}")
    table_ops.add_row("Viajes Cancelados", f"{summary['canceled_trips']:,} ({summary['cancellation_rate_pct']}%)")
    table_ops.add_row("Ingreso Bruto Total", f"C$ {summary['total_gross_revenue_nio']:,.2f} NIO")

    averages = summary["trip_averages"]
    table_ops.add_row("Promedios (Tarifa / Distancia / Duración)", f"C$ {averages['fare_nio']} | {averages['distance_km']} km | {averages['duration_minutes']} min")
    table_ops.add_row("Multiplicador Dinámico Medio", f"{averages['surge_multiplier']:.2f}x")

    corrs = summary["continuous_correlations"]
    table_ops.add_row("Correlación Lluvia y Congestión", f"Lluvia (r): {corrs['rain_vs_daily_demand']:.4f} | Congestión (r): {corrs['congestion_vs_daily_demand']:.4f}")

    chi_res = summary["chi_square_test_payment_method_vs_stratum"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"
    table_ops.add_row("Ji-Cuadrado (Pago vs Estrato)", f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}")
    console.print("\n", table_ops)

    # 2. Estadística II: Regresión y Supuestos OLS
    if "estadistica_ii" in summary:
        est = summary["estadistica_ii"]
        table_reg = Table(title="Estadística II: Regresión Lluvia vs Demanda y Pruebas de Hipótesis", style="magenta")
        table_reg.add_column("Análisis / Test", style="bold white")
        table_reg.add_column("Estadístico / Diagnóstico", style="yellow")
        table_reg.add_column("Resultado / Conclusión", style="green")

        sup = est.get("validacion_supuestos_ols", {})
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

        table_math = Table(title="Métodos Numéricos & Optimización Prescriptiva", style="cyan")
        table_math.add_column("Pilar / Modelo", style="bold white")
        table_math.add_column("Solución Numérica / Prescriptiva", style="green")

        eq = num.get("equilibrio_mercado_raices", {})
        table_math.add_row("Raíces (Multiplicador de Equilibrio)", f"Bisección: {eq.get('multiplicador_optimo_biseccion')}x | Newton: {eq.get('multiplicador_optimo_newton')}x ({eq.get('interpretacion')})")

        elast = num.get("diferenciacion_numerica_elasticidad", {})
        table_math.add_row("Diferenciación (Elasticidad Tarifa)", f"ε_p({elast.get('multiplicador_evaluado')}x) = {elast.get('elasticidad_precio_demanda')} -> {elast.get('clasificacion')}")

        hung = opt.get("algoritmo_hungaro_despacho", {})
        table_math.add_row("Asignación Conductores (Húngaro)", f"Tiempo Total Espera: {hung.get('tiempo_total_espera_minutos')} min | Ahorro Medio: {hung.get('ahorro_promedio_por_viaje_min')} min/viaje")

        dijk = opt.get("ruta_mas_corta_red_vial", {})
        table_math.add_row("Ruta Más Corta (Dijkstra Managua)", f"{dijk.get('origen')} -> {dijk.get('destino')} | {dijk.get('distancia_optima_km')} km ({dijk.get('tiempo_viaje_condicion_normal_min')} min despejado / {dijk.get('tiempo_viaje_congestion_lluvia_min')} min lluvia)")

        console.print("\n", table_math, "\n")


def cmd_generate(args):
    """Run full synthetic data generation pipeline."""
    console.print(Panel.fit(
        "[bold magenta]MoviGo Synthetic Data Simulation[/bold magenta]\n"
        "[cyan]Urban Mobility and Algorithmic Dispatch Engine (Managua, Nicaragua)[/cyan]",
        border_style="magenta"
    ))

    # 1. Weather series
    with console.status("[bold yellow]Fetching/loading 2024 Managua weather & traffic from Open-Meteo..."):
        weather_df, clima_records = get_movigo_weather_series(force_refresh=args.refresh_weather)
        if args.days and args.days < len(weather_df):
            weather_df = weather_df.head(args.days)
            clima_records = clima_records[:args.days]

    console.print(f"[green]✓[/green] Weather & traffic series ready: [bold]{len(weather_df)}[/bold] days (2024).")

    # 2. Simulation engine
    with console.status(f"[bold yellow]Running mobility simulation (seed={args.seed})..."):
        engine = MoviGoSimulationEngine(random_seed=args.seed)
        viajes, telemetria = engine.run_simulation(weather_df)

    console.print(f"[green]✓[/green] Simulated: [bold]{len(viajes):,}[/bold] rides, [bold]{len(telemetria):,}[/bold] telemetry pings.")

    # 3. Semantic enrichment
    with console.status(f"[bold yellow]Applying semantic enrichment (live_llm={args.live_llm})..."):
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

    display_movigo_rich_summary(summary)


def cmd_load(args):
    """Load pre-generated or fresh data into PostgreSQL."""
    console.print("[bold cyan]Running dlt pipeline load to PostgreSQL...[/bold cyan]")
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
    """Run Mock Open-Meteo API server for student ingesta.sh scripts."""
    start_movigo_mock_api_server(host=args.host, port=args.port)


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
        display_movigo_rich_summary(summary)


def cmd_fetch_weather(args):
    """Fetch fresh weather and traffic series from Open-Meteo API."""
    console.print("[bold cyan]Fetching weather and traffic series from Open-Meteo Archive API...[/bold cyan]")
    fetch_movigo_weather_archive(force_refresh=True)
    console.print(f"[bold green]✓ Successfully fetched and saved weather to {RAW_DATA_DIR / 'clima_managua_movigo_2024.json'}[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        prog="movigo-sim",
        description="MoviGo Synthetic Data Simulation CLI (Urban Mobility & Ride-Hailing - Managua, Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 synthetic mobility facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate")
    gen_parser.add_argument("--refresh-weather", action="store_true", help="Force refresh weather from Open-Meteo")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for dynamic enrichment")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(CSV_ARTIFACTS_DIR), help="Output directory for CSVs")
    gen_parser.set_defaults(func=cmd_generate)

    # fetch-weather
    weather_parser = subparsers.add_parser("fetch-weather", help="Fetch fresh weather/traffic data from Open-Meteo")
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
