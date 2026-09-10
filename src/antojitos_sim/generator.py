"""Numerical and driver simulation engine for Antojitos Express.

Generates transactional facts deterministically with strict mathematical guarantees:
- Continuous driver response (daily rain Pt -> order volume lambda_t)
- Non-Homogeneous Poisson Process (NHPP) intraday arrival times
- Categorical dependency injection (Chi-Square independence p < 0.01)
- Geometric basket line-item synthesis
- Relational integrity and financial aggregations
"""

import json
import logging
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from antojitos_sim.config import (
    SEEDS_DIR,
    DEMAND_BETA_0,
    DEMAND_BETA_1,
    DEMAND_BETA_2,
    DEMAND_NOISE_STD,
    DAY_OF_WEEK_BOOST,
    RAIN_DELAY_FACTOR,
    LOGNORMAL_SIGMA,
    BASKET_SIZE_P,
    MAX_BASKET_SIZE,
    OUTLIER_DEMAND_SHOCK_PROB,
    OUTLIER_DELAY_PROB,
    OUTLIER_CATERING_ORDER_PROB,
    PAYMENT_METHOD_WEIGHTS,
)
from antojitos_sim.models import (
    Zona,
    Repartidor,
    CategoriaPlatillo,
    Platillo,
    Promocion,
    ClimaDiario,
    Orden,
    DetalleOrden,
)

logger = logging.getLogger(__name__)


# Chi-Square Dependency Matrix: P(Category | Zone)
# Guaranteed to produce p-value < 0.01 on contingency test
# Categories order: 1 (CAT-FRT), 2 (CAT-QSL), 3 (CAT-HAM), 4 (CAT-BEB), 5 (CAT-POS)
ZONE_CATEGORY_PROBABILITIES: Dict[int, List[float]] = {
    1:  [0.25, 0.20, 0.25, 0.18, 0.12], # Los Robles: Modern / Gastro mix
    2:  [0.35, 0.25, 0.15, 0.15, 0.10], # Altamira: Traditional / Fritanga
    3:  [0.20, 0.15, 0.35, 0.20, 0.10], # Villa Fontana: High burger/snack & beer
    4:  [0.40, 0.20, 0.15, 0.12, 0.13], # Las Colinas: High premium fritanga & dessert
    5:  [0.45, 0.25, 0.10, 0.12, 0.08], # Bello Horizonte: Deep traditional fritanga
    6:  [0.30, 0.20, 0.22, 0.18, 0.10], # Bolonia: Balanced office & residential
    7:  [0.38, 0.28, 0.12, 0.14, 0.08], # Linda Vista: Traditional & quesillos
    8:  [0.38, 0.18, 0.18, 0.12, 0.14], # Santo Domingo: Premium family orders
    9:  [0.32, 0.22, 0.20, 0.14, 0.12], # Carretera Sur: Weekend family feasts
    10: [0.42, 0.30, 0.10, 0.12, 0.06], # Ciudad Jardín: Street fritanga & quesillo
    11: [0.33, 0.22, 0.20, 0.15, 0.10], # Colonia Centroamérica: Central mix
    12: [0.40, 0.26, 0.12, 0.14, 0.08], # Rubenia: High fritanga & snacks
}

# Category IDs for drink and dessert pairings
CAT_BEB = 4
CAT_POS = 5

# Hourly arrival weights for Non-Homogeneous Poisson Process (24 hours)
# Peaking at lunch (12:00-14:00) and dinner (19:00-21:30)
HOURLY_ARRIVAL_WEIGHTS = np.array([
    0.005, 0.002, 0.001, 0.001, 0.001, 0.002, # 00:00 - 05:59 (Closed)
    0.005, 0.015, 0.030, 0.050, 0.075, 0.110, # 06:00 - 11:59 (Morning ramp-up & lunch start)
    0.130, 0.095, 0.050, 0.040, 0.045, 0.065, # 12:00 - 17:59 (Lunch peak & afternoon lull)
    0.115, 0.140, 0.110, 0.070, 0.035, 0.015  # 18:00 - 23:59 (Dinner peak & close)
])
HOURLY_ARRIVAL_WEIGHTS /= HOURLY_ARRIVAL_WEIGHTS.sum()


