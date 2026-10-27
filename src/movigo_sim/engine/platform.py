"""Platform/App Dispatcher service for MoviGo ride-hailing simulation.

Models the MoviGo application layer:
- Microeconomic excess demand equation solver for dynamic surge pricing (m*).
- Candidate search and greedy/noisy dispatch matching.
- Payment method Chi-Square coupling with socioeconomic stratum.
- Micro-behavioral logistic cancellation model with structured semantic reasons.
- Fare computation and rating/tipping distributions.
"""

from __future__ import annotations

import math
from datetime import datetime, date, time
from typing import Any
import numpy as np

from movigo_sim.config import (
    BASE_PER_KM_NIO,
    BASE_PER_MINUTE_NIO,
    SURGE_MAX,
    OUTLIER_MOBILITY_SHOCK_PROB,
    SERVICE_CATEGORIES,
    SERVICE_FARE_FACTORS,
)
from movigo_sim.models import UrbanZone, IncentiveCampaign
from movigo_sim.engine.entities import DriverAgent
from movigo_sim.engine.world import WorldEnvironment, get_gravity_regime_name, haversine_km

# Multinomial Logit Alternative-Specific Constants (reference: movigo_estandar = 0.0)
MODE_CHOICE_ASC: dict[str, float] = {
    "movigo_moto": 0.45,       # Baseline appeal in dry weather (quick, cheap)
    "movigo_estandar": 0.00,   # Reference base alternative
    "movigo_comfort": -0.65,   # Premium baseline barrier
}

# Price sensitivity beta by stratum for Multinomial Logit
STRATUM_COST_BETA: dict[str, float] = {
    "popular":   -0.038,  # Highly sensitive to price
    "medio":     -0.024,
    "comercial": -0.018,
    "alto":      -0.009,  # Low sensitivity to price
}

# Weather (Rain mm) sensitivity beta by service modality
MODE_WEATHER_BETA: dict[str, float] = {
    "movigo_moto":    -0.95,  # Extreme penalty for rain on motorbikes (soaked/slip hazards)
    "movigo_estandar": 0.12,  # Positive preference for enclosed cabin
    "movigo_comfort":  0.32,  # High preference for safe, elevated SUVs during storms
}

# Wait time (ETA) sensitivity beta
WAIT_TIME_BETA: float = -0.06

# Chi-Square Conditional Probability Matrix: P(Payment Method | Socioeconomic Stratum)
STRATUM_PAYMENT_PROBABILITIES: dict[str, list[float]] = {
    "alto":      [0.10, 0.65, 0.25], # High stratum: heavily credit/debit card
    "medio":     [0.30, 0.42, 0.28], # Middle stratum: balanced
    "comercial": [0.20, 0.48, 0.32], # Commercial hubs & universities: cards & wallets
    "popular":   [0.75, 0.10, 0.15], # Traditional markets: predominantly cash
}

PAYMENT_METHODS = ["efectivo", "tarjeta", "billetera_digital"]

# Stratum price-sensitivity coefficients for logistic cancellation model
STRATUM_SURGE_BETA: dict[str, float] = {
    "popular":   2.10,
    "medio":     1.25,
    "comercial": 1.00,
    "alto":      0.45,
}

# Hourly arrival curve for Managua urban traffic (24 hours)
HOURLY_TRIP_WEIGHTS = np.array([
    0.015, 0.008, 0.005, 0.004, 0.008, 0.025, # 00:00 - 05:59 (Night)
    0.065, 0.115, 0.085, 0.055, 0.045, 0.055, # 06:00 - 11:59 (Morning peak 7-9am)
    0.080, 0.065, 0.045, 0.040, 0.055, 0.095, # 12:00 - 17:59 (Lunch & mid-afternoon)
    0.110, 0.085, 0.055, 0.040, 0.028, 0.020  # 18:00 - 23:59 (Evening rush & night close)
])
HOURLY_TRIP_WEIGHTS /= HOURLY_TRIP_WEIGHTS.sum()


