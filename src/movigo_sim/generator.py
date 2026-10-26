"""Numerical and operational simulation engine for MoviGo ride-hailing app in Managua.

Generates realistic urban mobility facts with strict mathematical guarantees:
- Street-snapped Origin, Destination, and Telemetry GPS coordinates from OpenStreetMap ways
- Physical route consistency (Haversine * circuity factor) with suboptimal detours for Optimization
- Micro-behavioral logistic cancellation model (stratum surge sensitivity, cash threshold C$200/C$500, dispatch wait > 10m)
- Structured categorical cancellation reasons for contingency analysis
- Transparent parametric pricing breakdown (tarifa_bajada_bandera, cargo_distancia, cargo_tiempo, tarifa_base, multiplicador_dinamico, tarifa_final)
- Supply & Demand snapshot at request time (solicitudes_activas_origen, conductores_disponibles_origen) coupled to f(m) = D(m) - S(m) = 0
- Multi-point GPS breadcrumb trajectories in telemetria_conductores linked via id_viaje
"""

import json
import logging
import math
from datetime import datetime, date, timedelta, time
from typing import Any
import numpy as np
import pandas as pd

from movigo_sim.config import (
    SEEDS_DIR,
    BASE_PER_KM_NIO,
    BASE_PER_MINUTE_NIO,
    SURGE_RAIN_FACTOR,
    SURGE_MAX,
    OUTLIER_MOBILITY_SHOCK_PROB,
    OUTLIER_AIRPORT_TRIP_PROB,
    OUTLIER_GRIDLOCK_DELAY_PROB,
)
from movigo_sim.models import (
    ZonaUrbana,
    Usuario,
    Conductor,
    Viaje,
    TelemetriaConductor,
    CampanaIncentivo,
)

logger = logging.getLogger(__name__)

