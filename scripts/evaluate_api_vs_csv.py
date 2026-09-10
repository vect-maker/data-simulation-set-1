#!/usr/bin/env python3
"""Evaluate data exposed by FastAPI against generated CSV simulation artifacts.

Performs automated verification:
1. Endpoint availability and HTTP status
2. Total record count comparison (API vs CSV rows)
3. Schema and column key completeness
4. Data value integrity and precision on sample records
"""

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

ENDPOINT_SPECS = [
    # Caso 1: Antojitos Express
    {
        "case": "antojitos",
        "endpoint": "/antojitos/zonas",
        "csv_file": "antojitos/csv/zonas.csv",
        "pk": "id_zona",
    },
    {
        "case": "antojitos",
        "endpoint": "/antojitos/repartidores",
        "csv_file": "antojitos/csv/repartidores.csv",
        "pk": "id_repartidor",
    },
    {
        "case": "antojitos",
        "endpoint": "/antojitos/categorias",
        "csv_file": "antojitos/csv/categorias_platillo.csv",
        "pk": "id_categoria",
    },
    {
        "case": "antojitos",
        "endpoint": "/antojitos/platillos",
        "csv_file": "antojitos/csv/platillos.csv",
        "pk": "id_platillo",
    },
    {
        "case": "antojitos",
        "endpoint": "/antojitos/promociones",
        "csv_file": "antojitos/csv/promociones.csv",
        "pk": "id_promocion",
    },
    {
        "case": "antojitos",
        "endpoint": "/antojitos/clima",
        "csv_file": "antojitos/csv/clima_diario.csv",
        "pk": "fecha",
    },
    {
        "case": "antojitos",
        "endpoint": "/antojitos/ordenes",
        "csv_file": "antojitos/csv/ordenes.csv",
        "pk": "id_orden",
    },
    {
        "case": "antojitos",
        "endpoint": "/antojitos/detalles",
        "csv_file": "antojitos/csv/detalle_ordenes.csv",
        "pk": "id_detalle",
    },

    # Caso 2: Cooperativa El Volcán
    {
        "case": "volcan",
        "endpoint": "/volcan/fincas",
        "csv_file": "volcan/csv/fincas.csv",
        "pk": "id_finca",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/variedades",
        "csv_file": "volcan/csv/variedades_cafe.csv",
        "pk": "id_variedad",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/beneficios",
        "csv_file": "volcan/csv/beneficios.csv",
        "pk": "id_beneficio",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/cuadrillas",
        "csv_file": "volcan/csv/cuadrillas_corte.csv",
        "pk": "id_cuadrilla",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/clima",
        "csv_file": "volcan/csv/clima_zonas_cafetaleras.csv",
        "pk": "fecha",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/lotes",
        "csv_file": "volcan/csv/lotes_acopio.csv",
        "pk": "id_lote",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/procesamiento",
        "csv_file": "volcan/csv/procesamiento_beneficio.csv",
        "pk": "id_proceso",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/subastas",
        "csv_file": "volcan/csv/subastas_especiales.csv",
        "pk": "id_subasta",
    },
    {
        "case": "volcan",
        "endpoint": "/volcan/embarques",
        "csv_file": "volcan/csv/embarques_exportacion.csv",
        "pk": "id_embarque",
    },

    # Caso 3: MoviGo
    {
        "case": "movigo",
        "endpoint": "/movigo/zonas",
        "csv_file": "movigo/csv/zonas_urbanas.csv",
        "pk": "id_zona",
    },
    {
        "case": "movigo",
        "endpoint": "/movigo/usuarios",
        "csv_file": "movigo/csv/usuarios.csv",
        "pk": "id_usuario",
    },
    {
        "case": "movigo",
        "endpoint": "/movigo/conductores",
        "csv_file": "movigo/csv/conductores.csv",
        "pk": "id_conductor",
    },
    {
        "case": "movigo",
        "endpoint": "/movigo/campanas",
        "csv_file": "movigo/csv/campanas_incentivos.csv",
        "pk": "id_campana",
    },
    {
        "case": "movigo",
        "endpoint": "/movigo/clima",
        "csv_file": "movigo/csv/clima_cuadrantes.csv",
        "pk": "fecha",
    },
    {
        "case": "movigo",
        "endpoint": "/movigo/viajes",
        "csv_file": "movigo/csv/viajes.csv",
        "pk": "id_viaje",
    },
    {
        "case": "movigo",
        "endpoint": "/movigo/telemetria",
        "csv_file": "movigo/csv/telemetria_conductores.csv",
        "pk": "id_telemetria",
    },
]