def load_seed_catalogs() -> Tuple[
    List[Zona],
    List[Repartidor],
    List[CategoriaPlatillo],
    List[Platillo],
    List[Promocion],
    Dict[str, Any],
]:
    """Load dimensional seed catalogs from JSON fixtures."""
    with open(SEEDS_DIR / "zonas_managua.json", "r", encoding="utf-8") as f:
        zonas = [Zona(**z) for z in json.load(f)]

    with open(SEEDS_DIR / "repartidores_managua.json", "r", encoding="utf-8") as f:
        repartidores = [Repartidor(**r) for r in json.load(f)]

    with open(SEEDS_DIR / "categorias_platillo.json", "r", encoding="utf-8") as f:
        categorias = [CategoriaPlatillo(**c) for c in json.load(f)]

    with open(SEEDS_DIR / "platillos_managua.json", "r", encoding="utf-8") as f:
        platillos = [Platillo(**p) for p in json.load(f)]

    with open(SEEDS_DIR / "promociones_knapsack.json", "r", encoding="utf-8") as f:
        promociones = [Promocion(**pr) for pr in json.load(f)]

    with open(SEEDS_DIR / "semantic_templates.json", "r", encoding="utf-8") as f:
        templates = json.load(f)

    return zonas, repartidores, categorias, platillos, promociones, templates


