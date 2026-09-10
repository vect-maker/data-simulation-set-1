"""Unit tests for Core Statistical & Econometric Engine (Estadística II)."""

import unittest
import numpy as np
import pandas as pd

from data_sim.core.stats import (
    compute_ols_regression,
    verify_gauss_markov,
    compute_contingency_chi2,
    welch_ttest,
    two_proportion_ztest,
    one_way_anova_test,
)


class TestCoreStats(unittest.TestCase):
    """Test suite for statistical inferential methods."""

    def setUp(self):
        np.random.seed(42)
        # Synthetic linear relationship: y = 20 + 3.5 * x + noise
        self.x = np.linspace(5, 50, 60)
        self.y = 20.0 + 3.5 * self.x + np.random.normal(0, 4.0, size=len(self.x))

    def test_ols_regression_and_anova_table(self):
        anova, residuals, y_pred, slope, intercept = compute_ols_regression(
            self.x, self.y, x_label="TestX", y_label="TestY"
        )
        self.assertAlmostEqual(slope, 3.5, delta=0.5)
        self.assertAlmostEqual(intercept, 20.0, delta=5.0)
        self.assertGreater(anova["r_cuadrado"], 0.90)
        self.assertLess(anova["f_p_valor"], 1e-10)
        self.assertEqual(len(anova["fuente_variacion"]), 3)
        self.assertEqual(len(residuals), len(self.x))

    def test_gauss_markov_diagnostics(self):
        _, residuals, _, _, _ = compute_ols_regression(self.x, self.y)
        diagnostics = verify_gauss_markov(self.x, residuals)

        self.assertIn("normalidad_residuos", diagnostics)
        self.assertIn("homocedasticidad", diagnostics)
        self.assertIn("independencia_errores", diagnostics)

        # For normal i.i.d. noise, Shapiro-Wilk should not reject at 0.01
        self.assertTrue(diagnostics["normalidad_residuos"]["cumple_supuesto"])
        self.assertTrue(diagnostics["homocedasticidad"]["cumple_supuesto"])
        # Durbin-Watson should be reasonably close to 2.0
        dw = diagnostics["independencia_errores"]["estadistico_dw"]
        self.assertTrue(1.4 <= dw <= 2.6)

    def test_contingency_chi_square(self):
        # Create non-independent categorical data
        df = pd.DataFrame({
            "zona": ["Z1"] * 50 + ["Z2"] * 50,
            "categoria": ["CatA"] * 40 + ["CatB"] * 10 + ["CatA"] * 10 + ["CatB"] * 40,
        })
        chi2_res = compute_contingency_chi2(df, "zona", "categoria")
        self.assertTrue(chi2_res["guarantee_p_less_than_0_01"])
        self.assertLess(chi2_res["p_value"], 0.001)

    def test_welch_ttest(self):
        s1 = pd.Series(np.random.normal(100, 10, size=50))
        s2 = pd.Series(np.random.normal(120, 15, size=50))
        res = welch_ttest(s1, s2, test_id="T1", name="Test Means", conclusion_true="Diferencia detectada")
        self.assertTrue(res["rechaza_h0_alpha"])
        self.assertLess(res["p_valor"], 0.01)

    def test_two_proportion_ztest(self):
        # 40/100 vs 15/100
        res = two_proportion_ztest(40, 100, 15, 100, test_id="Z1", name="Test Prop", conclusion_true="Diferencia de prop")
        self.assertTrue(res["rechaza_h0_alpha"])
        self.assertLess(res["p_valor"], 0.01)

    def test_one_way_anova(self):
        g1 = ("A", pd.Series(np.random.normal(10, 2, size=30)))
        g2 = ("B", pd.Series(np.random.normal(20, 2, size=30)))
        g3 = ("C", pd.Series(np.random.normal(30, 2, size=30)))
        res = one_way_anova_test([g1, g2, g3], test_id="A1", name="ANOVA Test", conclusion_true="Grupos difieren")
        self.assertTrue(res["rechaza_h0_alpha"])
        self.assertLess(res["p_valor"], 1e-5)


if __name__ == "__main__":
    unittest.main()
