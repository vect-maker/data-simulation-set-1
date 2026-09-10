"""Unit tests for Core Optimization Engine (Optimización)."""

import unittest
import numpy as np

from data_sim.core.optimization import (
    knapsack_01,
    solve_hungarian_assignment,
    dijkstra_shortest_path,
    solve_simplex_lp,
    compute_critical_path_method,
)


class TestCoreOptimization(unittest.TestCase):
    """Test suite for mathematical optimization algorithms."""

    def test_knapsack_01(self):
        names = ["Item1", "Item2", "Item3"]
        weights = [10, 20, 30]
        values = [60.0, 100.0, 120.0]
        capacity = 50

        res = knapsack_01(names, weights, values, capacity)
        # Optimal items: Item2 (20, 100) and Item3 (30, 120) => Weight 50, Value 220
        self.assertEqual(res["retorno_maximo"], 220.0)
        self.assertEqual(res["costo_total"], 50)
        self.assertIn("Item2", res["items_seleccionados"])
        self.assertIn("Item3", res["items_seleccionados"])

    def test_hungarian_assignment(self):
        cost_matrix = np.array([
            [9, 2, 7],
            [6, 4, 3],
            [5, 8, 1],
        ])
        # Optimal assignment: (0->1: 2), (1->0: 6), (2->2: 1) => total = 9
        res = solve_hungarian_assignment(cost_matrix)
        self.assertEqual(res["costo_total_minimo"], 9.0)
        self.assertEqual(len(res["filas_asignadas"]), 3)

    def test_dijkstra_shortest_path(self):
        graph = {
            "A": {"B": 4.0, "C": 2.0},
            "B": {"A": 4.0, "C": 1.0, "D": 5.0},
            "C": {"A": 2.0, "B": 1.0, "D": 8.0, "E": 10.0},
            "D": {"B": 5.0, "C": 8.0, "E": 2.0},
            "E": {"C": 10.0, "D": 2.0},
        }
        # Shortest path A -> E: A -> C (2) -> B (3) -> D (8) -> E (10)
        # Or A -> B (4) -> D (9) -> E (11)
        # Or A -> C (2) -> E (12)
        # Best: A -> C -> B -> D -> E = 2 + 1 + 5 + 2 = 10.0
        path, dist = dijkstra_shortest_path(graph, "A", "E")
        self.assertEqual(path, ["A", "C", "B", "D", "E"])
        self.assertEqual(dist, 10.0)

    def test_simplex_lp(self):
        # Maximize 3x1 + 2x2 subject to:
        # 2x1 + x2 <= 100
        # x1 + x2 <= 80
        # x1, x2 >= 0
        c = np.array([3.0, 2.0])
        A_ub = [[2.0, 1.0], [1.0, 1.0]]
        b_ub = [100.0, 80.0]
        bounds = [(0, None), (0, None)]

        res = solve_simplex_lp(c, A_ub, b_ub, bounds=bounds, maximize=True)
        self.assertTrue(res["exito"])
        # Optimal solution: x1 = 20, x2 = 60 => Value = 3*20 + 2*60 = 180
        self.assertAlmostEqual(res["valor_objetivo"], 180.0, delta=0.1)
        self.assertAlmostEqual(res["solucion_optima"][0], 20.0, delta=0.1)
        self.assertAlmostEqual(res["solucion_optima"][1], 60.0, delta=0.1)
        self.assertEqual(len(res["precios_sombra"]), 2)

    def test_critical_path_method(self):
        activities = {
            "A": {"duracion": 3, "predecesores": []},
            "B": {"duracion": 4, "predecesores": ["A"]},
            "C": {"duracion": 2, "predecesores": ["A"]},
            "D": {"duracion": 5, "predecesores": ["B", "C"]},
        }
        res = compute_critical_path_method(activities)
        # Path A (3) -> B (4) -> D (5) = 12
        # Path A (3) -> C (2) -> D (5) = 10
        # Critical path: A -> B -> D, duration = 12
        self.assertEqual(res["duracion_total_proyecto"], 12.0)
        self.assertEqual(res["ruta_critica"], ["A", "B", "D"])
        self.assertEqual(res["holguras"]["C"], 2.0)
        self.assertEqual(res["holguras"]["B"], 0.0)


if __name__ == "__main__":
    unittest.main()