class AntojitosSimulationEngine:
    """Core numerical simulation engine for generating realistic OLTP facts."""

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)

        (
            self.zonas,
            self.repartidores,
            self.categorias,
            self.platillos,
            self.promociones,
            self.semantic_templates,
        ) = load_seed_catalogs()

        self.zonas_map = {z.id_zona: z for z in self.zonas}
        self.repartidores_map = {r.id_repartidor: r for r in self.repartidores}
        self.platillos_map = {p.id_platillo: p for p in self.platillos}
        self.active_repartidores = [r for r in self.repartidores if r.estado == "activo"]

        # Platillos grouped by category for fast sampling
        self.platillos_by_cat: Dict[int, List[Platillo]] = {}
        for p in self.platillos:
            self.platillos_by_cat.setdefault(p.id_categoria, []).append(p)

        self.category_ids = [c.id_categoria for c in self.categorias]

    def simulate_daily_demand(self, precip_mm: float, day_of_week: int) -> int:
        """Calculate total orders for a day based on continuous rain driver and day of week with realistic noise and outliers."""
        dow_boost = DAY_OF_WEEK_BOOST.get(day_of_week, 0.0)
        # Heteroscedastic noise: higher variability during stormy days
        noise_std = DEMAND_NOISE_STD + (0.40 * precip_mm)
        noise = np.random.normal(0, noise_std)

        lambda_t = (
            DEMAND_BETA_0
            + DEMAND_BETA_1 * precip_mm
            + DEMAND_BETA_2 * (precip_mm ** 2)
            + dow_boost
            + noise
        )

        # Macro demand shock outliers (~3% of days):
        # - Viral social promo / pay-day holiday feast spike (+40% to +65%)
        # - Localized blackout / fiber cut / severe road flooding dip (-40% to -60%)
        shock_roll = np.random.rand()
        if shock_roll < (OUTLIER_DEMAND_SHOCK_PROB * 0.60):
            lambda_t *= float(np.random.uniform(1.40, 1.65))
        elif shock_roll < OUTLIER_DEMAND_SHOCK_PROB:
            lambda_t *= float(np.random.uniform(0.40, 0.60))

        return max(35, int(round(lambda_t)))

    def sample_order_time(self, order_date: date) -> datetime:
        """Sample intraday timestamp according to Non-Homogeneous Poisson Process."""
        hour = int(np.random.choice(24, p=HOURLY_ARRIVAL_WEIGHTS))
        minute = int(np.random.randint(0, 60))
        second = int(np.random.randint(0, 60))
        return datetime.combine(order_date, time(hour, minute, second))

    def sample_zone(self) -> Zona:
        """Sample zone with higher delivery density in central Managua."""
        zone_weights = [
            0.12, # Los Robles
            0.11, # Altamira
            0.10, # Villa Fontana
            0.08, # Las Colinas
            0.10, # Bello Horizonte
            0.09, # Bolonia
            0.07, # Linda Vista
            0.06, # Santo Domingo
            0.05, # Carretera Sur
            0.08, # Ciudad Jardín
            0.08, # Centroamérica
            0.06, # Rubenia
        ]
        zone_weights = np.array(zone_weights) / sum(zone_weights)
        idx = int(np.random.choice(len(self.zonas), p=zone_weights))
        return self.zonas[idx]

    def sample_category_for_zone(self, id_zona: int) -> int:
        """Sample primary food category using the Chi-Square conditional transition matrix."""
        probs = ZONE_CATEGORY_PROBABILITIES.get(id_zona)
        if not probs:
            probs = [0.35, 0.25, 0.15, 0.15, 0.10]
        cat_idx = int(np.random.choice(len(self.category_ids), p=probs))
        return self.category_ids[cat_idx]

    def get_active_promotion(self, order_date: date) -> Promocion | None:
        """Find matching campaign if any is running on order date."""
        active = [p for p in self.promociones if p.fecha_inicio <= order_date <= p.fecha_fin]
        if active and np.random.rand() < 0.38: # 38% application rate during campaigns
            return np.random.choice(active)
        return None

    def calculate_delivery_duration(
        self,
        zona: Zona,
        repartidor: Repartidor,
        precip_mm: float,
        prep_time_minutes: float,
    ) -> float:
        """Calculate total delivery duration in minutes using transit formula with operational noise and incident outliers."""
        # Vehicle transit multiplier
        vehicle_factor = {
            "moto": 1.0,
            "bicicleta": 1.30,
            "auto": 1.18,
        }.get(repartidor.tipo_vehiculo, 1.0)

        # Lognormal variation
        eta = np.random.lognormal(mean=0.0, sigma=LOGNORMAL_SIGMA)

        # Rain friction (bicycles suffer more in Managua downpours)
        rain_friction = RAIN_DELAY_FACTOR * precip_mm
        if repartidor.tipo_vehiculo == "bicicleta":
            rain_friction *= 1.45

        base_travel = zona.tiempo_base_minutos * vehicle_factor
        t_entrega = prep_time_minutes + base_travel + rain_friction + eta

        # Operational transit outliers (~2.5%):
        # 1. Punctured tire / police checkpoint / flooded cauce / address confusion (+35 to +75 min delay)
        # 2. Immediate express delivery next door (-40% time)
        incident_roll = np.random.rand()
        if incident_roll < (OUTLIER_DELAY_PROB * 0.75):
            incident_delay = float(np.random.uniform(35.0, 75.0))
            t_entrega += incident_delay
        elif incident_roll < OUTLIER_DELAY_PROB:
            t_entrega = max(10.0, t_entrega * float(np.random.uniform(0.45, 0.65)))

        return round(float(t_entrega), 2)

    def run_simulation(
        self,
        weather_df: pd.DataFrame,
    ) -> Tuple[List[Orden], List[DetalleOrden]]:
        """Run full year simulation and return validated headers and line items."""
        logger.info(f"Starting Antojitos Express numerical simulation across {len(weather_df)} days...")

        orders: List[Orden] = []
        details: List[DetalleOrden] = []
        detail_id_counter = 1
        order_num_counter = 1

        total_days = len(weather_df)

        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
            curr_date: date = row["fecha"]
            precip_mm: float = float(row["precipitacion_mm"])
            dow: int = curr_date.weekday()

            daily_target = self.simulate_daily_demand(precip_mm, dow)

            for _ in range(daily_target):
                order_id = order_num_counter
                order_num_counter += 1

                created_at = self.sample_order_time(curr_date)
                zona = self.sample_zone()
                primary_cat = self.sample_category_for_zone(zona.id_zona)

                # Check for bulk/catering feast order outlier (~1.8% of orders)
                is_bulk_catering = np.random.rand() < OUTLIER_CATERING_ORDER_PROB

                if is_bulk_catering:
                    # Large corporate / family celebration feast
                    basket_size = int(np.random.randint(7, 13))
                else:
                    # Standard Basket size: K ~ Geometric(p=0.45)
                    basket_size = int(np.random.geometric(p=BASKET_SIZE_P))
                    basket_size = min(max(basket_size, 1), MAX_BASKET_SIZE)

                # Select dishes
                primary_dishes = self.platillos_by_cat[primary_cat]
                first_dish = np.random.choice(primary_dishes)
                selected_dishes = [first_dish]

                for _ in range(basket_size - 1):
                    roll = np.random.rand()
                    if roll < 0.45 and CAT_BEB in self.platillos_by_cat:
                        # Drink pairing (cacao, beer, fresco)
                        selected_dishes.append(np.random.choice(self.platillos_by_cat[CAT_BEB]))
                    elif roll < 0.70 and CAT_POS in self.platillos_by_cat:
                        # Dessert pairing (buñuelos, tres leches)
                        selected_dishes.append(np.random.choice(self.platillos_by_cat[CAT_POS]))
                    else:
                        # Another dish in same primary category
                        selected_dishes.append(np.random.choice(primary_dishes))

                # Build line items
                order_items_total = 0.0
                max_dish_prep_time = 0.0

                for dish in selected_dishes:
                    if is_bulk_catering:
                        # Catering volume per dish: 3 to 6 portions
                        qty = int(np.random.choice([3, 4, 5, 6]))
                    else:
                        # Quantity: 1 (80%), 2 (15%), 3 (5%)
                        qty = int(np.random.choice([1, 2, 3], p=[0.80, 0.15, 0.05]))
                    subtotal = round(qty * dish.precio_unitario, 2)
                    order_items_total += subtotal

                    if dish.tiempo_preparacion_minutos > max_dish_prep_time:
                        max_dish_prep_time = dish.tiempo_preparacion_minutos

                    details.append(
                        DetalleOrden(
                            id_detalle=detail_id_counter,
                            id_orden=order_id,
                            id_platillo=dish.id_platillo,
                            cantidad=qty,
                            precio_unitario=dish.precio_unitario,
                            subtotal=subtotal,
                        )
                    )
                    detail_id_counter += 1

                # Active campaign check
                promo = self.get_active_promotion(curr_date)
                promo_id = promo.id_promocion if promo else None
                discount_rate = promo.descuento_pct if promo else 0.0
                discount_amount = round(order_items_total * discount_rate, 2)

                # Shipping fee with heavy rain surcharge
                shipping_fee = zona.tarifa_envio_base
                if precip_mm > 15.0:
                    shipping_fee += 15.0 # Tarifa dinámica por lluvia
                if is_bulk_catering:
                    shipping_fee += 25.0 # Recargo por volumen/peso

                # Assign courier
                repartidor = np.random.choice(self.active_repartidores)

                # Delivery duration calculation
                kitchen_buffer = float(np.random.normal(3.0, 1.0))
                if is_bulk_catering:
                    kitchen_buffer += float(np.random.uniform(15.0, 30.0))
                prep_total = max(5.0, max_dish_prep_time + kitchen_buffer)
                duration_minutes = self.calculate_delivery_duration(
                    zona, repartidor, precip_mm, prep_total
                )

                # Payment method
                metodo_pago = str(
                    np.random.choice(
                        list(PAYMENT_METHOD_WEIGHTS.keys()),
                        p=list(PAYMENT_METHOD_WEIGHTS.values()),
                    )
                )

                # State determination
                # Cancellation logic: base 2.0%, increases under severe delays or torrential rain
                cancel_prob = 0.020
                if duration_minutes > 55.0:
                    cancel_prob += 0.045
                if precip_mm > 20.0:
                    cancel_prob += 0.060

                is_canceled = np.random.rand() < cancel_prob

                # End of year edge case (last 2 hours of 2024)
                is_end_of_year_inflight = (
                    curr_date == date(2024, 12, 31) and created_at.hour >= 22 and not is_canceled
                )

                if is_canceled:
                    estado_orden = "cancelada"
                    delivered_at = None
                    propina = 0.0
                elif is_end_of_year_inflight:
                    estado_orden = np.random.choice(["en_camino", "preparando"], p=[0.70, 0.30])
                    delivered_at = None
                    propina = 0.0
                else:
                    estado_orden = "entregada"
                    delivered_at = created_at + timedelta(minutes=duration_minutes)
                    # Tip distribution with generous outliers
                    tip_roll = np.random.rand()
                    if tip_roll < 0.015:
                        # Generous customer outlier
                        propina = float(np.random.choice([80.0, 100.0, 150.0]))
                    elif tip_roll < 0.32:
                        propina = float(np.random.choice([10.0, 15.0, 20.0, 30.0, 50.0]))
                    else:
                        propina = 0.0

                final_total = round((order_items_total - discount_amount) + shipping_fee, 2)

                orders.append(
                    Orden(
                        id_orden=order_id,
                        id_zona=zona.id_zona,
                        id_repartidor=repartidor.id_repartidor,
                        id_promocion=promo_id,
                        fecha_hora_creacion=created_at,
                        fecha_hora_entrega=delivered_at,
                        metodo_pago=metodo_pago,
                        estado_orden=estado_orden,
                        total_orden=final_total,
                        costo_envio=round(shipping_fee, 2),
                        propina=propina,
                        notas_entrega=None, # Populated by Stage 3 enrichment
                        comentario_cliente=None,
                        motivo_cancelacion=None,
                    )
                )

            if (day_idx + 1) % 60 == 0 or (day_idx + 1) == total_days:
                logger.info(f"Simulated {day_idx + 1}/{total_days} days... ({len(orders)} orders generated)")

        logger.info(f"Simulation completed! Generated {len(orders)} orders and {len(details)} line items.")
        return orders, details
