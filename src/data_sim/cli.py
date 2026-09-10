"""Unified CLI Interface for Data Simulation Suite.

Provides unified management across all 3 semester project simulation engines:
- generate: Execute simulation pipelines and produce CSV & SQL artifacts
- inspect: Display rich multi-pillar academic indicators and model benchmarks
- load: Load schemas and synthetic data into PostgreSQL
- weather: Fetch driver meteorological series from Open-Meteo API
- bundle: Package complete student distributions (CSVs, SQL, guides, queries)
- mock-api: Launch standalone mock Open-Meteo HTTP servers for student labs
"""

import argparse
import sys
import logging
from pathlib import Path
from rich.console import Console

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("data_sim")


def cmd_generate(args):
    """Run generation for specified case or all cases."""
    cases = ["antojitos", "volcan", "movigo"] if args.case == "all" else [args.case]

    for case in cases:
        console.print(f"\n[bold cyan]===> Simulating Case: {case.upper()} (days={args.days or 'all 2024'})[/bold cyan]")
        if case == "antojitos":
            from antojitos_sim.cli import run_generation as gen_antojitos
            gen_antojitos(days=args.days, seed=args.seed)
        elif case == "volcan":
            from volcan_sim.cli import run_generation as gen_volcan
            gen_volcan(days=args.days, seed=args.seed)
        elif case == "movigo":
            from movigo_sim.cli import run_generation as gen_movigo
            gen_movigo(days=args.days, seed=args.seed)

    console.print("\n[bold green]✓ Generation complete for selected cases![/bold green]")


def cmd_inspect(args):
    """Inspect mathematical summary metrics for specified case or all cases."""
    cases = ["antojitos", "volcan", "movigo"] if args.case == "all" else [args.case]

    for case in cases:
        console.print(f"\n[bold cyan]=== Summary: {case.upper()} ===[/bold cyan]")
        if case == "antojitos":
            from antojitos_sim.cli import run_inspection as insp_antojitos
            insp_antojitos()
        elif case == "volcan":
            from volcan_sim.cli import run_inspection as insp_volcan
            insp_volcan()
        elif case == "movigo":
            from movigo_sim.cli import run_inspection as insp_movigo
            insp_movigo()


def cmd_load(args):
    """Load schema and generated data into PostgreSQL."""
    cases = ["antojitos", "volcan", "movigo"] if args.case == "all" else [args.case]

    for case in cases:
        console.print(f"\n[bold cyan]===> Loading into PostgreSQL: {case.upper()}[/bold cyan]")
        if case == "antojitos":
            from antojitos_sim.cli import run_loading as load_antojitos
            load_antojitos()
        elif case == "volcan":
            from volcan_sim.cli import run_loading as load_volcan
            load_volcan()
        elif case == "movigo":
            from movigo_sim.cli import run_loading as load_movigo
            load_movigo()

    console.print("\n[bold green]✓ Database loading complete![/bold green]")


def cmd_weather(args):
    """Fetch Open-Meteo weather driver series."""
    cases = ["antojitos", "volcan", "movigo"] if args.case == "all" else [args.case]

    for case in cases:
        console.print(f"\n[bold cyan]===> Fetching weather for: {case.upper()}[/bold cyan]")
        if case == "antojitos":
            from antojitos_sim.weather import fetch_open_meteo_archive
            fetch_open_meteo_archive(force_refresh=args.force)
        elif case == "volcan":
            from volcan_sim.weather import fetch_jinotega_weather_archive
            fetch_jinotega_weather_archive(force_refresh=args.force)
        elif case == "movigo":
            from movigo_sim.weather import fetch_open_meteo_managua_series
            fetch_open_meteo_managua_series(force_refresh=args.force)


def cmd_bundle(args):
    """Package complete student deliverables."""
    from data_sim.core.bundle import create_student_bundle, create_all_student_bundles

    console.print(f"\n[bold cyan]===> Creating student bundles (case={args.case})...[/bold cyan]")
    make_tar = not args.no_archive

    if args.case == "all":
        results = create_all_student_bundles(make_archive=make_tar)
        for k, p in results.items():
            console.print(f"  [green]✓ {k}:[/green] {p}")
    else:
        res = create_student_bundle(args.case, make_archive=make_tar)
        console.print(f"  [green]✓ {args.case}:[/green] {res}")

    console.print("\n[bold green]✓ Student bundles packaged successfully in data/exports/student_bundles/[/bold green]")


def cmd_mock_api(args):
    """Start standalone mock Open-Meteo server."""
    port = args.port or (8000 if args.case == "antojitos" else 8001 if args.case == "volcan" else 8002)

    if args.case == "antojitos":
        from antojitos_sim.weather import start_mock_api_server
        start_mock_api_server(port=port)
    elif args.case == "volcan":
        from volcan_sim.weather import start_volcan_mock_api_server
        start_volcan_mock_api_server(port=port)
    elif args.case == "movigo":
        from movigo_sim.weather import start_mock_api_server
        start_mock_api_server(port=port)


def build_parser() -> argparse.ArgumentParser:
    """Build root CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="data-sim",
        description="Unified Synthetic Data Simulation Engine for Nicaragua Capstones",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. generate
    p_gen = subparsers.add_parser("generate", help="Run simulation and generate artifacts")
    p_gen.add_argument("--case", choices=["all", "antojitos", "volcan", "movigo"], default="all")
    p_gen.add_argument("--days", type=int, default=None, help="Number of days to simulate (default: full year)")
    p_gen.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    p_gen.set_defaults(func=cmd_generate)

    # 2. inspect
    p_insp = subparsers.add_parser("inspect", help="Display analytical summary tables")
    p_insp.add_argument("--case", choices=["all", "antojitos", "volcan", "movigo"], default="all")
    p_insp.set_defaults(func=cmd_inspect)

    # 3. load
    p_load = subparsers.add_parser("load", help="Load schema and data into PostgreSQL")
    p_load.add_argument("--case", choices=["all", "antojitos", "volcan", "movigo"], default="all")
    p_load.set_defaults(func=cmd_load)

    # 4. weather
    p_wea = subparsers.add_parser("weather", help="Fetch or cache Open-Meteo weather series")
    p_wea.add_argument("--case", choices=["all", "antojitos", "volcan", "movigo"], default="all")
    p_wea.add_argument("--force", action="store_true", help="Force refresh API cache")
    p_wea.set_defaults(func=cmd_weather)

    # 5. bundle
    p_bun = subparsers.add_parser("bundle", help="Package student assignment bundles")
    p_bun.add_argument("--case", choices=["all", "antojitos", "volcan", "movigo"], default="all")
    p_bun.add_argument("--no-archive", action="store_true", help="Skip creating .tar.gz compressed archive")
    p_bun.set_defaults(func=cmd_bundle)

    # 6. mock-api
    p_mock = subparsers.add_parser("mock-api", help="Run mock Open-Meteo server")
    p_mock.add_argument("--case", choices=["antojitos", "volcan", "movigo"], default="antojitos")
    p_mock.add_argument("--port", type=int, default=None, help="Port to bind server")
    p_mock.set_defaults(func=cmd_mock_api)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
