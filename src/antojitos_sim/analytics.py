"""Advanced Analytics & Mathematical Engine for Antojitos Express.

Delegates core computations to data_sim.core while maintaining business domain models:
- Estadistica II: OLS Regression, Gauss-Markov assumptions, Welch t-test, z-test, ANOVA
- Metodos Numericos: Root finding (Bisection & Newton), Numerical integration (Simpson/Trapezoid), Elasticity
- Optimizacion: Simplex LP (kitchen capacity & shadow prices), Hungarian courier dispatch, Knapsack 0/1
"""

from typing import Any
import numpy as np
import pandas as pd

from data_sim.core.stats import (
    compute_ols_regression,
    verify_gauss_markov,
    welch_ttest,
    two_proportion_ztest,
    one_way_anova_test,
)
from data_sim.core.numerics import (
    bisection_method,
    newton_raphson_method,
    centered_finite_difference,
    calculate_price_elasticity,
    numerical_integration_composite,
)
from data_sim.core.optimization import (
    solve_simplex_lp,
    solve_hungarian_assignment,
    knapsack_01,
)


def compute_estadistica_ii_models(
    df_orders: pd.DataFrame,
    df_clima: pd.DataFrame,
    df_details: pd.DataFrame,
    df_platillos: pd.DataFrame,
    df_zonas: pd.DataFrame,
    df_repartidores: pd.DataFrame,
) -> dict[str, Any]:
    """Perform formal Estadistica II inferential battery."""
    df_orders["fecha"] = pd.to_datetime(df_orders["fecha_hora_creacion"]).dt.date
    daily_orders = df_orders.groupby("fecha").size().reset_index(name="num_orders")
    merged_weather = pd.merge(df_clima, daily_orders, on="fecha", how="left").fillna(0)

    # 1. OLS Regression: Daily Rain (mm) -> Daily Orders
    x = merged_weather["precipitacion_mm"].values.astype(float)
    y = merged_weather["num_orders"].values.astype(float)

    anova_table, residuals, _, _, _ = compute_ols_regression(
        x, y, x_label="Precipitacion Diaria mm", y_label="Numero de Ordenes"
    )
    supuestos_regresion = verify_gauss_markov(x, residuals)

    # 2. Formal Hypothesis Testing (>= 3 Tests)
    df_merged_orders = df_orders.merge(df_clima[["fecha", "precipitacion_mm"]], on="fecha", how="left")

    # Test A: Difference of Means (Welch t-test)
    rain_tickets = df_merged_orders[df_merged_orders["precipitacion_mm"] > 2.0]["total_orden"]
    dry_tickets = df_merged_orders[df_merged_orders["precipitacion_mm"] <= 2.0]["total_orden"]
    test_a = welch_ttest(
        sample_a=rain_tickets,
        sample_b=dry_tickets,
        test_id="H1_DOS_MEDIAS",
        name="Diferencia de Medias en Ticket Total (Lluvia vs Dia Seco)",
        conclusion_true="Existe diferencia estadisticamente significativa en el ticket promedio por efecto de la lluvia.",
    )

    # Test B: Difference of Proportions (z-test)
    heavy_rain = df_merged_orders[df_merged_orders["precipitacion_mm"] > 10.0]
    dry_orders = df_merged_orders[df_merged_orders["precipitacion_mm"] <= 10.0]
    n1 = len(heavy_rain)
    x1 = int((heavy_rain["estado_orden"] == "cancelada").sum()) if n1 > 0 else 0
    n2 = len(dry_orders)
    x2 = int((dry_orders["estado_orden"] == "cancelada").sum()) if n2 > 0 else 0

    test_b = two_proportion_ztest(
        count_1=x1,
        n_1=n1,
        count_2=x2,
        n_2=n2,
        test_id="H2_DOS_PROPORCIONES",
        name="Diferencia de Proporciones en Tasa de Cancelacion (Aguacero vs Seco)",
        conclusion_true="La lluvia extrema incrementa de forma significativa la tasa de cancelacion por friccion de transito.",
    )

    # Test C: One-Way ANOVA across Vehicle Types
    orders_delivered = df_orders[df_orders["estado_orden"] == "entregada"].copy()
    if not orders_delivered.empty and "fecha_hora_entrega" in orders_delivered:
        orders_delivered["duracion_min"] = (
            pd.to_datetime(orders_delivered["fecha_hora_entrega"])
            - pd.to_datetime(orders_delivered["fecha_hora_creacion"])
        ).dt.total_seconds() / 60.0
    else:
        orders_delivered["duracion_min"] = 30.0

    merged_vehicles = (
        orders_delivered.merge(
            df_repartidores[["id_repartidor", "tipo_vehiculo"]], on="id_repartidor", how="left"
        )
        if not df_repartidores.empty
        else pd.DataFrame()
    )

    groups = []
    for veh in ["moto", "bicicleta", "auto"]:
        s = (
            merged_vehicles[merged_vehicles["tipo_vehiculo"] == veh]["duracion_min"]
            if not merged_vehicles.empty
            else pd.Series()
        )
        groups.append((veh, s))

    test_c = one_way_anova_test(
        groups=groups,
        test_id="H3_ANOVA_VEHICULOS",
        name="Comparacion de Tiempos de Despacho segun Tipo de Vehiculo",
        conclusion_true="Existen diferencias altamente significativas en el tiempo de entrega segun el vehiculo del repartidor.",
    )

    return {
        "regresion_lineal_anova": anova_table,
        "validacion_supuestos": supuestos_regresion,
        "bateria_pruebas_hipotesis": [test_a, test_b, test_c],
    }


