"""Unit tests for Core Numerical Methods Engine (Métodos Numéricos)."""

import unittest
import numpy as np

from data_sim.core.numerics import (
    bisection_method,
    newton_raphson_method,
    centered_finite_difference,
    calculate_price_elasticity,
    numerical_integration_composite,
    fit_exponential_decay,
)


class TestCoreNumerics(unittest.TestCase):
    """Test suite for numerical analysis algorithms."""

    def test_bisection_root_finding(self):
        # f(x) = x^2 - 4 = 0 on [0, 5], root is 2.0
        f = lambda x: x ** 2 - 4.0
        root, iters, conv = bisection_method(f, 0.0, 5.0, tol=1e-5)
        self.assertTrue(conv)
        self.assertAlmostEqual(root, 2.0, delta=1e-4)

    def test_newton_raphson_root_finding(self):
        # f(x) = x^3 - 27 = 0, f'(x) = 3*x^2, root is 3.0
        f = lambda x: x ** 3 - 27.0
        df = lambda x: 3.0 * (x ** 2)
        root, iters, conv = newton_raphson_method(f, df, x0=5.0, tol=1e-5)
        self.assertTrue(conv)
        self.assertAlmostEqual(root, 3.0, delta=1e-4)

    def test_centered_finite_difference(self):
        # f(x) = x^2 => f'(3) = 6
        # f(3 + 0.1) = 9.61, f(3 - 0.1) = 8.41, h = 0.1
        deriv = centered_finite_difference(9.61, 8.41, h=0.1)
        self.assertAlmostEqual(deriv, 6.0, delta=1e-3)

    def test_price_elasticity(self):
        # dq/dp = -2.0, price = 100, quantity = 100 => elasticity = -2.0 (Elastic)
        val, cls = calculate_price_elasticity(dq_dp=-2.0, price=100.0, quantity=100.0)
        self.assertEqual(val, -2.0)
        self.assertEqual(cls, "Demanda Elastica (|e| > 1)")

        # dq/dp = -0.5, price = 100, quantity = 200 => elasticity = -0.25 (Inelastic)
        val2, cls2 = calculate_price_elasticity(dq_dp=-0.5, price=100.0, quantity=200.0)
        self.assertEqual(val2, -0.25)
        self.assertEqual(cls2, "Demanda Inelastica (|e| < 1)")

    def test_numerical_integration(self):
        # Integrate f(x) = x^2 on [0, 4]. Exact integral is 4^3 / 3 = 64/3 ≈ 21.333
        x = np.linspace(0, 4, 9) # 9 points (8 subintervals, Simpson works exactly)
        y = x ** 2
        res = numerical_integration_composite(y, x)
        self.assertAlmostEqual(res["simpson"], 21.33, delta=0.05)
        self.assertAlmostEqual(res["trapecio"], 21.33, delta=0.5)

    def test_exponential_decay_fit(self):
        # M(t) = 50 * exp(-0.02 * t)
        t = np.array([0.0, 10.0, 20.0, 30.0, 40.0, 50.0])
        m = 50.0 * np.exp(-0.02 * t)
        res = fit_exponential_decay(t, m)
        self.assertAlmostEqual(res["m0"], 50.0, delta=0.5)
        self.assertAlmostEqual(res["k"], 0.02, delta=0.002)
        self.assertGreater(res["r2"], 0.999)


if __name__ == "__main__":
    unittest.main()
