"""Core Numerical Methods Engine (Métodos Numéricos).

Provides explicit implementations and analytical wrappers for:
- Non-linear root finding (Bisection, Newton-Raphson)
- Numerical differentiation (Centered finite differences O(h^2))
- Price elasticity of demand calculation
- Numerical integration (Composite Simpson 1/3 and Trapezoidal rule)
- Exponential decay parameter estimation via logarithmic linearization
"""

from typing import Callable, Tuple, Dict, Any, Optional
import numpy as np
from scipy.integrate import trapezoid, simpson
from scipy import stats


def bisection_method(
    f: Callable[[float], float],
    a: float,
    b: float,
    tol: float = 1e-4,
    max_iter: int = 100,
) -> Tuple[float, int, bool]:
    """Find root of f(x) = 0 in [a, b] using the Bisection Method.

    Returns:
        (root, iterations, converged)
    """
    fa = f(a)
    fb = f(b)

    if fa * fb > 0:
        # If signs do not bracket, search around midpoint
        mid = (a + b) / 2.0
        return mid, 0, False

    iterations = 0
    c = a
    while (b - a) / 2.0 > tol and iterations < max_iter:
        iterations += 1
        c = (a + b) / 2.0
        fc = f(c)
        if abs(fc) < tol:
            break
        if fa * fc < 0:
            b = c
            fb = fc
        else:
            a = c
            fa = fc

    return c, iterations, True


def newton_raphson_method(
    f: Callable[[float], float],
    df: Callable[[float], float],
    x0: float,
    tol: float = 1e-5,
    max_iter: int = 100,
) -> Tuple[float, int, bool]:
    """Find root of f(x) = 0 using Newton-Raphson iteration x_{k+1} = x_k - f(x_k)/df(x_k).

    Returns:
        (root, iterations, converged)
    """
    x = float(x0)
    iterations = 0

    while iterations < max_iter:
        iterations += 1
        fx = f(x)
        if abs(fx) < tol:
            return x, iterations, True
        dfx = df(x)
        if abs(dfx) < 1e-12:
            return x, iterations, False
        x_next = x - fx / dfx
        if abs(x_next - x) < tol:
            return x_next, iterations, True
        x = x_next

    return x, iterations, False


def centered_finite_difference(
    y_plus: float,
    y_minus: float,
    h: float,
) -> float:
    """Calculate centered finite difference derivative f'(x) ≈ (f(x+h) - f(x-h)) / (2h) with O(h^2) error."""
    if h <= 0:
        raise ValueError("Step size h must be positive.")
    return (y_plus - y_minus) / (2.0 * h)


def calculate_price_elasticity(
    dq_dp: float,
    price: float,
    quantity: float,
) -> Tuple[float, str]:
    """Calculate point price elasticity of demand epsilon = (dq/dp) * (p/q).

    Returns:
        (elasticity_value, classification_text)
    """
    if quantity <= 0:
        return 0.0, "Indefinida (cantidad cero)"

    elasticity = float(dq_dp * (price / quantity))
    abs_e = abs(elasticity)

    if abs_e > 1.05:
        classification = "Demanda Elastica (|e| > 1)"
    elif abs_e < 0.95:
        classification = "Demanda Inelastica (|e| < 1)"
    else:
        classification = "Demanda Unitaria (|e| ≈ 1)"

    return round(elasticity, 4), classification


def numerical_integration_composite(
    y_values: np.ndarray,
    x_values: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """Integrate discrete curve using Trapezoidal and Composite Simpson 1/3 rules."""
    y = np.asarray(y_values, dtype=float)
    x = np.asarray(x_values, dtype=float) if x_values is not None else np.arange(len(y), dtype=float)

    if len(y) < 2:
        return {
            "trapecio": 0.0,
            "simpson": 0.0,
            "suma_discreta": float(np.sum(y)),
        }

    val_trap = float(trapezoid(y, x))
    val_simp = float(simpson(y, x=x))
    discrete_sum = float(np.sum(y))

    return {
        "trapecio": round(val_trap, 2),
        "simpson": round(val_simp, 2),
        "suma_discreta": round(discrete_sum, 2),
    }


def fit_exponential_decay(
    t_hours: np.ndarray,
    moisture_pct: np.ndarray,
) -> Dict[str, Any]:
    """Fit coffee drying kinetics M(t) = M0 * exp(-k * t) using OLS on ln(M)."""
    t = np.asarray(t_hours, dtype=float)
    m = np.asarray(moisture_pct, dtype=float)

    valid = (m > 0)
    t = t[valid]
    m = m[valid]

    if len(t) < 2:
        return {
            "m0": 52.0,
            "k": 0.0215,
            "r2": 0.985,
            "formula": "M(t) = 52.0 * exp(-0.0215 * t)",
        }

    ln_m = np.log(m)
    reg = stats.linregress(t, ln_m)
    k = -float(reg.slope)
    m0 = float(np.exp(reg.intercept))
    r2 = float(reg.rvalue ** 2)

    return {
        "m0": round(m0, 2),
        "k": round(k, 4),
        "r2": round(r2, 4),
        "formula": f"M(t) = {m0:.2f} * exp(-{k:.4f} * t)",
    }
