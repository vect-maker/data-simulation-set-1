"""CLI interface for Cooperativa El Volcan Synthetic Data Simulation Engine."""

import argparse
import json
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
    table_ops = Table(title="Cooperativa El Volcán: Resumen Operativo y Cadena de Valor (2024)", style="green")
    table_ops.add_column("Métrica", style="bold white")
    table_ops.add_column("Valor", style="cyan")

    table_ops.add_row("Caso de Estudio", summary["case_name"])
    table_ops.add_row("Regiones Cafetaleras", ", ".join(summary["coffee_regions"]))
    table_ops.add_row("Puerto de Exportación", summary["export_port"])
    table_ops.add_row("Total Fincas Participantes", f"{summary['total_farms']}")
    table_ops.add_row("Total Lotes Cosechados", f"{summary['total_harvest_lots']:,}")
    table_ops.add_row("Café Cereza Recolectado", f"{summary['total_cherry_harvested_kg']:,.2f} kg")
    table_ops.add_row("Café Oro Exportado", f"{summary['total_green_coffee_exported_qq']:,.2f} quintales")
    table_ops.add_row("Ingresos Totales FOB", f"USD ${summary['total_export_revenue_usd']:,.2f}")

    scaa_stats = summary["scaa_cupping_scores"]
    table_ops.add_row("Puntaje SCAA (Media / Min / Max)", f"{scaa_stats['mean']} / {scaa_stats['min']} / {scaa_stats['max']}")
    table_ops.add_row("Correlación Altitud vs SCAA (r)", f"{scaa_stats['correlation_with_altitude']:.4f}")

    chi_res = summary["chi_square_test_variety_vs_region"]
    p_status = "[bold green]PASS (p < 0.01)[/bold green]" if chi_res["guarantee_p_less_than_0_01"] else "[bold red]FAIL[/bold red]"
    table_ops.add_row("Ji-Cuadrado (Variedad vs Región)", f"χ² = {chi_res['chi2_statistic']}, p = {chi_res['p_value']:.2e} -> {p_status}")
    console.print("\n", table_ops)

    # 2. Estadística II: Regresión y Supuestos OLS
    if "estadistica_ii" in summary:
        est = summary["estadistica_ii"]
        table_reg = Table(title="Estadística II: Regresión Altitud vs SCAA y Pruebas de Hipótesis", style="magenta")
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

        secado = num.get("linealizacion_cinetica_secado", {})
        table_math.add_row("Linealización (Cinética de Secado)", f"{secado.get('modelo_teorico')} | k={secado.get('constante_secado_k')} | R²={secado.get('r_cuadrado_linealizado')}")

        newt = num.get("calculo_raices_newton_secado", {})
        table_math.add_row("Raíces (Newton-Raphson Secado)", f"Días óptimos para 11.5% humedad: {newt.get('dias_optimos_secado_newton')} días ({newt.get('iteraciones_convergencia')} iteraciones)")

        cpm = opt.get("metodo_ruta_critica_cpm", {})
        table_math.add_row("Ruta Crítica (CPM / PERT)", f"Duración Total: {cpm.get('duracion_total_proyecto_dias')} días | Ruta: {cpm.get('ruta_critica')}")

        trans = opt.get("modelo_transporte_cafetalero", {})
        table_math.add_row("Modelo de Transporte (Vogel VAM)", f"Oferta: {trans.get('oferta_total_quintales')} qq | Costo Total Óptimo de Flete: USD ${trans.get('costo_total_flete_usd'):,.2f}")

        console.print("\n", table_math, "\n")


def cmd_generate(args):
    """Run full synthetic data generation pipeline."""
    console.print(Panel.fit(
        "[bold green]Cooperativa El Volcán Synthetic Data Simulation[/bold green]\n"
        "[cyan]Nicaragua Specialty Coffee Export Supply Chain (Jinotega - Puerto Corinto)[/cyan]",
        border_style="green"
    ))

    # 1. Weather series
    with console.status("[bold yellow]Fetching/loading 2024 Jinotega agro-weather from Open-Meteo..."):
        weather_df, clima_records = get_coffee_weather_series(force_refresh=args.refresh_weather)
        if args.days and args.days < len(weather_df):
            weather_df = weather_df.head(args.days)
            clima_records = clima_records[:args.days]

    console.print(f"[green]✓[/green] Agro-climatic series ready: [bold]{len(weather_df)}[/bold] days (2024).")

    # 2. Simulation engine
    with console.status(f"[bold yellow]Running agricultural simulation (seed={args.seed})..."):
        engine = VolcanSimulationEngine(random_seed=args.seed)
        lotes, procesos, subastas, embarques = engine.run_simulation(weather_df)

    console.print(
        f"[green]✓[/green] Simulated: [bold]{len(lotes):,}[/bold] lots, "
        f"[bold]{len(procesos):,}[/bold] processing steps, [bold]{len(embarques):,}[/bold] shipments."
    )

    # 3. Semantic enrichment
    with console.status(f"[bold yellow]Applying semantic enrichment (live_llm={args.live_llm})..."):
        enricher = VolcanSemanticEnricher(
            templates=engine.notes_templates,
            use_llm=args.live_llm,
            random_seed=args.seed,
        )
        lotes, procesos = enricher.enrich_lots_and_processes(lotes, procesos)

    console.print("[green]✓[/green] Cupping tasting notes enriched.")

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

    display_volcan_rich_summary(summary)


def cmd_load(args):
    """Load pre-generated or fresh data into PostgreSQL."""
    console.print("[bold cyan]Running dlt pipeline load to PostgreSQL...[/bold cyan]")
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
    """Run Mock Open-Meteo API server for student ingesta.sh scripts."""
    start_volcan_mock_api_server(host=args.host, port=args.port)


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
        display_volcan_rich_summary(summary)


def cmd_fetch_weather(args):
    """Fetch fresh agro-weather series from Open-Meteo API."""
    console.print("[bold cyan]Fetching agro-weather series from Open-Meteo Archive API...[/bold cyan]")
    fetch_jinotega_weather_archive(force_refresh=True)
    console.print(f"[bold green]✓ Successfully fetched and saved weather to {RAW_DATA_DIR / 'clima_jinotega_2024.json'}[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        prog="volcan-sim",
        description="Cooperativa El Volcán Synthetic Data Simulation CLI (Specialty Coffee Export - Nicaragua)"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 synthetic harvest facts")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate")
    gen_parser.add_argument("--refresh-weather", action="store_true", help="Force refresh weather from Open-Meteo")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for dynamic enrichment")
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
