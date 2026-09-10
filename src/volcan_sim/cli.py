"""CLI interface for Cooperativa El Volcan Synthetic Data Simulation Engine."""

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
from volcan_sim.config import (
    CSV_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    RAW_DATA_DIR,
    MOCK_API_PORT,
    MOCK_API_HOST,
    POSTGRES_SCHEMA,
)
from volcan_sim.weather import (
    get_coffee_weather_series,
    fetch_jinotega_weather_archive,
    start_volcan_mock_api_server,
)
from volcan_sim.generator import VolcanSimulationEngine
from volcan_sim.enrichment import VolcanSemanticEnricher
from volcan_sim.exporter import (
    export_volcan_to_csv,
    export_volcan_to_sql_dump,
    compute_volcan_simulation_summary,
)
from volcan_sim.pipeline import load_volcan_to_postgres

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("volcan_sim")


def display_volcan_rich_summary(summary: dict):
    """Render comprehensive multi-pillar academic report for Cooperativa El Volcán."""
    # 1. Operational Metrics
    scaa_stats = summary["scaa_cupping_scores"]
    chi_res = summary["chi_square_test_variety_vs_region"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"

    ops_rows = [
        ("Caso de Estudio", summary["case_name"]),
        ("Regiones Cafetaleras", ", ".join(summary["coffee_regions"])),
        ("Puerto de Exportación", summary["export_port"]),
        ("Total Fincas Participantes", f"{summary['total_farms']}"),
        ("Total Lotes Cosechados", f"{summary['total_harvest_lots']:,}"),
        ("Café Cereza Recolectado", f"{summary['total_cherry_harvested_kg']:,.2f} kg"),
        ("Café Oro Exportado", f"{summary['total_green_coffee_exported_qq']:,.2f} quintales"),
        ("Ingresos Totales FOB", f"USD ${summary['total_export_revenue_usd']:,.2f}"),
        ("Puntaje SCAA (Media / Min / Max)", f"{scaa_stats['mean']} / {scaa_stats['min']} / {scaa_stats['max']}"),
        ("Correlación Altitud vs SCAA (r)", f"{scaa_stats['correlation_with_altitude']:.4f}"),
        ("Ji-Cuadrado (Variedad vs Región)", f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}"),
    ]
    render_operational_table("Cooperativa El Volcán: Resumen Operativo y Cadena de Valor (2024)", ops_rows, border_style="green")

    # 2. Estadística II: Regresión y Supuestos OLS
    if "estadistica_ii" in summary:
        est = summary["estadistica_ii"]
        render_statistical_table(
            "Estadística II: Regresión Altitud vs SCAA y Pruebas de Hipótesis",
            est.get("validacion_supuestos", est.get("validacion_supuestos_ols", {})),
            est.get("bateria_pruebas_hipotesis", []),
            border_style="magenta",
        )

    # 3. Métodos Numéricos & Optimización
    if "metodos_numericos" in summary and "optimizacion" in summary:
        num = summary["metodos_numericos"]
        opt = summary["optimizacion"]
        secado = num.get("cinetica_secado_deshidratacion", num.get("linealizacion_cinetica_secado", {}))
        newt = num.get("raices_newton_raphson_tiempo_secado", num.get("calculo_raices_newton_secado", {}))
        cpm = opt.get("gestion_proyectos_cpm_pert", opt.get("metodo_ruta_critica_cpm", {}))
        trans = opt.get("modelo_transporte_vogel", opt.get("modelo_transporte_cafetalero", {}))

        math_rows = [
            ("Linealización (Cinética de Secado)", f"{secado.get('modelo', secado.get('modelo_teorico'))} | k={secado.get('constante_secado_k')} | R²={secado.get('coeficiente_determinacion_r2', secado.get('r_cuadrado_linealizado'))}"),
            ("Raíces (Newton-Raphson Secado)", f"Horas para 11.5% humedad: {newt.get('tiempo_optimo_horas', newt.get('dias_optimos_secado_newton'))} ({newt.get('iteraciones_newton', newt.get('iteraciones_convergencia'))} iteraciones)"),
            ("Ruta Crítica (CPM / PERT)", f"Duración Total: {cpm.get('duracion_total_dias', cpm.get('duracion_total_proyecto_dias'))} días | Ruta: {cpm.get('ruta_critica')}"),
            ("Modelo de Transporte (Vogel VAM)", f"Oferta: {trans.get('oferta_total_quintales')} qq | Costo Total Óptimo de Flete: USD ${trans.get('costo_total_minimo_flete_usd', trans.get('costo_total_flete_usd')):,.2f}"),
        ]
        render_math_optimization_table("Métodos Numéricos & Optimización Prescriptiva", math_rows, border_style="cyan")


def run_generation(days=None, seed=42, live_llm=False, load_db=False, schema=POSTGRES_SCHEMA, output_dir=None):
    """Programmatic entry point for Volcan simulation generation."""
    weather_df, clima_records = get_coffee_weather_series()
    if days and days < len(weather_df):
        weather_df = weather_df.head(days)
        clima_records = clima_records[:days]

    engine = VolcanSimulationEngine(random_seed=seed)
    lotes, procesos, subastas, embarques = engine.run_simulation(weather_df)

    enricher = VolcanSemanticEnricher(
        templates=engine.notes_templates,
        use_llm=live_llm,
        random_seed=seed,
    )
    lotes, procesos = enricher.enrich_lots_and_processes(lotes, procesos)

    csv_dir = Path(output_dir) if output_dir else CSV_ARTIFACTS_DIR
    csv_files = export_volcan_to_csv(
        fincas=engine.fincas,
        variedades=engine.variedades,
        beneficios=engine.beneficios,
        cuadrillas=engine.cuadrillas,
        clima=clima_records,
        lotes=lotes,
        procesos=procesos,
        subastas=subastas,
        embarques=embarques,
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

    if load_db:
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
    display_volcan_rich_summary(summary)


def run_loading(schema=POSTGRES_SCHEMA):
    """Programmatic entry point for loading to PostgreSQL."""
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
        schema_name=schema,
    )


def cmd_generate(args):
    """CLI handler for generate."""
    console.print(Panel.fit(
        "[bold green]Cooperativa El Volcán Synthetic Data Simulation[/bold green]\n"
        "[cyan]Nicaragua Specialty Coffee Export Supply Chain (Jinotega - Puerto Corinto)[/cyan]",
        border_style="green"
    ))
    summary = run_generation(
        days=args.days,
        seed=args.seed,
        live_llm=args.live_llm,
        load_db=args.load_db,
        schema=args.schema,
        output_dir=args.output_dir,
    )
    display_volcan_rich_summary(summary)


def cmd_load(args):
    """CLI handler for load."""
    run_loading(schema=args.schema)
    console.print(f"[bold green]Data loaded into PostgreSQL schema '{args.schema}'.[/bold green]")


def cmd_mock_api(args):
    """CLI handler for mock-api."""
    start_volcan_mock_api_server(host=args.host, port=args.port)


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
        display_volcan_rich_summary(summary)


def cmd_fetch_weather(args):
    """CLI handler for fetch-weather."""
    console.print("[bold cyan]Fetching agro-weather series from Open-Meteo API for Jinotega...[/bold cyan]")
    fetch_jinotega_weather_archive(force_refresh=True)
    console.print(f"[bold green]✓ Successfully fetched and saved agro-weather to {RAW_DATA_DIR / 'clima_jinotega_2024.json'}[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        prog="volcan-sim",
        description="Cooperativa El Volcán Synthetic Data Simulation CLI (Jinotega, Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 coffee harvest & processing facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate")
    gen_parser.add_argument("--refresh-weather", action="store_true", help="Force refresh agro-weather from Open-Meteo")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for cupping notes")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(CSV_ARTIFACTS_DIR), help="Output directory for CSVs")
    gen_parser.set_defaults(func=cmd_generate)

    # fetch-weather
    weather_parser = subparsers.add_parser("fetch-weather", help="Fetch fresh agro-weather data from Open-Meteo API")
    weather_parser.set_defaults(func=cmd_fetch_weather)

    # load
    load_parser = subparsers.add_parser("load", help="Load data into PostgreSQL via dlt")
    load_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL schema")
    load_parser.set_defaults(func=cmd_load)

    # mock-api
    mock_parser = subparsers.add_parser("mock-api", help="Serve Open-Meteo mock HTTP endpoint for agro-weather")
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
