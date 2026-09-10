"""Core Terminal Reporting Engine.

Provides Rich table formatters for the 5 analytical pillars:
- Operational & Demand Summary Table
- Estadística II OLS Gauss-Markov & Hypothesis Testing Table
- Métodos Numéricos & Optimización Solutions Table
"""

from typing import Any
from rich.console import Console
from rich.table import Table

console = Console()


def render_operational_table(
    title: str,
    metrics: list[tuple[str, str]],
    border_style: str = "cyan",
) -> None:
    """Render Rich table for operational indicators."""
    table = Table(title=title, style=border_style)
    table.add_column("Métrica", style="bold white")
    table.add_column("Valor", style="green")

    for metric, value in metrics:
        table.add_row(metric, str(value))

    console.print("\n", table)


def render_statistical_table(
    title: str,
    supuestos: dict[str, Any],
    hipotesis: list[dict[str, Any]],
    border_style: str = "magenta",
) -> None:
    """Render Rich table for regression assumptions and hypothesis tests."""
    table = Table(title=title, style=border_style)
    table.add_column("Análisis / Test", style="bold white")
    table.add_column("Estadístico / Diagnóstico", style="yellow")
    table.add_column("Resultado / Conclusión", style="green")

    norm = supuestos.get("normalidad_residuos", {})
    if norm:
        status_norm = "Cumple Gauss-Markov" if norm.get("cumple_supuesto") else "Aceptable para n grande"
        table.add_row(
            "Normalidad Residuos (Shapiro)",
            f"W = {norm.get('estadistico_w')}, p = {norm.get('p_valor')}",
            status_norm,
        )

    homo = supuestos.get("homocedasticidad", {})
    if homo:
        status_homo = "Varianza residual constante" if homo.get("cumple_supuesto") else "Heterocedasticidad leve"
        table.add_row(
            "Homocedasticidad (Breusch-Pagan)",
            f"LM = {homo.get('estadistico_lm')}, p = {homo.get('p_valor')}",
            status_homo,
        )

    dw = supuestos.get("independencia_errores", {})
    if dw:
        table.add_row(
            "Autocorrelación (Durbin-Watson)",
            f"DW = {dw.get('estadistico_dw')}",
            dw.get("diagnostico", "N/A"),
        )

    for h in hipotesis:
        p_val = h.get("p_valor", 0.0)
        p_str = f"p = {p_val:.4e}" if isinstance(p_val, float) else f"p = {p_val}"
        table.add_row(
            f"Hipótesis: {h.get('id', 'H')}",
            p_str,
            h.get("conclusion", ""),
        )

    console.print("\n", table)


def render_math_optimization_table(
    title: str,
    solutions: list[tuple[str, str]],
    border_style: str = "green",
) -> None:
    """Render Rich table for numerical methods and optimization models."""
    table = Table(title=title, style=border_style)
    table.add_column("Pilar / Modelo", style="bold white")
    table.add_column("Solución Numérica / Prescriptiva", style="cyan")

    for model, sol in solutions:
        table.add_row(model, str(sol))

    console.print("\n", table)
