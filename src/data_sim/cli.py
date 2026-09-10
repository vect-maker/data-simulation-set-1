"""Unified CLI Interface for Data Simulation Suite.

Provides unified management across all 3 semester project simulation engines:
- generate: Execute simulation pipelines and produce CSV & SQL artifacts
- inspect: Display rich multi-pillar academic indicators and model benchmarks
- load: Load schemas and synthetic data into PostgreSQL
- weather: Fetch driver meteorological series from Open-Meteo API
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

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