def compare_values(val_api: Any, val_csv: Any, tolerance: float = 0.01) -> bool:
    """Compare an API field value against a CSV string/parsed value."""
    # Check nulls
    is_api_null = val_api is None or (isinstance(val_api, float) and math.isnan(val_api))
    is_csv_null = pd.isna(val_csv) or val_csv == "" or val_csv is None

    if is_api_null and is_csv_null:
        return True
    if is_api_null != is_csv_null:
        return False

    # Booleans (check first because in Python bool is a subclass of int)
    if isinstance(val_api, bool):
        if isinstance(val_csv, bool):
            return val_api == val_csv
        str_csv = str(val_csv).lower()
        if str_csv in ("true", "t", "1"):
            return val_api is True
        elif str_csv in ("false", "f", "0"):
            return val_api is False
        return False

    # Numbers
    if isinstance(val_api, (int, float)):
        try:
            num_csv = float(val_csv)
            if math.isnan(val_api) and math.isnan(num_csv):
                return True
            return abs(float(val_api) - num_csv) <= tolerance
        except (ValueError, TypeError):
            return False

    # Strings, dates, timestamps
    str_api = str(val_api).strip()
    str_csv = str(val_csv).strip()

    # Handle ISO datetime (e.g., 2024-01-01T18:20:38 vs 2024-01-01 18:20:38)
    if "T" in str_api:
        str_api_norm = str_api.replace("T", " ")
        if str_api_norm == str_csv or str_api_norm.startswith(str_csv) or str_csv.startswith(str_api_norm):
            return True

    return str_api == str_csv


def evaluate_endpoint(
    base_url: str,
    spec: Dict[str, Any],
    artifacts_dir: Path,
    sample_size: int = 50,
    tolerance: float = 0.01,
) -> Dict[str, Any]:
    """Compare a single API endpoint against its corresponding CSV artifact."""
    endpoint = spec["endpoint"]
    csv_path = artifacts_dir / spec["csv_file"]
    pk_col = spec["pk"]

    result = {
        "case": spec["case"],
        "endpoint": endpoint,
        "csv_path": str(csv_path.relative_to(artifacts_dir.parent) if artifacts_dir.parent in csv_path.parents else csv_path),
        "status": "PASS",
        "http_status": None,
        "api_total": 0,
        "csv_rows": 0,
        "count_match": False,
        "columns_match": False,
        "value_match_pct": 100.0,
        "details": [],
    }

    if not csv_path.exists():
        result["status"] = "ERROR"
        result["details"].append(f"CSV file not found: {csv_path}")
        return result

    # Read CSV
    try:
        df_csv = pd.read_csv(csv_path, dtype=str)
        result["csv_rows"] = len(df_csv)
    except Exception as e:
        result["status"] = "ERROR"
        result["details"].append(f"Failed to read CSV: {e}")
        return result

    # Request API
    url = f"{base_url.rstrip('/')}{endpoint}?limit={sample_size}&offset=0"
    try:
        resp = requests.get(url, timeout=5)
        result["http_status"] = resp.status_code
        if resp.status_code != 200:
            result["status"] = "FAIL"
            result["details"].append(f"HTTP {resp.status_code}: {resp.text[:100]}")
            return result
        payload = resp.json()
    except Exception as e:
        result["status"] = "FAIL"
        result["details"].append(f"Request failed: {e}")
        return result

    result["api_total"] = payload.get("total", 0)
    items = payload.get("items", [])

    # Count check
    result["count_match"] = (result["api_total"] == result["csv_rows"])
    if not result["count_match"]:
        result["status"] = "FAIL"
        result["details"].append(f"Row count mismatch: API={result['api_total']}, CSV={result['csv_rows']}")

    # Columns check
    csv_cols = set(df_csv.columns)
    if items:
        api_cols = set(items[0].keys())
        missing_in_api = csv_cols - api_cols
        # DetalleOrden in antojitos might have items nested in order detail, but on list it matches
        if missing_in_api:
            result["columns_match"] = False
            result["status"] = "FAIL"
            result["details"].append(f"Missing in API: {list(missing_in_api)}")
        else:
            result["columns_match"] = True
    else:
        if result["csv_rows"] == 0:
            result["columns_match"] = True
        else:
            result["columns_match"] = False
            result["status"] = "FAIL"
            result["details"].append("API returned 0 items while CSV has data.")

    # Values check
    if items and result["count_match"] and pk_col in df_csv.columns:
        df_csv_indexed = df_csv.set_index(pk_col)
        total_fields = 0
        matched_fields = 0

        for item in items:
            pk_val = str(item.get(pk_col))
            if pk_val in df_csv_indexed.index:
                csv_row = df_csv_indexed.loc[pk_val]
                if isinstance(csv_row, pd.DataFrame):
                    csv_row = csv_row.iloc[0]

                for col, val_api in item.items():
                    if col in csv_row:
                        total_fields += 1
                        val_csv = csv_row[col]
                        if compare_values(val_api, val_csv, tolerance=tolerance):
                            matched_fields += 1
                        else:
                            if len(result["details"]) < 3:
                                result["details"].append(
                                    f"Diff [{pk_val}].{col}: API='{val_api}' vs CSV='{val_csv}'"
                                )

        if total_fields > 0:
            result["value_match_pct"] = round((matched_fields / total_fields) * 100, 2)
            if result["value_match_pct"] < 98.0:
                result["status"] = "WARNING" if result["status"] == "PASS" else result["status"]

    return result