def compute_metodos_numericos_models(df_orders: pd.DataFrame) -> dict[str, Any]:
    """Calculate numerical analysis problems and analytical benchmarks."""
    # 1. Non-linear root finding: Break-Even Point f(q) = -0.0035 q^2 + 225 q - 350000 = 0
    profit_fun = lambda q: -0.0035 * (q ** 2) + 225.0 * q - 350000.0
    profit_deriv = lambda q: -0.0070 * q + 225.0

    root_bis, iter_bis, _ = bisection_method(profit_fun, 1000.0, 10000.0, tol=1e-4)
    root_newt, iter_newt, _ = newton_raphson_method(profit_fun, profit_deriv, 2000.0, tol=1e-4)
    q_star_optimal = 225.0 / 0.0070

    # 2. Numerical Integration: Total Hourly Demand Intensity
    df_orders["hora"] = pd.to_datetime(df_orders["fecha_hora_creacion"]).dt.hour
    hourly_counts = df_orders.groupby("hora").size().reindex(range(24), fill_value=0).values.astype(float)
    x_hours = np.arange(24, dtype=float)

    integ = numerical_integration_composite(hourly_counts, x_hours)
    discrete_sum = integ["suma_discreta"]
    err_pct = (
        round(abs(integ["simpson"] - discrete_sum) / discrete_sum * 100, 4)
        if discrete_sum > 0
        else 0.0
    )

    # 3. Numerical Differentiation: Price Elasticity of Demand
    demands = np.array([68500.0, 61200.0, 54500.0, 48100.0, 42000.0])
    h = 30.0
    dq_centered = centered_finite_difference(demands[3], demands[1], h)
    elasticity_p340, elast_class = calculate_price_elasticity(dq_centered, price=340.0, quantity=demands[2])

    return {
        "ecuaciones_no_lineales_raices": {
            "modelo": "Punto de Equilibrio de Cocina Fantasma: pi(q) = -0.0035 q^2 + 225 q - 350000 = 0",
            "raiz_biseccion_ordenes": round(root_bis, 2),
            "iteraciones_biseccion": iter_bis,
            "raiz_newton_raphson_ordenes": round(root_newt, 2),
            "iteraciones_newton": iter_newt,
            "q_optimo_maximo_beneficio": round(q_star_optimal, 2),
        },
        "integracion_numerica_demanda": {
            "descripcion": "Integracion de curva horaria de intensidad de pedidos en Managua",
            "suma_discreta_real": discrete_sum,
            "integral_regla_trapecio": integ["trapecio"],
            "integral_regla_simpson_compuesta": integ["simpson"],
            "error_relativo_simpson_pct": err_pct,
        },
        "diferenciacion_numerica_elasticidad": {
            "precio_evaluado_nio": 340.0,
            "derivada_dq_dp_centrada": round(dq_centered, 2),
            "elasticidad_precio_demanda": elasticity_p340,
            "clasificacion": elast_class,
        },
    }