# Chi-Square Conditional Probability Matrix: P(Payment Method | Socioeconomic Stratum)
# Order: ['efectivo', 'tarjeta', 'billetera_digital']
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
# Peaks: Morning rush (07:00-08:30), Lunch (12:00-13:30), Evening rush (17:00-19:30), Friday/Saturday nightlife
HOURLY_TRIP_WEIGHTS = np.array([
    0.015, 0.008, 0.005, 0.004, 0.008, 0.025, # 00:00 - 05:59 (Night)
    0.065, 0.115, 0.085, 0.055, 0.045, 0.055, # 06:00 - 11:59 (Morning peak 7-9am)
    0.080, 0.065, 0.045, 0.040, 0.055, 0.095, # 12:00 - 17:59 (Lunch & mid-afternoon)
    0.110, 0.085, 0.055, 0.040, 0.028, 0.020  # 18:00 - 23:59 (Evening rush & night close)
])
HOURLY_TRIP_WEIGHTS /= HOURLY_TRIP_WEIGHTS.sum()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two WGS84 coordinates."""
    r_earth = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    return 2.0 * r_earth * math.asin(min(1.0, math.sqrt(a)))


def load_movigo_seed_catalogs() -> tuple[
    list[ZonaUrbana],
    list[Usuario],
    list[Conductor],
    list[CampanaIncentivo],
    dict[str, Any],
]:
    """Load dimensional seed catalogs from JSON fixtures."""
    with open(SEEDS_DIR / "zonas_urbanas.json", encoding="utf-8") as f:
        zonas = [ZonaUrbana(**z) for z in json.load(f)]

    with open(SEEDS_DIR / "usuarios.json", encoding="utf-8") as f:
        usuarios = [Usuario(**u) for u in json.load(f)]

    with open(SEEDS_DIR / "conductores.json", encoding="utf-8") as f:
        conductores = [Conductor(**c) for c in json.load(f)]

    with open(SEEDS_DIR / "campanas_incentivos.json", encoding="utf-8") as f:
        campanas = [CampanaIncentivo(**cmp) for cmp in json.load(f)]

    with open(SEEDS_DIR / "semantic_templates.json", encoding="utf-8") as f:
        templates = json.load(f)

    return zonas, usuarios, conductores, campanas, templates


def load_managua_street_network() -> dict[str, Any]:
    """Load cached OpenStreetMap drivable street segments for Managua zones."""
    network_path = SEEDS_DIR / "managua_street_network.json"
    if network_path.exists():
        with open(network_path, encoding="utf-8") as f:
            return json.load(f)
    return {"zones": {}, "arterials": []}


class MoviGoSimulationEngine:
    """Core numerical simulation engine for MoviGo ride-hailing facts."""

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)

        (
            self.zonas,
            self.usuarios,
            self.conductores,
            self.campanas,
            self.templates,
        ) = load_movigo_seed_catalogs()

        self.street_network = load_managua_street_network()
        self.zone_streets: dict[int, np.ndarray] = {}
        for z in self.zonas:
            segs = self.street_network.get("zones", {}).get(str(z.id_zona), [])
            if segs:
                self.zone_streets[z.id_zona] = np.array(segs, dtype=float)
            else:
                self.zone_streets[z.id_zona] = np.empty((0, 4), dtype=float)

        arterials = self.street_network.get("arterials", [])
        self.arterial_segments = np.array(arterials, dtype=float) if arterials else np.empty((0, 4), dtype=float)
        if len(self.arterial_segments) > 0:
            self.arterial_mid_lats = 0.5 * (self.arterial_segments[:, 0] + self.arterial_segments[:, 2])
            self.arterial_mid_lons = 0.5 * (self.arterial_segments[:, 1] + self.arterial_segments[:, 3])
        else:
            self.arterial_mid_lats = np.empty(0, dtype=float)
            self.arterial_mid_lons = np.empty(0, dtype=float)

        self.zonas_map = {z.id_zona: z for z in self.zonas}
        self.conductores_map = {c.id_conductor: c for c in self.conductores}
        self.active_conductores = [c for c in self.conductores if c.estado == "activo"]

    @property
    def semantic_templates(self):
        """Backward-compatible alias for templates."""
        return self.templates

    def sample_street_coordinate(self, zona: ZonaUrbana) -> tuple[float, float]:
        """Sample a GPS coordinate strictly on a drivable street within the urban zone's radius."""
        segs = self.zone_streets.get(zona.id_zona)
        if segs is not None and len(segs) > 0:
            idx = int(np.random.randint(0, len(segs)))
            lat1, lon1, lat2, lon2 = segs[idx]
            t = float(np.random.uniform(0.0, 1.0))
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            return round(float(np.clip(lat, 12.00, 12.30)), 6), round(float(np.clip(lon, -86.45, -86.10)), 6)

        # Fallback: polar sampling within operational radius
        r_km = float(np.random.uniform(0.05, zona.radio_cobertura_km * 0.85))
        theta = float(np.random.uniform(0.0, 2.0 * math.pi))
        r_deg = r_km / 111.0
        lat = zona.latitud + r_deg * math.cos(theta)
        lon = zona.longitud + (r_deg * math.sin(theta)) / math.cos(math.radians(zona.latitud))
        return round(float(np.clip(lat, 12.00, 12.30)), 6), round(float(np.clip(lon, -86.45, -86.10)), 6)

    def snap_to_nearest_street(self, target_lat: float, target_lon: float, fallback_zona: ZonaUrbana) -> tuple[float, float]:
        """Snap an arbitrary waypoint coordinate onto the nearest real OpenStreetMap street segment."""
        if len(self.arterial_segments) > 0:
            d2 = (self.arterial_mid_lats - target_lat) ** 2 + (self.arterial_mid_lons - target_lon) ** 2
            # Pick among the closest street segments
            nearest_idx = int(np.argmin(d2))
            lat1, lon1, lat2, lon2 = self.arterial_segments[nearest_idx]
            t = float(np.random.uniform(0.15, 0.85))
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            return round(float(np.clip(lat, 12.00, 12.30)), 6), round(float(np.clip(lon, -86.45, -86.10)), 6)
        return self.sample_street_coordinate(fallback_zona)

    def find_closest_zone_id(self, lat: float, lon: float) -> int:
        """Return the id_zona of the urban zone closest to (lat, lon)."""
        best_id = self.zonas[0].id_zona
        best_d2 = float("inf")
        for z in self.zonas:
            d2 = (z.latitud - lat) ** 2 + (z.longitud - lon) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_id = z.id_zona
        return best_id

    def calculate_daily_demand(self, precip_mm: float, dow: int) -> int:
        """Daily ride requests driven by rain and day-of-week in Managua with realistic noise and mobility shocks."""
        dow_adj = 30.0 if dow in [4, 5] else (0.0 if dow in [0, 1, 2, 3] else -15.0)
        rain_adj = 5.2 * precip_mm
        noise_std = 12.0 + (0.65 * precip_mm)
        noise = np.random.normal(0, noise_std)

        total_rides = 175.0 + rain_adj + dow_adj + noise

        shock_roll = np.random.rand()
        if shock_roll < (OUTLIER_MOBILITY_SHOCK_PROB * 0.60):
            total_rides *= float(np.random.uniform(1.35, 1.65))
        elif shock_roll < OUTLIER_MOBILITY_SHOCK_PROB:
            total_rides *= float(np.random.uniform(0.50, 0.68))

        return max(60, int(round(total_rides)))

    def sample_trip_time(self, curr_date: date) -> datetime:
        """Sample request timestamp via NHPP."""
        hour = int(np.random.choice(24, p=HOURLY_TRIP_WEIGHTS))
        minute = int(np.random.randint(0, 60))
        second = int(np.random.randint(0, 60))
        return datetime.combine(curr_date, time(hour, minute, second))

    def simulate_supply_demand_and_surge(
        self,
        zona_origen: ZonaUrbana,
        precip_mm: float,
        hour: int,
        dow: int,
    ) -> tuple[int, int, float]:
        """Simulate origin zone active demand (Dt), available drivers (St), and equilibrium surge multiplier m*.

        Couples Dt and St to the excess demand equation:
            f(m) = Dt * exp(-alpha * (m - 1)) - St * (1 + gamma * ln(m)) = 0
        """
        hour_weight = HOURLY_TRIP_WEIGHTS[hour] / HOURLY_TRIP_WEIGHTS.mean()
        stratum_demand_factor = {
            "comercial": 1.30,
            "popular": 1.20,
            "medio": 1.00,
            "alto": 0.90,
        }.get(zona_origen.estrato_socioeconomico, 1.0)

        weekend_boost = 1.15 if dow in [4, 5] else 1.00

        # Active trip requests in origin zone during that hour (Dt)
        expected_d = (14.0 * hour_weight * stratum_demand_factor * weekend_boost) + (0.55 * precip_mm)
        d_t = max(2, int(round(np.random.normal(expected_d, max(1.8, 0.12 * expected_d)))))

        # Available driver supply in origin zone during that hour (St)
        # Drivers log off or get stuck during torrential rain, tightening supply relative to demand
        rain_supply_penalty = max(0.52, 1.0 - 0.014 * precip_mm)
        peak_supply_factor = 0.82 if hour in [7, 8, 17, 18] else (0.90 if hour in [12, 13, 19] else 1.12)
        expected_s = (13.5 * hour_weight * stratum_demand_factor * peak_supply_factor * rain_supply_penalty) + 2.0
        s_t = max(1, int(round(np.random.normal(expected_s, max(1.5, 0.10 * expected_s)))))

        # Solve market-clearing surge multiplier m* from excess demand ratio Dt / St
        # f(m) = Dt * exp(-0.65 * (m - 1)) - St * (1 + 0.85 * ln(m)) = 0
        # Using 3 Newton-Raphson iterations starting at m0 = max(1.0, (Dt / St) ** 0.65)
        if d_t <= s_t and precip_mm < 2.0 and hour not in [7, 8, 17, 18]:
            base_m = 1.00 + max(0.0, float(np.random.normal(0.0, 0.03)))
        else:
            m = float(np.clip((d_t / max(1.0, float(s_t))) ** 0.65, 1.01, SURGE_MAX))
            alpha = 0.65
            gamma = 0.85
            for _ in range(4):
                f_val = d_t * math.exp(-alpha * (m - 1.0)) - s_t * (1.0 + gamma * math.log(m))
                df_val = -alpha * d_t * math.exp(-alpha * (m - 1.0)) - (s_t * gamma / m)
                if abs(df_val) > 1e-6:
                    m = float(np.clip(m - f_val / df_val, 1.00, SURGE_MAX))
            # Add rain friction and micro market noise
            rain_boost = 0.50 * SURGE_RAIN_FACTOR * precip_mm
            rush_boost = 0.12 if hour in [7, 8, 17, 18] else (0.06 if hour in [12, 13, 19] else 0.0)
            base_m = m + rain_boost + rush_boost + float(np.random.normal(0.0, 0.04))

        # Extreme surge outlier event: intense storm combined with rush hour bottleneck
        if precip_mm > 18.0 and hour in [7, 8, 17, 18] and np.random.rand() < 0.15:
            multiplier = float(np.random.uniform(2.80, 3.20))
        else:
            multiplier = float(np.clip(base_m, 1.00, SURGE_MAX))

        return d_t, s_t, round(multiplier, 2)

    def calculate_surge_multiplier(self, precip_mm: float, hour: int) -> float:
        """Backward-compatible helper to calculate dynamic surge multiplier."""
        _, _, m = self.simulate_supply_demand_and_surge(self.zonas[0], precip_mm, hour, 2)
        return m

    def sample_payment_method_for_stratum(self, stratum: str) -> str:
        """Sample payment method conditioned on origin zone stratum (Chi-Square guarantee)."""
        probs = STRATUM_PAYMENT_PROBABILITIES.get(stratum, [0.40, 0.35, 0.25])
        return str(np.random.choice(PAYMENT_METHODS, p=probs))

    def estimate_distance_and_duration(
        self,
        lat_o: float,
        lon_o: float,
        lat_d: float,
        lon_d: float,
        congestion_idx: float,
        precip_mm: float = 0.0,
    ) -> tuple[float, float, bool]:
        """Calculate road distance and duration from exact GPS coordinates with realistic suboptimal detours.

        Returns:
            (distancia_km, duracion_minutos, is_suboptimal_detour)
        """
        hav_km = haversine_km(lat_o, lon_o, lat_d, lon_d)

        # ~18% of trips exhibit suboptimal routing (detours around roundabouts / non-optimal street choice)
        # so students can identify and optimize inefficient trajectories
        is_suboptimal = bool(np.random.rand() < 0.18)
        if is_suboptimal:
            circuity_factor = float(np.random.uniform(1.52, 1.92))
        else:
            # Standard road network circuity ~ 1.30x Haversine
            circuity_factor = float(np.random.normal(1.30, 0.03))
            circuity_factor = float(np.clip(circuity_factor, 1.24, 1.38))

        dist_km = round(max(0.65, hav_km * circuity_factor), 2)

        # Realistic urban speed in Managua: ~29 km/h clear, penalized by traffic congestion and rainfall
        rain_speed_penalty = 1.0 + 0.012 * precip_mm
        effective_speed_kmh = max(9.5, 30.0 / (congestion_idx * rain_speed_penalty))
        duration_min = round(
            max(2.5, (dist_km / effective_speed_kmh) * 60.0 + float(np.random.uniform(1.0, 3.5))),
            2,
        )

        # Urban mobility outliers (~2.5% of trips):
        roll = np.random.rand()
        if roll < OUTLIER_AIRPORT_TRIP_PROB:
            # Suburban/Airport corridor extension
            dist_km = round(max(dist_km, float(np.random.uniform(18.0, 32.0))), 2)
            duration_min = round(float(dist_km * np.random.uniform(1.6, 2.2) + np.random.uniform(8.0, 18.0)), 2)
            is_suboptimal = True
        elif roll < (OUTLIER_AIRPORT_TRIP_PROB + OUTLIER_GRIDLOCK_DELAY_PROB):
            # Severe traffic bottleneck / flooded cauce roadblock (+30 to +55 min delay)
            duration_min = round(float(duration_min + np.random.uniform(30.0, 55.0)), 2)

        return dist_km, duration_min, is_suboptimal

    def evaluate_cancellation(
        self,
        stratum: str,
        metodo_pago: str,
        surge: float,
        tarifa_final: float,
        wait_min: float,
        precip_mm: float,
        congestion_idx: float,
        hour: int,
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate trip cancellation via micro-behavioral logistic model and assign structured reason.

        Conditioned on:
        1. Surge Multiplier (m) with steeper sensitivity for 'popular' vs 'alto' stratum
        2. Payment Method ('efectivo') crossing typical cash denomination thresholds (C$200 and C$500)
        3. Dispatch Delay (tiempo_espera_minutos > 10 min exponential risk increase)
        4. Storm / flooded cauce conditions and peak-hour gridlock
        """
        beta_surge = STRATUM_SURGE_BETA.get(stratum, 1.15)
        surge_term = beta_surge * (surge - 1.0)

        # Cash denomination threshold effect (C$ 200 and C$ 500 bills)
        cash_term = 0.0
        if metodo_pago == "efectivo":
            if tarifa_final > 500.0:
                cash_term = 2.15
            elif tarifa_final > 200.0:
                cash_term = 1.10

        # Exponential dispatch delay penalty above 10 minutes
        delay_term = 0.0
        if wait_min > 10.0:
            delay_term = 0.24 * (math.exp(0.22 * min(wait_min - 10.0, 10.0)) - 1.0)

        # Peak hour and storm friction (preserves H2 hypothesis test: peak > off-peak cancellation)
        peak_term = 0.55 if hour in [7, 8, 17, 18] else 0.0
        storm_term = 0.45 if precip_mm > 15.0 else (0.20 if congestion_idx > 2.2 else 0.0)

        # Baseline logit ~ -3.85 (~2.1% base cancellation in calm, base-fare, fast-pickup conditions)
        logit = -3.85 + surge_term + cash_term + delay_term + peak_term + storm_term
        cancel_prob = 1.0 / (1.0 + math.exp(-logit))
        cancel_prob = float(np.clip(cancel_prob, 0.015, 0.65))

        if np.random.rand() >= cancel_prob:
            return False, None, None

        # Determine structured cancellation reason based on dominant trigger
        if precip_mm > 12.0 and np.random.rand() < 0.48:
            return True, "cancelado_conductor", "Vía anegada / cauce intransitable"

        if (cash_term > 0.0 or surge >= 1.35) and np.random.rand() < 0.58:
            return True, "cancelado_usuario", "Tarifa dinámica sobrepasa presupuesto"

        if wait_min > 10.0:
            if np.random.rand() < 0.62:
                return True, "cancelado_usuario", "Tiempo de llegada excesivo"
            return True, "cancelado_usuario", "Conductor no avanza"

        if congestion_idx > 2.0 and np.random.rand() < 0.55:
            if np.random.rand() < 0.65:
                return True, "cancelado_usuario", "Conductor no avanza"
            return True, "cancelado_usuario", "Tiempo de llegada excesivo"

        # Remaining cancellations split between budget, impatience, and driver issues
        roll = np.random.rand()
        if roll < 0.40:
            return True, "cancelado_usuario", "Tarifa dinámica sobrepasa presupuesto"
        elif roll < 0.72:
            return True, "cancelado_usuario", "Tiempo de llegada excesivo"
        elif roll < 0.88:
            return True, "cancelado_usuario", "Conductor no avanza"
        else:
            reason = "Vía anegada / cauce intransitable" if precip_mm > 5.0 else "Falla mecánica / imprevisto del conductor"
            return True, "cancelado_conductor", reason

    def run_simulation(
        self,
        weather_df: pd.DataFrame,
    ) -> tuple[list[Viaje], list[TelemetriaConductor]]:
        """Run full year MoviGo simulation."""
        logger.info(f"Starting MoviGo simulation across {len(weather_df)} days...")

        viajes: list[Viaje] = []
        telemetria: list[TelemetriaConductor] = []
        trip_counter = 1
        telemetry_counter = 1

        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
            curr_date: date = row["fecha"]
            precip_mm: float = float(row["precipitacion_mm"])
            congestion_idx: float = float(row["indice_congestion"])
            dow: int = curr_date.weekday()

            daily_target = self.calculate_daily_demand(precip_mm, dow)

            # Sample daily trips
            for _ in range(daily_target):
                trip_id = trip_counter
                trip_counter += 1

                req_time = self.sample_trip_time(curr_date)
                hour = req_time.hour

                # Sample passenger
                user = np.random.choice(self.usuarios)

                # Sample origin and destination zones
                zona_origen = np.random.choice(self.zonas)
                dest_candidates = [z for z in self.zonas if z.id_zona != zona_origen.id_zona]
                zona_destino = np.random.choice(dest_candidates)

                # Street-snapped Origin and Destination GPS coordinates
                lat_o, lon_o = self.sample_street_coordinate(zona_origen)
                lat_d, lon_d = self.sample_street_coordinate(zona_destino)

                # Supply & Demand state at request time and equilibrium surge multiplier
                d_t, s_t, surge = self.simulate_supply_demand_and_surge(
                    zona_origen, precip_mm, hour, dow
                )

                # Payment method conditioned on stratum (Chi-Square guarantee)
                metodo_pago = self.sample_payment_method_for_stratum(zona_origen.estrato_socioeconomico)

                # Physical route distance and duration
                dist_km, dur_min, is_suboptimal = self.estimate_distance_and_duration(
                    lat_o, lon_o, lat_d, lon_d, congestion_idx, precip_mm
                )

                # Transparent Pricing Breakdown
                tarifa_bajada = round(float(zona_origen.tarifa_base_bajada_bandera), 2)
                cargo_dist = round(dist_km * BASE_PER_KM_NIO, 2)
                cargo_tpo = round(dur_min * BASE_PER_MINUTE_NIO, 2)
                tarifa_base = round(tarifa_bajada + cargo_dist + cargo_tpo, 2)
                tarifa_final = round(tarifa_base * surge, 2)

                # Dispatch wait time (scales with demand/supply ratio and traffic congestion)
                imbalance_ratio = d_t / max(1.0, float(s_t))
                base_wait = float(np.random.uniform(2.5, 6.5)) + 1.4 * max(0.0, imbalance_ratio - 0.9) + 1.1 * (congestion_idx - 1.0)
                if precip_mm > 10.0 or hour in [7, 8, 17, 18]:
                    base_wait += float(np.random.exponential(2.2))
                wait_min = round(float(np.clip(base_wait, 1.5, 24.0)), 2)

                # Assign driver
                conductor = np.random.choice(self.active_conductores)

                # Micro-behavioral cancellation evaluation
                is_canceled, cancel_state, motivo = self.evaluate_cancellation(
                    stratum=zona_origen.estrato_socioeconomico,
                    metodo_pago=metodo_pago,
                    surge=surge,
                    tarifa_final=tarifa_final,
                    wait_min=wait_min,
                    precip_mm=precip_mm,
                    congestion_idx=congestion_idx,
                    hour=hour,
                )

                if is_canceled:
                    estado_viaje = cancel_state or "cancelado_usuario"
                    start_time = None
                    end_time = None
                    rating_usr = None
                    rating_cnd = None
                    propina = 0.0
                else:
                    estado_viaje = "completado"
                    start_time = req_time + timedelta(minutes=wait_min)
                    end_time = start_time + timedelta(minutes=dur_min)
                    rating_usr = float(np.random.choice([5.0, 4.0, 3.0, 2.0, 1.0], p=[0.67, 0.20, 0.06, 0.04, 0.03]))
                    rating_cnd = float(np.random.choice([5.0, 4.0, 3.0, 2.0, 1.0], p=[0.75, 0.14, 0.05, 0.03, 0.03]))

                    tip_roll = np.random.rand()
                    if tip_roll < 0.015:
                        propina = float(np.random.choice([80.0, 100.0, 150.0]))
                    elif tip_roll < 0.28:
                        propina = float(np.random.choice([20.0, 30.0, 50.0], p=[0.60, 0.30, 0.10]))
                    else:
                        propina = 0.0

                viajes.append(
                    Viaje(
                        id_viaje=trip_id,
                        id_usuario=user.id_usuario,
                        id_conductor=conductor.id_conductor,
                        id_zona_origen=zona_origen.id_zona,
                        id_zona_destino=zona_destino.id_zona,
                        latitud_origen=lat_o,
                        longitud_origen=lon_o,
                        latitud_destino=lat_d,
                        longitud_destino=lon_d,
                        fecha_hora_solicitud=req_time,
                        fecha_hora_inicio=start_time,
                        fecha_hora_fin=end_time,
                        tiempo_espera_minutos=wait_min,
                        distancia_km=dist_km,
                        duracion_minutos=dur_min,
                        tarifa_bajada_bandera=tarifa_bajada,
                        cargo_distancia=cargo_dist,
                        cargo_tiempo=cargo_tpo,
                        tarifa_base=tarifa_base,
                        multiplicador_dinamico=surge,
                        tarifa_final=tarifa_final,
                        solicitudes_activas_origen=d_t,
                        conductores_disponibles_origen=s_t,
                        metodo_pago=metodo_pago,
                        estado_viaje=estado_viaje,
                        calificacion_usuario=rating_usr,
                        calificacion_conductor=rating_cnd,
                        propina=propina,
                        motivo_cancelacion=motivo,
                    )
                )

                # Generate street-snapped telemetry breadcrumb trail & idle pings
                # ~8% of completed trips get a full 4-point breadcrumb trail (en_camino_recogida -> ocupado x3)
                # plus ~6% of trips emit an idle 'disponible' ping (id_viaje = None)
                if not is_canceled and np.random.rand() < 0.08:
                    avg_speed_kmh = max(10.0, min(75.0, (dist_km / max(0.05, dur_min / 60.0))))
                    # Detour lateral offset if suboptimal trajectory
                    detour_lat_offset = float(np.random.choice([-0.008, 0.008])) if is_suboptimal else 0.0
                    detour_lon_offset = float(np.random.choice([-0.009, 0.009])) if is_suboptimal else 0.0

                    # 1. Dispatch approach ping (en_camino_recogida)
                    approach_lat, approach_lon = self.sample_street_coordinate(zona_origen)
                    telemetria.append(
                        TelemetriaConductor(
                            id_telemetria=telemetry_counter,
                            id_conductor=conductor.id_conductor,
                            id_viaje=trip_id,
                            id_zona=zona_origen.id_zona,
                            fecha_hora=req_time + timedelta(minutes=round(wait_min * 0.5, 2)),
                            latitud=approach_lat,
                            longitud=approach_lon,
                            velocidad_kmh=round(float(np.clip(avg_speed_kmh * np.random.uniform(0.75, 1.15), 8.0, 65.0)), 2),
                            estado_disponibilidad="en_camino_recogida",
                        )
                    )
                    telemetry_counter += 1

                    # 2-4. Three sequential in-trip waypoints ('ocupado') from origin street to destination street
                    for frac in (0.15, 0.55, 0.90):
                        raw_lat = lat_o + frac * (lat_d - lat_o) + (detour_lat_offset if frac == 0.55 else 0.0)
                        raw_lon = lon_o + frac * (lon_d - lon_o) + (detour_lon_offset if frac == 0.55 else 0.0)
                        fallback_z = zona_origen if frac < 0.5 else zona_destino
                        wp_lat, wp_lon = self.snap_to_nearest_street(raw_lat, raw_lon, fallback_z)
                        wp_zone_id = self.find_closest_zone_id(wp_lat, wp_lon)

                        speed_roll = np.random.rand()
                        if speed_roll < 0.08:
                            wp_speed = float(np.random.uniform(0.0, 5.0))
                        elif speed_roll < 0.16:
                            wp_speed = float(np.random.uniform(60.0, 76.0))
                        else:
                            wp_speed = float(np.clip(avg_speed_kmh * np.random.uniform(0.80, 1.25), 12.0, 58.0))

                        telemetria.append(
                            TelemetriaConductor(
                                id_telemetria=telemetry_counter,
                                id_conductor=conductor.id_conductor,
                                id_viaje=trip_id,
                                id_zona=wp_zone_id,
                                fecha_hora=start_time + timedelta(minutes=round(dur_min * frac, 2)),
                                latitud=wp_lat,
                                longitud=wp_lon,
                                velocidad_kmh=round(wp_speed, 2),
                                estado_disponibilidad="ocupado",
                            )
                        )
                        telemetry_counter += 1

                elif np.random.rand() < 0.06:
                    # Cruising / waiting driver ('disponible' -> id_viaje is None)
                    idle_lat, idle_lon = self.sample_street_coordinate(zona_origen)
                    telemetria.append(
                        TelemetriaConductor(
                            id_telemetria=telemetry_counter,
                            id_conductor=conductor.id_conductor,
                            id_viaje=None,
                            id_zona=zona_origen.id_zona,
                            fecha_hora=req_time,
                            latitud=idle_lat,
                            longitud=idle_lon,
                            velocidad_kmh=round(float(np.random.uniform(0.0, 22.0)), 2),
                            estado_disponibilidad="disponible",
                        )
                    )
                    telemetry_counter += 1

            if (day_idx + 1) % 60 == 0 or (day_idx + 1) == len(weather_df):
                logger.info(f"Simulated {day_idx + 1}/{len(weather_df)} days... ({len(viajes)} rides generated)")

        logger.info(f"MoviGo simulation completed! Produced {len(viajes)} rides and {len(telemetria)} telemetry pings.")
        return viajes, telemetria