def main():
    parser = argparse.ArgumentParser(description="Evaluate FastAPI Data Exposure vs CSV Artifacts.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="FastAPI base URL (default: http://localhost:8000)")
    parser.add_argument("--case", choices=["all", "antojitos", "volcan", "movigo"], default="all", help="Case to evaluate")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts"), help="Path to artifacts directory")
    parser.add_argument("--sample-size", type=int, default=50, help="Number of records to sample per endpoint")
    parser.add_argument("--tolerance", type=float, default=0.01, help="Numeric tolerance")
    args = parser.parse_args()

    console.print(Panel.fit(
        f"[bold cyan]Evaluación de Integridad: FastAPI API vs Artefactos CSV[/bold cyan]\n"
        f"Base URL: [green]{args.base_url}[/green] | Caso: [yellow]{args.case.upper()}[/yellow] | "
        f"Muestras: [magenta]{args.sample_size}[/magenta]",
        border_style="cyan"
    ))

    # Health check
    try:
        h_resp = requests.get(f"{args.base_url.rstrip('/')}/health", timeout=3)
        if h_resp.status_code == 200:
            console.print("[green]✓ Conexión exitosa con la API y PostgreSQL (Healthcheck OK)[/green]\n")
        else:
            console.print(f"[yellow]⚠ Healthcheck respondió HTTP {h_resp.status_code}: {h_resp.text}[/yellow]\n")
    except Exception as e:
        console.print(f"[bold red]✗ No se pudo conectar a {args.base_url}: {e}[/bold red]")
        console.print("[dim]Asegúrate de que la API esté corriendo con 'just api-up' o 'just api-run'.[/dim]\n")
        sys.exit(1)

    specs = [s for s in ENDPOINT_SPECS if args.case == "all" or s["case"] == args.case]

    table = Table(title="Resultados de Verificación por Endpoint", show_header=True, header_style="bold magenta")
    table.add_column("Caso", style="cyan", width=12)
    table.add_column("Endpoint", style="bold white")
    table.add_column("CSV Filas", justify="right")
    table.add_column("API Total", justify="right")
    table.add_column("Columnas", justify="center")
    table.add_column("Integridad %", justify="right")
    table.add_column("Estado", justify="center")

    total_eval = len(specs)
    passed_eval = 0
    failed_eval = 0
    all_details = []

    for spec in specs:
        res = evaluate_endpoint(
            base_url=args.base_url,
            spec=spec,
            artifacts_dir=args.artifacts_dir,
            sample_size=args.sample_size,
            tolerance=args.tolerance,
        )

        status_text = res["status"]
        if status_text == "PASS":
            passed_eval += 1
            status_style = "[bold green]PASS[/bold green]"
        elif status_text == "WARNING":
            passed_eval += 1
            status_style = "[bold yellow]WARN[/bold yellow]"
        else:
            failed_eval += 1
            status_style = "[bold red]FAIL[/bold red]"

        cols_style = "[green]✓ OK[/green]" if res["columns_match"] else "[red]✗ Error[/red]"
        count_color = "green" if res["count_match"] else "red"
        val_color = "green" if res["value_match_pct"] >= 99.0 else ("yellow" if res["value_match_pct"] >= 95.0 else "red")

        table.add_row(
            res["case"],
            res["endpoint"],
            str(res["csv_rows"]),
            f"[{count_color}]{res['api_total']}[/{count_color}]",
            cols_style,
            f"[{val_color}]{res['value_match_pct']}%[/{val_color}]",
            status_style,
        )

        if res["details"]:
            all_details.append((res["endpoint"], res["details"]))

    console.print(table)

    if all_details:
        console.print("\n[bold yellow]Detalles y Observaciones:[/bold yellow]")
        for ep, notes in all_details:
            console.print(f"  [bold cyan]{ep}[/bold cyan]:")
            for note in notes:
                console.print(f"    • {note}")

    console.print(f"\n[bold]Resumen Final:[/bold] {passed_eval}/{total_eval} endpoints superaron la evaluación "
                  f"({'[green]100% Exitoso[/green]' if failed_eval == 0 else f'[red]{failed_eval} fallos[/red]'})\n")

    sys.exit(0 if failed_eval == 0 else 1)


if __name__ == "__main__":
    main()