def compute_optimizacion_models() -> dict[str, Any]:
    """Solve Linear Programming Simplex (with Shadow Prices), Hungarian Assignment, and Knapsack."""
    # 1. Simplex LP
    c = np.array([120.0, 65.0, 110.0, 55.0])
    A_ub = [
        [15.0, 5.0, 10.0, 20.0],
        [20.0, 8.0, 15.0, 5.0],
        [0.5, 0.2, 0.3, 0.25],
    ]
    b_ub = [480.0, 600.0, 24.0]
    bounds = [(5.0, None), (5.0, None), (5.0, None), (5.0, None)]

    res_lp = solve_simplex_lp(c, A_ub, b_ub, bounds=bounds, maximize=True)

    # 2. Hungarian Assignment
    cost_matrix = np.array([
        [18, 22, 14, 25, 30],
        [24, 15, 20, 19, 28],
        [12, 18, 26, 22, 16],
        [32, 28, 15, 18, 20],
        [20, 14, 22, 26, 15],
    ])
    res_hungarian = solve_hungarian_assignment(cost_matrix)

    # 3. Knapsack 0/1
    campaign_costs = [12000, 8500, 15000, 9000, 11000, 7500, 14000]
    campaign_returns = [38000.0, 24000.0, 46000.0, 26000.0, 31000.0, 21000.0, 42000.0]
    campaign_names = [
        "PROMO-COMBO-FRITANGA", "PROMO-QUESILLO-FIESTA", "PROMO-BURGER-BEER",
        "PROMO-DULCE-TRADICION", "PROMO-CACAO-LOVERS", "PROMO-SNACK-ATTACK", "PROMO-ASADOS-VIP",
    ]
    budget = 50000
    res_knapsack = knapsack_01(campaign_names, campaign_costs, campaign_returns, budget)

    return {
        "programacion_lineal_simplex": {
            "modelo": "Max Z = 120 x1 + 65 x2 + 110 x3 + 55 x4 s.a. Horno <= 480m, Plancha <= 600m, Cocineros <= 24h",
            "exito": res_lp["exito"],
            "margen_maximo_nio": res_lp["valor_objetivo"],
            "cantidades_optimas": res_lp["solucion_optima"],
            "precios_sombra_restricciones": res_lp["precios_sombra"],
            "interpretacion_precios_sombra": "Incremento en ganancia por cada minuto adicional de capacidad en horno/plancha.",
        },
        "algoritmo_hungaro_asignacion": {
            "matriz_dimension": "5x5 (Repartidores x Zonas)",
            "asignacion_optima_filas": res_hungarian["filas_asignadas"],
            "asignacion_optima_columnas": res_hungarian["columnas_asignadas"],
            "tiempo_total_minutos": res_hungarian["costo_total_minimo"],
        },
        "problema_de_la_mochila_promociones": {
            "presupuesto_limite_nio": budget,
            "retorno_maximo_esperado_nio": res_knapsack["retorno_maximo"],
            "campanas_seleccionadas": res_knapsack["items_seleccionados"],
        },
    }
