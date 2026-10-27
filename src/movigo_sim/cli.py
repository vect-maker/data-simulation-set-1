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
    PARQUET_ARTIFACTS_DIR,
    SQL_ARTIFACTS_DIR,
    ARTIFACTS_DIR,
    RAW_DATA_DIR,
    POSTGRES_SCHEMA,
    SIMULATION_SEED,
)
from movigo_sim.weather import (
    get_movigo_weather_series,
    fetch_movigo_weather_archive,
)
from movigo_sim.generator import MoviGoSimulationEngine
from movigo_sim.enrichment import MoviGoSemanticEnricher
from movigo_sim.exporter import (
    export_movigo_to_parquet,
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
        integ = num.get("integracion_numerica_demanda_diaria", {})
        hung = opt.get("algoritmo_hungaro_despacho", {})
        dijk = opt.get("ruta_mas_corta_red_vial", {})
        knap = opt.get("optimizacion_mochila_campanas", {})

        math_rows = [
            ("Raíces (Multiplicador de Equilibrio)", f"Bisección: {eq.get('multiplicador_optimo_biseccion')}x | Newton: {eq.get('multiplicador_optimo_newton')}x ({eq.get('interpretacion')})"),
            ("Diferenciación (Elasticidad Tarifa)", f"ε_p({elast.get('multiplicador_evaluado')}x) = {elast.get('elasticidad_precio_demanda')} -> {elast.get('clasificacion')}"),
            ("Integración Numérica (Demanda Diaria)", f"Simpson 1/3: {integ.get('simpson')} viajes/día | Trapecio: {integ.get('trapecio')} | Suma Discreta: {integ.get('suma_discreta')}"),
            ("Asignación Conductores (Húngaro)", f"Tiempo Total Espera: {hung.get('tiempo_total_espera_minutos')} min | Ahorro Medio: {hung.get('ahorro_promedio_por_viaje_min')} min/viaje"),
            ("Ruta Más Corta (Dijkstra Managua)", f"{dijk.get('origen')} -> {dijk.get('destino')} | {dijk.get('distancia_optima_km')} km ({dijk.get('tiempo_viaje_condicion_normal_min')} min despejado / {dijk.get('tiempo_viaje_congestion_lluvia_min')} min lluvia)"),
            ("Mochila 0/1 (Campañas de Bonos)", f"Presupuesto: C$ {knap.get('costo_total', 0):,} / C$ {knap.get('capacidad_presupuesto', 120000):,} -> +{knap.get('retorno_maximo', 0)} hrs ({len(knap.get('items_seleccionados', []))} campañas)"),
        ]
        render_math_optimization_table("Métodos Numéricos & Optimización Prescriptiva", math_rows, border_style="cyan")

    # 4. Ciencia de Datos Espacial & GIS
    if "analitica_espacial_gis" in summary:
        gis = summary["analitica_espacial_gis"]
        od = gis.get("matriz_origen_destino", {})
        grav = gis.get("modelo_gravedad_wilson", {})
        moran = gis.get("autocorrelacion_espacial_moran", {})
        lisa = gis.get("agrupamiento_lisa_puntos_calientes", {})
        cauces = gis.get("vulnerabilidad_hidraulica_cauces", {})

        top_hotspots_str = ", ".join([h["codigo"] for h in lisa.get("top_puntos_calientes_hotspots", [])[:4]])
        p_moran = moran.get("p_value", 0.0)
        p_moran_str = f"{p_moran:.2e}" if isinstance(p_moran, (float, int)) else str(p_moran)
        p_grav = grav.get("p_value_friction", 0.0)
        p_grav_str = f"{p_grav:.2e}" if isinstance(p_grav, (float, int)) else str(p_grav)

        spatial_rows = [
            ("Movilidad Interzonal vs Intrazonal", f"Interzonal: {od.get('porcentaje_viajes_interzonales')}% | Intrazonal: {od.get('porcentaje_viajes_intrazonales')}%"),
            ("Modelo de Gravedad de Wilson", f"Fricción distancia γ = {grav.get('friction_gamma')} (R² = {grav.get('r_squared')}, p = {p_grav_str})"),
            ("Autocorrelación Espacial (Moran's I)", f"I = {moran.get('moran_i')} (z = {moran.get('z_score')}, p = {p_moran_str}) -> {'Clustering Positivo' if moran.get('is_spatially_clustered') else 'Aleatorio'}"),
            ("Puntos Calientes LISA (Hotspots)", f"{lisa.get('distribucion_clusters', {}).get('High-High', 0)} cuadrantes High-High ({top_hotspots_str})"),
            ("Vulnerabilidad Hidráulica de Cauces", f"Índice Medio: {cauces.get('indice_vulnerabilidad_promedio')} | Crítico: {cauces.get('distribucion_riesgo', {}).get('critico', 0)}, Alto: {cauces.get('distribucion_riesgo', {}).get('alto', 0)}, Medio: {cauces.get('distribucion_riesgo', {}).get('medio', 0)}, Bajo: {cauces.get('distribucion_riesgo', {}).get('bajo', 0)}"),
        ]
        render_operational_table("Ciencia de Datos Espacial & GIS (Managua 2024)", spatial_rows, border_style="green")

    # 5. Elección Modal & Demanda Multimodal (Multinomial Logit)
    if "eleccion_modal_multinomial_logit" in summary:
        ml = summary["eleccion_modal_multinomial_logit"]
        cg = ml.get("cuota_modal_global", {})
        cs = ml.get("cuota_modal_clima_seco_pct", {})
        cl = ml.get("cuota_modal_lluvia_severa_pct", {})

        moto_g = cg.get("movigo_moto", {})
        std_g = cg.get("movigo_estandar", {})
        comf_g = cg.get("movigo_comfort", {})

        modal_rows = [
            ("Cuota Global por Categoría", f"Estándar: {std_g.get('porcentaje')}% ({std_g.get('viajes')} v.) | Comfort: {comf_g.get('porcentaje')}% ({comf_g.get('viajes')} v.) | Moto: {moto_g.get('porcentaje')}% ({moto_g.get('viajes')} v.)"),
            ("Tarifas Promedio por Categoría", f"Estándar: C$ {std_g.get('tarifa_promedio_nio')} | Comfort: C$ {comf_g.get('tarifa_promedio_nio')} | Moto: C$ {moto_g.get('tarifa_promedio_nio')}"),
            ("Cuota en Clima Seco (< 0.5 mm)", f"Estándar: {cs.get('movigo_estandar', 0.0)}% | Comfort: {cs.get('movigo_comfort', 0.0)}% | Moto: {cs.get('movigo_moto', 0.0)}%"),
            ("Cuota en Lluvia Severa (≥ 3.0 mm)", f"Estándar: {cl.get('movigo_estandar', 0.0)}% | Comfort: {cl.get('movigo_comfort', 0.0)}% | Moto: {cl.get('movigo_moto', 0.0)}%"),
            ("Sensibilidad y Elasticidad Cruzada", f"Ratio Desplome Moto: {ml.get('ratio_sensibilidad_climatica_moto')}x | Elasticidad Cruzada (Estándar/Moto): {ml.get('elasticidad_precio_cruzada_estandar_moto')}"),
        ]
        render_operational_table("Elección Modal & Demanda Multimodal (Multinomial Logit)", modal_rows, border_style="magenta")

    # 6. Heterogeneidad, Fatiga y Rechazo de Viajes por Conductores
    if "heterogeneidad_fatiga_conductores" in summary:
        hf = summary["heterogeneidad_fatiga_conductores"]
        motivos_pct = hf.get("distribucion_motivos_rechazo_pct", {})
        motivos_cnt = hf.get("distribucion_motivos_rechazo_conteo", {})
        rango = hf.get("rango_tasa_aceptacion", {})
        cats = hf.get("rechazos_por_categoria_vehiculo", {})

        driver_rows = [
            ("Tasa Aceptación Promedio Flota", f"{hf.get('tasa_aceptacion_promedio_flota_pct', 0.0)}% (Rango: {rango.get('min', 0.0)}% - {rango.get('max', 0.0)}%)"),
            ("Total Rechazos por Conductores", f"{hf.get('total_rechazos_conductor', 0)} rechazos registrados"),
            ("Desglose por Motivo de Rechazo", f"Riesgo Cauces: {motivos_pct.get('riesgo_cauce_desbordado', 0.0)}% ({motivos_cnt.get('riesgo_cauce_desbordado', 0)}) | Fatiga/Turno: {motivos_pct.get('fatiga_fin_turno', 0.0)}% ({motivos_cnt.get('fatiga_fin_turno', 0)}) | Deadhead >4km: {motivos_pct.get('desplazamiento_vacio', 0.0)}% ({motivos_cnt.get('desplazamiento_vacio', 0)})"),
            ("Rechazos por Categoría Vehicular", f"Moto: {cats.get('movigo_moto', 0)} | Estándar: {cats.get('movigo_estandar', 0)} | Comfort: {cats.get('movigo_comfort', 0)}"),
            ("Machine Learning & Driver Churn", f"Conductores en Riesgo Churn (<75%): {hf.get('conductores_riesgo_desercion_churn', 0)} | Retención Flota: {hf.get('tasa_retencion_proyectada_flota_pct', 0.0)}% | Corr(Aceptación, Rating): {hf.get('correlacion_aceptacion_calificacion', 0.0)}"),
        ]
        render_operational_table("Heterogeneidad, Fatiga & Rechazo de Conductores (Machine Learning)", driver_rows, border_style="yellow")

    # 7. Investigación de Operaciones: Talleres, Colas M/M/c & Repostaje
    if "investigacion_operaciones_talleres_y_colas" in summary:
        ioc = summary["investigacion_operaciones_talleres_y_colas"]
        mmc = ioc.get("colas_multicanal_mmc_talleres", {})

        or_rows = []
        for w_name, info in mmc.items():
            or_rows.append((
                f"Taller: {w_name}",
                f"Capacidad: {info.get('capacidad_bahias_c')} bahías | Atendidos: {info.get('vehiculos_atendidos')} | Espera Media Cola: {info.get('tiempo_medio_espera_cola_min')} min | Utilización ρ: {round(info.get('factor_utilizacion_bahias_rho', 0.0) * 100, 1)}%",
            ))
        or_rows.append((
            "Costo & Inactividad Flota",
            f"Costo Total: C$ {ioc.get('costo_total_mantenimiento_flota_nio', 0.0):,.2f} NIO | Downtime Acumulado: {ioc.get('horas_totales_inactividad_flota', 0.0)} hrs",
        ))
        render_operational_table("Investigación de Operaciones: Talleres, Colas M/M/c & Desgaste", or_rows, border_style="blue")

    # 8. Indicadores de Tráfico Horario & Enrutamiento Dinámico de Conductores
    if "indicadores_trafico_y_enrutamiento_dinamico" in summary:
        td = summary["indicadores_trafico_y_enrutamiento_dinamico"]
        cats = td.get("desglose_por_categoria_servicio", {})
        comf = cats.get("movigo_comfort", {})
        std = cats.get("movigo_estandar", {})
        moto = cats.get("movigo_moto", {})

        traffic_rows = [
            (
                "Adopción de Enrutamiento Inteligente",
                f"{td.get('total_viajes_re_enrutados_trafico', 0)} viajes re-enrutados ({td.get('porcentaje_re_enrutamiento_trafico', 0.0)}% del total)",
            ),
            (
                "Demora Total Evitada por Tráfico",
                f"{td.get('minutos_totales_demora_evitados', 0.0)} minutos evitados (promedio {td.get('promedio_minutos_ahorrados_por_re_enrutamiento', 0.0)} min/viaje re-enrutado)",
            ),
            (
                "Re-enrutamiento por Categoría",
                f"Comfort: {comf.get('viajes_re_enrutados_por_trafico', 0)} ({comf.get('minutos_demora_evitados', 0.0)} min) | Estándar: {std.get('viajes_re_enrutados_por_trafico', 0)} ({std.get('minutos_demora_evitados', 0.0)} min) | Moto: {moto.get('viajes_re_enrutados_por_trafico', 0)} ({moto.get('minutos_demora_evitados', 0.0)} min)",
            ),
            (
                "Estrés Promedio de Flota",
                f"Comfort: {comf.get('estres_promedio_acumulado', 0.0)} | Estándar: {std.get('estres_promedio_acumulado', 0.0)} | Moto: {moto.get('estres_promedio_acumulado', 0.0)}",
            ),
        ]
        render_operational_table(
            "Indicadores de Tráfico Horario & Enrutamiento Dinámico de Conductores",
            traffic_rows,
            border_style="bright_cyan",
        )

    # 9. Auditoría de Generación y Rendimiento del Simulador
    if "registro_auditoria_generacion" in summary and summary["registro_auditoria_generacion"]:
        aud = summary["registro_auditoria_generacion"]
        aud_rows = [
            ("Días Simulados", f"{aud.get('total_dias_simulados', 0):,} días"),
            (
                "Tiempo Total de Generación",
                f"{aud.get('tiempo_total_generacion_segundos', 0.0):.2f} s ({aud.get('tiempo_promedio_por_dia_segundos', 0.0):.3f} s/día)",
            ),
            (
                "Velocidad de Generación",
                f"{aud.get('velocidad_generacion_viajes_por_segundo', 0.0):.1f} viajes/segundo",
            ),
            ("Solicitudes Evaluadas", f"{aud.get('total_solicitudes_evaluadas', 0):,}"),
            (
                "Viajes Completados / Cancelados",
                f"{aud.get('total_viajes_completados', 0):,} completados | {aud.get('total_viajes_cancelados', 0):,} cancelados ({aud.get('tasa_cancelacion_auditoria_pct', 0.0)}%)",
            ),
            ("Archivo de Auditoría (JSONL)", f"{aud.get('archivo_log_auditoria', '')}"),
        ]
        render_operational_table(
            "Auditoría de Generación y Rendimiento del Simulador",
            aud_rows,
            border_style="bright_green",
        )


def run_generation(
    days=None,
    seed: int = SIMULATION_SEED,
    live_llm: bool = False,
    load_db: bool = False,
    schema: str = POSTGRES_SCHEMA,
    output_dir=None,
    refresh_weather: bool = False,
):
    """Programmatic entry point for MoviGo 3NF simulation generation."""
    weather_df, weather_records = get_movigo_weather_series(force_refresh=refresh_weather, seed=seed)
    if days and days < len(weather_df):
        weather_df = weather_df.head(days)
        valid_dates = set(weather_df["date"])
        if hasattr(weather_records, "filter_dates"):
            weather_records = weather_records.filter_dates(valid_dates)
        else:
            weather_records = [c for c in weather_records if c.date in valid_dates]

    engine = MoviGoSimulationEngine(random_seed=seed)
    trips, payments, ratings, cancellations, telemetry, maintenance = engine.run_simulation(weather_df)

    enricher = MoviGoSemanticEnricher(
        templates=engine.templates,
        use_llm=live_llm,
        random_seed=seed,
    )
    cancellations = enricher.enrich_cancellations(cancellations)

    target_dir = Path(output_dir).resolve() if output_dir else PARQUET_ARTIFACTS_DIR.resolve()
    is_custom_dir = target_dir != PARQUET_ARTIFACTS_DIR.resolve()
    sql_path = (target_dir.parent / "sql" / "schema_and_data.sql") if is_custom_dir else (SQL_ARTIFACTS_DIR / "schema_and_data.sql")
    summary_path = (target_dir.parent / "simulation_summary.json") if is_custom_dir else (ARTIFACTS_DIR / "simulation_summary.json")

    parquet_files = export_movigo_to_parquet(
        zones=engine.zones,
        users=engine.users,
        drivers=engine.drivers,
        vehicles=engine.vehicles,
        campaigns=engine.campaigns,
        weather=weather_records,
        trips=trips,
        payments=payments,
        ratings=ratings,
        cancellations=cancellations,
        telemetry=telemetry,
        maintenance=maintenance,
        output_dir=target_dir,
        quadrants=engine.quadrants,
    )
    export_movigo_to_sql_dump(parquet_files, output_file=sql_path)

    from movigo_sim.generator import load_movigo_drainage_channels
    from movigo_sim.exporter import export_movigo_spatial_layers
    spatial_dir = target_dir.parent / "spatial"
    export_movigo_spatial_layers(
        output_dir=spatial_dir,
        quadrants=engine.quadrants,
        zones=engine.zones,
        drainage_channels=load_movigo_drainage_channels(),
    )
    summary = compute_movigo_simulation_summary(
        zones=engine.zones,
        quadrants=engine.quadrants,
        trips=trips,
        payments=payments,
        weather=weather_records,
        campaigns=engine.campaigns,
        cancellations=cancellations,
        maintenance=maintenance,
        vehicles=engine.vehicles,
        drivers=engine.drivers,
        driver_agents=engine.driver_agents,
        workshops=engine.world.workshops,
        seed=seed,
        summary_path=summary_path,
        audit_logs=engine.audit_logs,
    )

    if load_db:
        load_movigo_to_postgres(
            zones=engine.zones,
            users=engine.users,
            drivers=engine.drivers,
            vehicles=engine.vehicles,
            campaigns=engine.campaigns,
            weather=weather_records,
            trips=trips,
            payments=payments,
            ratings=ratings,
            cancellations=cancellations,
            telemetry=telemetry,
            schema_name=schema,
            quadrants=engine.quadrants,
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


def run_loading(schema: str = POSTGRES_SCHEMA, seed: int = SIMULATION_SEED):
    """Programmatic entry point for loading to PostgreSQL."""
    engine = MoviGoSimulationEngine(random_seed=seed)
    weather_df, weather_records = get_movigo_weather_series(seed=seed)
    trips, payments, ratings, cancellations, telemetry, maintenance = engine.run_simulation(weather_df)
    enricher = MoviGoSemanticEnricher(engine.templates, random_seed=seed)
    cancellations = enricher.enrich_cancellations(cancellations)

    load_movigo_to_postgres(
        zones=engine.zones,
        users=engine.users,
        drivers=engine.drivers,
        vehicles=engine.vehicles,
        campaigns=engine.campaigns,
        weather=weather_records,
        trips=trips,
        payments=payments,
        ratings=ratings,
        cancellations=cancellations,
        telemetry=telemetry,
        schema_name=schema,
        quadrants=engine.quadrants,
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
        refresh_weather=getattr(args, "refresh_weather", False),
    )
    display_movigo_rich_summary(summary)


def cmd_load(args):
    """CLI handler for load."""
    p_dir = Path(getattr(args, "parquet_dir", str(PARQUET_ARTIFACTS_DIR))).resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from scripts.load_movigo_parquet_to_postgres import load_all_movigo_parquet
    load_all_movigo_parquet(
        parquet_dir=p_dir,
        schema=args.schema,
        batch_size=getattr(args, "batch_size", 10000),
    )


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
    gen_parser = subparsers.add_parser("generate", help="Generate 2024 urban rides & telemetry facts in Apache Parquet")
    gen_parser.add_argument("--seed", type=int, default=SIMULATION_SEED, help="Random seed for reproducibility")
    gen_parser.add_argument("--days", type=int, default=None, help="Number of days to simulate")
    gen_parser.add_argument("--refresh-weather", action="store_true", help="Force refresh weather from Open-Meteo")
    gen_parser.add_argument("--live-llm", action="store_true", help="Use live Gemini LLM for trip reviews")
    gen_parser.add_argument("--load-db", action="store_true", help="Load into PostgreSQL via dlt immediately")
    gen_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL staging schema")
    gen_parser.add_argument("--output-dir", type=str, default=str(PARQUET_ARTIFACTS_DIR), help="Output directory for Parquet files")
    gen_parser.set_defaults(func=cmd_generate)

    # fetch-weather
    weather_parser = subparsers.add_parser("fetch-weather", help="Fetch fresh weather data from Open-Meteo API")
    weather_parser.set_defaults(func=cmd_fetch_weather)

    # load
    load_parser = subparsers.add_parser("load", help="Load MoviGo Parquet datasets into PostgreSQL")
    load_parser.add_argument("--parquet-dir", type=str, default=str(PARQUET_ARTIFACTS_DIR), help="Path to Parquet artifacts directory")
    load_parser.add_argument("--schema", type=str, default=POSTGRES_SCHEMA, help="Target PostgreSQL schema")
    load_parser.add_argument("--batch-size", type=int, default=10000, help="Batch size for streaming ingestion (default: 10000)")
    load_parser.add_argument("--seed", type=int, default=SIMULATION_SEED, help="Random seed for reproducibility")
    load_parser.set_defaults(func=cmd_load)

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect simulation metrics and statistical tests")
    inspect_parser.add_argument("--json", action="store_true", help="Output raw JSON instead of tables")
    inspect_parser.set_defaults(func=cmd_inspect)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