class MoviGoPlatform:
    """Manages matching, pricing, incentive campaigns, and payment clearing."""

    def __init__(
        self,
        campaigns: list[IncentiveCampaign],
        templates: dict[str, Any],
    ):
        self.campaigns = campaigns
        self.templates = templates

    def calculate_daily_demand(
        self, precip_mm: float, dow: int, rng: np.random.Generator
    ) -> int:
        """Daily ride requests driven by rain and day-of-week with realistic noise and mobility shocks."""
        dow_adj = 30.0 if dow in [4, 5] else (0.0 if dow in [0, 1, 2, 3] else -15.0)
        rain_adj = 5.2 * precip_mm
        noise_std = 12.0 + (0.65 * precip_mm)
        noise = float(rng.normal(0, noise_std))

        total_rides = 175.0 + rain_adj + dow_adj + noise

        shock_roll = float(rng.random())
        if shock_roll < (OUTLIER_MOBILITY_SHOCK_PROB * 0.60):
            total_rides *= float(rng.uniform(1.35, 1.65))
        elif shock_roll < OUTLIER_MOBILITY_SHOCK_PROB:
            total_rides *= float(rng.uniform(0.50, 0.68))

        return max(60, int(round(total_rides)))

    def sample_trip_time(self, curr_date: date, rng: np.random.Generator) -> datetime:
        """Sample request timestamp via Non-Homogeneous Poisson Process (NHPP)."""
        hour = int(rng.choice(24, p=HOURLY_TRIP_WEIGHTS))
        minute = int(rng.integers(0, 60))
        second = int(rng.integers(0, 60))
        return datetime.combine(curr_date, time(hour, minute, second))

    def simulate_supply_demand_and_surge(
        self,
        origin_zone: UrbanZone,
        hourly_precip_mm: float,
        runoff_mm: float,
        flooded_roads: bool,
        hour: int,
        dow: int,
        world: WorldEnvironment,
        rng: np.random.Generator,
        curr_date: date | None = None,
    ) -> tuple[int, int, float]:
        """Simulate origin zone active demand (Dt), available drivers (St), and equilibrium surge multiplier m*."""
        hour_weight = HOURLY_TRIP_WEIGHTS[hour] / HOURLY_TRIP_WEIGHTS.mean()
        stratum_demand_factor = {
            "comercial": 1.30,
            "popular": 1.20,
            "medio": 1.00,
            "alto": 0.90,
        }.get(origin_zone.socioeconomic_stratum, 1.0)

        regime = get_gravity_regime_name(hour, dow)
        gravity_push = world.regime_origin_push_factor[regime].get(origin_zone.zone_id, 1.0)
        zone_demand_factor = 0.65 * stratum_demand_factor + 0.35 * gravity_push

        weekend_boost = 1.15 if dow in [4, 5] else 1.00
        effective_water_mm = max(hourly_precip_mm, 0.75 * runoff_mm)

        expected_d = (14.0 * hour_weight * zone_demand_factor * weekend_boost) + (1.45 * effective_water_mm)
        if flooded_roads:
            expected_d *= 1.22
        d_t = max(2, int(round(rng.normal(expected_d, max(1.8, 0.12 * expected_d)))))

        rain_supply_penalty = max(0.45, 1.0 - 0.032 * effective_water_mm - (0.18 if flooded_roads else 0.0))
        peak_supply_factor = 0.82 if hour in [7, 8, 17, 18] else (0.90 if hour in [12, 13, 19] else 1.12)
        campaign_supply_boost = 1.0
        if curr_date is not None:
            for camp in self.campaigns:
                if camp.start_date <= curr_date <= camp.end_date:
                    hours_factor = camp.online_hours_increase / 1000.0
                    if camp.target_zone_id == origin_zone.zone_id:
                        campaign_supply_boost += 0.14 * hours_factor
                    elif camp.incentive_type == "hora_pico_lluvia" and effective_water_mm >= 1.0:
                        campaign_supply_boost += 0.12 * hours_factor
                    else:
                        campaign_supply_boost += 0.04 * hours_factor
        expected_s = (
            13.5 * hour_weight * zone_demand_factor * peak_supply_factor * rain_supply_penalty * campaign_supply_boost
        ) + 2.0
        s_t = max(1, int(round(rng.normal(expected_s, max(1.5, 0.10 * expected_s)))))

        if d_t <= s_t and effective_water_mm < 0.5 and hour not in [7, 8, 17, 18]:
            base_m = 1.00 + max(0.0, float(rng.normal(0.0, 0.03)))
        else:
            m = float(np.clip((d_t / max(1.0, float(s_t))) ** 0.65, 1.01, SURGE_MAX))
            alpha = 0.65
            gamma = 0.85
            for _ in range(4):
                f_val = d_t * math.exp(-alpha * (m - 1.0)) - s_t * (1.0 + gamma * math.log(m))
                df_val = -alpha * d_t * math.exp(-alpha * (m - 1.0)) - (s_t * gamma / m)
                if abs(df_val) > 1e-6:
                    m = float(np.clip(m - f_val / df_val, 1.00, SURGE_MAX))
            rain_boost = 0.045 * effective_water_mm + (0.18 if flooded_roads else 0.0)
            rush_boost = 0.12 if hour in [7, 8, 17, 18] else (0.06 if hour in [12, 13, 19] else 0.0)
            base_m = m + rain_boost + rush_boost + float(rng.normal(0.0, 0.04))

        if (flooded_roads or effective_water_mm > 8.0) and hour in [7, 8, 17, 18] and rng.random() < 0.22:
            multiplier = float(rng.uniform(2.60, 3.20))
        else:
            multiplier = float(np.clip(base_m, 1.00, SURGE_MAX))

        return d_t, s_t, round(multiplier, 2)

    def simulate_category_surge_multipliers(
        self,
        origin_zone: UrbanZone,
        hourly_precip_mm: float,
        runoff_mm: float,
        flooded_roads: bool,
        hour: int,
        dow: int,
        world: WorldEnvironment,
        rng: np.random.Generator,
        curr_date: date | None = None,
    ) -> dict[str, tuple[int, int, float]]:
        """Simulate demand (Dt), supply (St), and equilibrium surge (m*) independently for each vehicle category."""
        base_d, base_s, base_m = self.simulate_supply_demand_and_surge(
            origin_zone, hourly_precip_mm, runoff_mm, flooded_roads, hour, dow, world, rng, curr_date
        )

        effective_water = max(hourly_precip_mm, runoff_mm)
        category_results: dict[str, tuple[int, int, float]] = {}

        for st in SERVICE_CATEGORIES:
            if st == "movigo_moto":
                # Rain destroys moto demand and causes moto drivers to log off or refuse service
                if effective_water >= 5.0 or flooded_roads:
                    d_cat = max(1, int(round(base_d * 0.02)))
                    s_cat = max(1, int(round(base_s * 0.18 * 0.20)))
                    m_cat = 1.00
                elif effective_water >= 1.0:
                    d_cat = max(1, int(round(base_d * 0.12)))
                    s_cat = max(1, int(round(base_s * 0.18 * 0.50)))
                    m_cat = round(float(np.clip(1.00 + rng.normal(0.0, 0.02), 1.00, 1.15)), 2)
                else:
                    # Dry weather: popular sectors have very high moto preference
                    pop_boost = 1.35 if origin_zone.socioeconomic_stratum == "popular" else 1.00
                    d_cat = max(1, int(round(base_d * 0.32 * pop_boost)))
                    s_cat = max(1, int(round(base_s * 0.18)))
                    m_cat = round(float(np.clip((d_cat / max(1.0, float(s_cat))) ** 0.55, 1.00, 2.20)), 2)

            elif st == "movigo_comfort":
                # High-income / commercial zones have baseline comfort demand; rain triggers severe surge
                stratum_factor = 1.65 if origin_zone.socioeconomic_stratum == "alto" else (
                    1.20 if origin_zone.socioeconomic_stratum == "comercial" else 0.60
                )
                if effective_water >= 5.0 or flooded_roads:
                    # In downpours, affluent riders seek safe elevated SUVs
                    d_cat = max(1, int(round(base_d * 0.32 * stratum_factor * 1.50)))
                    s_cat = max(1, int(round(base_s * 0.24)))
                    m_cat = round(float(np.clip(base_m * 1.25 + rng.normal(0.05, 0.03), 1.20, SURGE_MAX)), 2)
                else:
                    d_cat = max(1, int(round(base_d * 0.18 * stratum_factor)))
                    s_cat = max(1, int(round(base_s * 0.24)))
                    m_cat = round(float(np.clip(base_m * 0.95 + rng.normal(0.0, 0.02), 1.00, SURGE_MAX)), 2)

            else:  # movigo_estandar
                # Standard car captures bulk of displacement from moto during rain
                if effective_water >= 5.0 or flooded_roads:
                    d_cat = max(1, int(round(base_d * 0.66 * 1.30)))
                    s_cat = max(1, int(round(base_s * 0.58)))
                    m_cat = round(float(np.clip(base_m * 1.12, 1.10, SURGE_MAX)), 2)
                else:
                    d_cat = max(1, int(round(base_d * 0.50)))
                    s_cat = max(1, int(round(base_s * 0.58)))
                    m_cat = round(float(np.clip(base_m, 1.00, SURGE_MAX)), 2)

            category_results[st] = (d_cat, s_cat, m_cat)

        return category_results

    def sample_mode_choice(
        self,
        stratum: str,
        effective_water_mm: float,
        category_fares: dict[str, float],
        category_etas: dict[str, float],
        rng: np.random.Generator,
    ) -> tuple[str, dict[str, float]]:
        """Multinomial Logit discrete vehicle category choice model for passenger agents.

        Returns:
            chosen_category: one of 'movigo_moto', 'movigo_estandar', 'movigo_comfort'
            choice_probabilities: dict mapping each category to its selection probability
        """
        beta_cost = STRATUM_COST_BETA.get(stratum, -0.024)

        v_utilities: dict[str, float] = {}
        for cat in SERVICE_CATEGORIES:
            asc = MODE_CHOICE_ASC[cat]
            fare = category_fares.get(cat, 100.0)
            eta = category_etas.get(cat, 5.0)
            w_beta = MODE_WEATHER_BETA[cat]

            # Systematic utility: V_ij = ASC_j + beta_cost * Fare_j + beta_time * ETA_j + beta_rain * Rain_mm
            v = asc + (beta_cost * fare) + (WAIT_TIME_BETA * eta) + (w_beta * effective_water_mm)
            v_utilities[cat] = v

        # Softmax with numerical stability
        max_v = max(v_utilities.values())
        exp_v = {cat: math.exp(v - max_v) for cat, v in v_utilities.items()}
        sum_exp = sum(exp_v.values())
        probs = {cat: exp_v[cat] / sum_exp for cat in SERVICE_CATEGORIES}

        prob_list = [probs[cat] for cat in SERVICE_CATEGORIES]
        chosen_cat = str(rng.choice(SERVICE_CATEGORIES, p=prob_list))
        return chosen_cat, probs

    def sample_payment_method_for_stratum(
        self,
        stratum: str,
        preferred_method: str | None,
        rng: np.random.Generator,
        user_weight: float = 0.75,
    ) -> str:
        """Sample payment method coupling user preference with origin zone stratum (Chi-Square guarantee)."""
        stratum_probs = np.array(
            STRATUM_PAYMENT_PROBABILITIES.get(stratum, [0.40, 0.35, 0.25]),
            dtype=float,
        )
        if preferred_method is not None and preferred_method in PAYMENT_METHODS:
            pref_idx = PAYMENT_METHODS.index(preferred_method)
            probs = (1.0 - user_weight) * stratum_probs
            probs[pref_idx] += user_weight
            probs /= probs.sum()
        else:
            probs = stratum_probs
        return str(rng.choice(PAYMENT_METHODS, p=probs))

    def compute_fare(
        self,
        flag_drop_fare: float,
        distance_km: float,
        duration_min: float,
        surge_multiplier: float,
        service_type: str = "movigo_estandar",
    ) -> tuple[float, float]:
        """Compute base fare and final fare incorporating service category factor."""
        factor = SERVICE_FARE_FACTORS.get(service_type, 1.00)
        distance_charge = round(distance_km * BASE_PER_KM_NIO, 2)
        time_charge = round(duration_min * BASE_PER_MINUTE_NIO, 2)
        raw_base = flag_drop_fare + distance_charge + time_charge
        base_fare = round(raw_base * factor, 2)
        final_fare = round(base_fare * surge_multiplier, 2)
        return base_fare, final_fare

    def dispatch_driver(
        self,
        free_drivers: list[DriverAgent],
        all_operational_drivers: list[DriverAgent],
        lat_o: float,
        lon_o: float,
        req_time: datetime,
        world: WorldEnvironment,
        rng: np.random.Generator,
        service_type: str = "movigo_estandar",
    ) -> tuple[DriverAgent, float]:
        """Match request with on-duty company driver prioritizing the requested vehicle category."""
        # 1. Filter dispatchable free drivers operating the requested category
        matching_free = [
            d for d in free_drivers
            if d.is_dispatchable(req_time) and d.vehicle_model.service_type == service_type
        ]

        # 2. If no free driver of that category is available, fall back to any dispatchable free driver
        if not matching_free:
            matching_free = [d for d in free_drivers if d.is_dispatchable(req_time)]

        # 3. If free drivers exist, dispatch closest via proximity
        if matching_free:
            proximity_w = []
            for d in matching_free:
                d_pos = world.node_coords[d.current_node]
                d_hav = haversine_km(d_pos[0], d_pos[1], lat_o, lon_o)
                # Proximity score with central corporate dispatch compliance (96% company policy compliance)
                score = (1.0 / max(0.35, d_hav)) ** 1.35
                compliance = 0.96 * (d.acceptance_rate_pct / 100.0)
                proximity_w.append(score * compliance)
            proximity_w_arr = np.array(proximity_w, dtype=float)
            proximity_w_arr /= proximity_w_arr.sum()
            chosen_local_idx = int(rng.choice(len(matching_free), p=proximity_w_arr))
            driver = matching_free[chosen_local_idx]
            extra_wait = 0.0
        else:
            # 4. If no free driver is available, queue with earliest finishing on-duty driver
            on_duty_drivers = [d for d in all_operational_drivers if d.is_on_duty(req_time)]
            pool = on_duty_drivers if on_duty_drivers else all_operational_drivers
            driver = min(pool, key=lambda d: d.available_at)
            extra_wait = max(0.0, (driver.available_at - req_time).total_seconds() / 60.0)

        return driver, extra_wait

    def evaluate_cancellation(
        self,
        stratum: str,
        payment_method: str,
        surge: float,
        final_fare: float,
        wait_min: float,
        effective_water_mm: float,
        flood_affected: bool,
        congestion_idx: float,
        hour: int,
        rng: np.random.Generator,
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate trip cancellation via micro-behavioral logistic model and assign structured reason."""
        beta_surge = STRATUM_SURGE_BETA.get(stratum, 1.15)
        surge_term = beta_surge * (surge - 1.0)

        cash_term = 0.0
        if payment_method == "efectivo":
            if final_fare > 500.0:
                cash_term = 2.15
            elif final_fare > 200.0:
                cash_term = 1.10

        delay_term = 0.0
        if wait_min > 10.0:
            delay_term = 0.24 * (math.exp(0.22 * min(wait_min - 10.0, 10.0)) - 1.0)

        peak_term = 0.55 if hour in [7, 8, 17, 18] else 0.0
        flood_term = 0.95 if flood_affected else (0.35 if effective_water_mm > 4.0 else (0.18 if congestion_idx > 2.2 else 0.0))

        logit = -3.88 + surge_term + cash_term + delay_term + peak_term + flood_term
        cancel_prob = float(np.clip(1.0 / (1.0 + math.exp(-logit)), 0.015, 0.72))

        if rng.random() >= cancel_prob:
            return False, None, None

        if flood_affected or (effective_water_mm > 3.5 and rng.random() < 0.55):
            return True, "cancelado_conductor", "Vía anegada / cauce intransitable"

        if (cash_term > 0.0 or surge >= 1.35) and rng.random() < 0.58:
            return True, "cancelado_usuario", "Tarifa dinámica sobrepasa presupuesto"

        if wait_min > 10.0:
            if rng.random() < 0.62:
                return True, "cancelado_usuario", "Tiempo de llegada excesivo"
            return True, "cancelado_usuario", "Conductor no avanza"

        if congestion_idx > 2.0 and rng.random() < 0.55:
            if rng.random() < 0.65:
                return True, "cancelado_usuario", "Conductor no avanza"
            return True, "cancelado_usuario", "Tiempo de llegada excesivo"

        roll = float(rng.random())
        if roll < 0.40:
            return True, "cancelado_usuario", "Tarifa dinámica sobrepasa presupuesto"
        elif roll < 0.72:
            return True, "cancelado_usuario", "Tiempo de llegada excesivo"
        elif roll < 0.88:
            return True, "cancelado_usuario", "Conductor no avanza"
        else:
            reason = "Vía anegada / cauce intransitable" if effective_water_mm > 1.5 else "Falla mecánica / imprevisto del conductor"
            return True, "cancelado_conductor", reason

    def sample_ratings(self, rng: np.random.Generator) -> tuple[float, float]:
        """Sample passenger rating and driver rating."""
        rating_usr = float(rng.choice([5.0, 4.0, 3.0, 2.0, 1.0], p=[0.67, 0.20, 0.06, 0.04, 0.03]))
        rating_drv = float(rng.choice([5.0, 4.0, 3.0, 2.0, 1.0], p=[0.75, 0.14, 0.05, 0.03, 0.03]))
        return rating_usr, rating_drv

    def sample_tip(self, rng: np.random.Generator) -> float:
        """Sample discretionary passenger tip."""
        tip_roll = float(rng.random())
        if tip_roll < 0.015:
            return float(rng.choice([80.0, 100.0, 150.0]))
        elif tip_roll < 0.28:
            return float(rng.choice([20.0, 30.0, 50.0], p=[0.60, 0.30, 0.10]))
        return 0.0
