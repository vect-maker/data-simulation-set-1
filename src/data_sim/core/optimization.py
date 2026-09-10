"""Core Optimization Engine (Optimización).

Provides canonical implementations and solvers for:
- 0/1 Knapsack Problem (Dynamic Programming with item backtracking)
- Hungarian Algorithm for bipartite matching / driver-courier dispatch
- Dijkstra's Shortest Path on urban road graphs
- Linear Programming / Simplex with dual shadow price extraction
- Transportation Problem solver
- Critical Path Method (CPM / PERT) with project slack calculations
"""

from typing import Any
import heapq
import numpy as np
from scipy.optimize import linprog, linear_sum_assignment


def knapsack_01(
    item_names: list[str],
    weights: list[int],
    values: list[float],
    capacity: int,
) -> dict[str, Any]:
    """Solve 0/1 Knapsack Problem using Dynamic Programming with full backtracking."""
    n = len(weights)
    if n == 0 or capacity <= 0:
        return {
            "retorno_maximo": 0.0,
            "costo_total": 0.0,
            "items_seleccionados": [],
        }

    # DP table: (n + 1) x (capacity + 1)
    dp = np.zeros((n + 1, capacity + 1), dtype=float)

    for i in range(1, n + 1):
        w = int(weights[i - 1])
        v = float(values[i - 1])
        for c in range(capacity + 1):
            if w <= c:
                dp[i, c] = max(dp[i - 1, c], dp[i - 1, c - w] + v)
            else:
                dp[i, c] = dp[i - 1, c]

    # Backtracking
    selected = []
    curr_cap = capacity
    total_cost = 0

    for i in range(n, 0, -1):
        if dp[i, curr_cap] != dp[i - 1, curr_cap]:
            selected.append(item_names[i - 1])
            total_cost += weights[i - 1]
            curr_cap -= int(weights[i - 1])

    selected.reverse()
    return {
        "retorno_maximo": round(float(dp[n, capacity]), 2),
        "costo_total": total_cost,
        "capacidad_presupuesto": capacity,
        "items_seleccionados": selected,
    }


def solve_hungarian_assignment(cost_matrix: np.ndarray) -> dict[str, Any]:
    """Solve optimal bipartite assignment problem minimizing total cost/time."""
    costs = np.asarray(cost_matrix, dtype=float)
    row_ind, col_ind = linear_sum_assignment(costs)
    total_cost = float(costs[row_ind, col_ind].sum())

    return {
        "filas_asignadas": row_ind.tolist(),
        "columnas_asignadas": col_ind.tolist(),
        "costo_total_minimo": round(total_cost, 2),
        "tamano_matriz": f"{costs.shape[0]}x{costs.shape[1]}",
    }


def dijkstra_shortest_path(
    graph: dict[str, dict[str, float]],
    source: str,
    target: str,
) -> tuple[list[str], float]:
    """Find the shortest path on a weighted graph using Dijkstra's algorithm.

    Args:
        graph: Adjacency map {node: {neighbor: cost}}
        source: Starting node ID
        target: Ending node ID

    Returns:
        (path_list, total_cost)
    """
    distances: dict[str, float] = {node: float("inf") for node in graph}
    previous: dict[str, str | None] = {node: None for node in graph}
    distances[source] = 0.0

    pq = [(0.0, source)]

    while pq:
        curr_dist, curr_node = heapq.heappop(pq)

        if curr_node == target:
            break

        if curr_dist > distances.get(curr_node, float("inf")):
            continue

        for neighbor, weight in graph.get(curr_node, {}).items():
            dist = curr_dist + weight
            if dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = dist
                previous[neighbor] = curr_node
                heapq.heappush(pq, (dist, neighbor))

    # Reconstruct path
    path = []
    curr: str | None = target
    while curr is not None:
        path.append(curr)
        curr = previous.get(curr)

    path.reverse()
    total_dist = distances.get(target, float("inf"))
    if not path or path[0] != source:
        return [], float("inf")

    return path, round(total_dist, 2)


def solve_simplex_lp(
    c: np.ndarray,
    A_ub: np.ndarray,
    b_ub: np.ndarray,
    bounds: list[tuple[float | None, float | None]] | None = None,
    maximize: bool = True,
) -> dict[str, Any]:
    """Solve continuous Linear Programming problem using HiGHS Simplex/Interior point.

    Returns optimal quantities, objective value, and dual shadow prices.
    """
    c_vec = -np.asarray(c, dtype=float) if maximize else np.asarray(c, dtype=float)
    A_mat = np.asarray(A_ub, dtype=float)
    b_vec = np.asarray(b_ub, dtype=float)

    res = linprog(c_vec, A_ub=A_mat, b_ub=b_vec, bounds=bounds, method="highs")

    if not res.success:
        return {
            "exito": False,
            "valor_objetivo": 0.0,
            "solucion_optima": [],
            "precios_sombra": [],
        }

    opt_val = float(-res.fun) if maximize else float(res.fun)
    sol = [round(float(x), 4) for x in res.x]

    # Extract shadow prices (marginals)
    shadow_prices = []
    if hasattr(res, "ineqlin") and res.ineqlin is not None and hasattr(res.ineqlin, "marginals"):
        shadow_prices = [round(float(abs(m)), 4) for m in res.ineqlin.marginals]
    else:
        shadow_prices = [0.0] * len(b_vec)

    return {
        "exito": True,
        "valor_objetivo": round(opt_val, 2),
        "solucion_optima": sol,
        "precios_sombra": shadow_prices,
    }


def compute_critical_path_method(
    activities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute Critical Path Method (CPM / PERT) with ES, EF, LS, LF, and total float/slack.

    Args:
        activities: {
            "A": {"duracion": 2, "predecesores": []},
            "B": {"duracion": 3, "predecesores": ["A"]},
            ...
        }
    """
    # 1. Forward Pass (ES, EF)
    es: dict[str, float] = {}
    ef: dict[str, float] = {}

    for act, data in activities.items():
        preds = data.get("predecesores", [])
        if not preds:
            es[act] = 0.0
        else:
            es[act] = max(ef[p] for p in preds if p in ef)
        ef[act] = es[act] + data["duracion"]

    project_duration = max(ef.values()) if ef else 0.0

    # 2. Backward Pass (LS, LF)
    lf: dict[str, float] = {}
    ls: dict[str, float] = {}

    # Identify successors
    successors: dict[str, list[str]] = {act: [] for act in activities}
    for act, data in activities.items():
        for p in data.get("predecesores", []):
            if p in successors:
                successors[p].append(act)

    for act in reversed(list(activities.keys())):
        succs = successors[act]
        if not succs:
            lf[act] = project_duration
        else:
            lf[act] = min(ls[s] for s in succs if s in ls)
        ls[act] = lf[act] - activities[act]["duracion"]

    # 3. Slacks & Critical Path
    slacks = {}
    critical_path = []
    for act in activities:
        slack = round(ls[act] - es[act], 2)
        slacks[act] = slack
        if abs(slack) < 1e-4:
            critical_path.append(act)

    return {
        "duracion_total_proyecto": project_duration,
        "ruta_critica": critical_path,
        "holguras": slacks,
        "tiempos_actividad": {
            act: {
                "ES": es[act],
                "EF": ef[act],
                "LS": ls[act],
                "LF": lf[act],
                "holgura": slacks[act],
            }
            for act in activities
        },
    }
