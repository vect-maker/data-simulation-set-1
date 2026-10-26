"""Numerical and operational simulation engine for MoviGo ride-hailing app in Managua.

Generates realistic urban mobility facts with strict mathematical guarantees:
- Two-tier spatial architecture: 12 urban pricing zones (zonas_urbanas) grouping 92 fine-grained square quadrants (cuadrantes, ~0.88 km x 0.88 km)
- Hourly localized weather, topographical cauce runoff (escorrentia_cauce_mm), and street flooding (vias_anegadas) per square quadrant
- Street-snapped Origin, Destination, and Telemetry GPS coordinates from OpenStreetMap ways strictly within their square quadrant bounding box
- Physical route consistency (Haversine * circuity factor) with forced detours when cauces flood
- Micro-behavioral logistic cancellation model (stratum surge sensitivity, cash threshold C$200/C$500, dispatch wait > 10m, flooded streets)
- Transparent parametric pricing breakdown (tarifa_bajada_bandera, cargo_distancia, cargo_tiempo, tarifa_base, multiplicador_dinamico, tarifa_final)
- Supply & Demand snapshot at request time (solicitudes_activas_origen, conductores_disponibles_origen) coupled to f(m) = D(m) - S(m) = 0
- Multi-point GPS breadcrumb trajectories in telemetria_conductores linked via id_viaje and id_cuadrante
"""

import json
import logging
import math
from datetime import datetime, date, timedelta, time
from typing import Any
import numpy as np
import pandas as pd

from movigo_sim.config import (
    DETERMINISTIC_SEEDS_DIR,
    LLM_SEEDS_DIR,
    BASE_PER_KM_NIO,
    BASE_PER_MINUTE_NIO,
    SURGE_RAIN_FACTOR,
    SURGE_MAX,
    OUTLIER_MOBILITY_SHOCK_PROB,
    OUTLIER_AIRPORT_TRIP_PROB,
    OUTLIER_GRIDLOCK_DELAY_PROB,
)
from movigo_sim.models import (
    Cuadrante,
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


def load_movigo_cuadrantes() -> list[Cuadrante]:
    """Load the 92 Managua geographical square quadrants from deterministic JSON seed fixture."""
    with open(DETERMINISTIC_SEEDS_DIR / "cuadrantes.json", encoding="utf-8") as f:
        return [Cuadrante(**c) for c in json.load(f)]


def load_movigo_seed_catalogs() -> tuple[
    list[ZonaUrbana],
    list[Usuario],
    list[Conductor],
    list[CampanaIncentivo],
    dict[str, Any],
]:
    """Load dimensional seed catalogs from deterministic/ and llm/ JSON fixtures."""
    with open(DETERMINISTIC_SEEDS_DIR / "zonas_urbanas.json", encoding="utf-8") as f:
        zonas = [ZonaUrbana(**z) for z in json.load(f)]

    with open(LLM_SEEDS_DIR / "usuarios.json", encoding="utf-8") as f:
        usuarios = [Usuario(**u) for u in json.load(f)]

    with open(LLM_SEEDS_DIR / "conductores.json", encoding="utf-8") as f:
        conductores = [Conductor(**c) for c in json.load(f)]

    with open(LLM_SEEDS_DIR / "campanas_incentivos.json", encoding="utf-8") as f:
        campanas = [CampanaIncentivo(**cmp) for cmp in json.load(f)]

    with open(LLM_SEEDS_DIR / "semantic_templates.json", encoding="utf-8") as f:
        templates = json.load(f)

    return zonas, usuarios, conductores, campanas, templates


def load_managua_street_network() -> dict[str, Any]:
    """Load cached OpenStreetMap drivable street segments and flood-hotspot flags from deterministic/."""
    network_path = DETERMINISTIC_SEEDS_DIR / "managua_street_network.json"
    if network_path.exists():
        with open(network_path, encoding="utf-8") as f:
            return json.load(f)
    return {"zones": {}, "arterials": [], "zone_flood_flags": {}, "cuadrante_streets": {}, "cuadrante_flood_flags": {}}


class MoviGoSimulationEngine:
    """Core numerical simulation engine for MoviGo ride-hailing facts."""

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)

        self.cuadrantes = load_movigo_cuadrantes()
        self.cuadrantes_map = {c.id_cuadrante: c for c in self.cuadrantes}
        self.cuadrantes_centers = np.array(
            [[0.5 * (c.lat_min + c.lat_max), 0.5 * (c.lon_min + c.lon_max)] for c in self.cuadrantes],
            dtype=float,
        )

        (
            self.zonas,
            self.usuarios,
            self.conductores,
            self.campanas,
            self.templates,
        ) = load_movigo_seed_catalogs()

        self.zone_cuadrantes: dict[int, list[Cuadrante]] = {z.id_zona: [] for z in self.zonas}
        for c in self.cuadrantes:
            if c.id_zona in self.zone_cuadrantes:
                self.zone_cuadrantes[c.id_zona].append(c)

        self.street_network = load_managua_street_network()
        self.cuadrante_streets: dict[int, np.ndarray] = {}
        self.cuadrante_flood_flags: dict[int, np.ndarray] = {}
        for c in self.cuadrantes:
            segs = self.street_network.get("cuadrante_streets", {}).get(str(c.id_cuadrante), [])
            flags = self.street_network.get("cuadrante_flood_flags", {}).get(str(c.id_cuadrante), [])
            if segs:
                self.cuadrante_streets[c.id_cuadrante] = np.array(segs, dtype=float)
                self.cuadrante_flood_flags[c.id_cuadrante] = (
                    np.array(flags, dtype=bool) if len(flags) == len(segs) else np.zeros(len(segs), dtype=bool)
                )
            else:
                self.cuadrante_streets[c.id_cuadrante] = np.empty((0, 4), dtype=float)
                self.cuadrante_flood_flags[c.id_cuadrante] = np.empty(0, dtype=bool)

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

    def sample_street_coordinate(self, zona: ZonaUrbana) -> tuple[float, float, int, bool]:
        """Sample a GPS coordinate strictly on a drivable street within one of the urban zone's square cuadrantes.

        Returns:
            (latitud, longitud, id_cuadrante, is_flood_prone_street)
        """
        quad_list = self.zone_cuadrantes.get(zona.id_zona) or self.cuadrantes
        q_idx = int(np.random.randint(0, len(quad_list)))
        cuad = quad_list[q_idx]

        segs = self.cuadrante_streets.get(cuad.id_cuadrante)
        flags = self.cuadrante_flood_flags.get(cuad.id_cuadrante)
        if segs is not None and len(segs) > 0:
            idx = int(np.random.randint(0, len(segs)))
            lat1, lon1, lat2, lon2 = segs[idx]
            t = float(np.random.uniform(0.0, 1.0))
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            lat_clamped = round(float(np.clip(lat, cuad.lat_min, cuad.lat_max)), 6)
            lon_clamped = round(float(np.clip(lon, cuad.lon_min, cuad.lon_max)), 6)
            is_flood_street = bool(flags[idx]) if flags is not None and len(flags) > idx else (cuad.riesgo_inundacion == "critico")
            return lat_clamped, lon_clamped, cuad.id_cuadrante, is_flood_street

        lat_f = round(float(np.random.uniform(cuad.lat_min + 0.0005, cuad.lat_max - 0.0005)), 6)
        lon_f = round(float(np.random.uniform(cuad.lon_min + 0.0005, cuad.lon_max - 0.0005)), 6)
        return lat_f, lon_f, cuad.id_cuadrante, (cuad.riesgo_inundacion == "critico")

    def snap_to_nearest_street_and_cuadrante(
        self, target_lat: float, target_lon: float, fallback_zona: ZonaUrbana
    ) -> tuple[float, float, int, int]:
        """Snap an arbitrary waypoint coordinate onto the nearest real OpenStreetMap street inside an active square cuadrante.

        Returns:
            (lat, lon, id_zona, id_cuadrante)
        """
        d2 = (self.cuadrantes_centers[:, 0] - target_lat) ** 2 + (self.cuadrantes_centers[:, 1] - target_lon) ** 2
        nearest_q_idx = int(np.argmin(d2))
        cuad = self.cuadrantes[nearest_q_idx]
        segs = self.cuadrante_streets.get(cuad.id_cuadrante)
        if segs is not None and len(segs) > 0:
            seg_idx = int(np.random.randint(0, len(segs)))
            lat1, lon1, lat2, lon2 = segs[seg_idx]
            t = float(np.random.uniform(0.15, 0.85))
            lat = round(float(np.clip(lat1 + t * (lat2 - lat1), cuad.lat_min, cuad.lat_max)), 6)
            lon = round(float(np.clip(lon1 + t * (lon2 - lon1), cuad.lon_min, cuad.lon_max)), 6)
            return lat, lon, cuad.id_zona, cuad.id_cuadrante

        lat, lon, qid, _ = self.sample_street_coordinate(fallback_zona)
        return lat, lon, fallback_zona.id_zona, qid

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
        hourly_precip_mm: float,
        escorrentia_mm: float,
        vias_anegadas: bool,
        hour: int,
        dow: int,
    ) -> tuple[int, int, float]:
        """Simulate origin zone active demand (Dt), available drivers (St), and equilibrium surge multiplier m*.

        Couples Dt and St to the excess demand equation:
            f(m) = Dt * exp(-alpha * (m - 1)) - St * (1 + gamma * ln(m)) = 0
        driven by localized hourly quadrant rainfall and cauce runoff.
        """
        hour_weight = HOURLY_TRIP_WEIGHTS[hour] / HOURLY_TRIP_WEIGHTS.mean()
        stratum_demand_factor = {
            "comercial": 1.30,
            "popular": 1.20,
            "medio": 1.00,
            "alto": 0.90,
        }.get(zona_origen.estrato_socioeconomico, 1.0)

        weekend_boost = 1.15 if dow in [4, 5] else 1.00
        effective_water_mm = max(hourly_precip_mm, 0.75 * escorrentia_mm)

        # Active trip requests in origin zone during that hour (Dt)
        expected_d = (14.0 * hour_weight * stratum_demand_factor * weekend_boost) + (1.45 * effective_water_mm)
        if vias_anegadas:
            expected_d *= 1.22
        d_t = max(2, int(round(np.random.normal(expected_d, max(1.8, 0.12 * expected_d)))))

        # Available driver supply in origin zone during that hour (St)
        rain_supply_penalty = max(0.45, 1.0 - 0.032 * effective_water_mm - (0.18 if vias_anegadas else 0.0))
        peak_supply_factor = 0.82 if hour in [7, 8, 17, 18] else (0.90 if hour in [12, 13, 19] else 1.12)
        expected_s = (13.5 * hour_weight * stratum_demand_factor * peak_supply_factor * rain_supply_penalty) + 2.0
        s_t = max(1, int(round(np.random.normal(expected_s, max(1.5, 0.10 * expected_s)))))

        # Solve market-clearing surge multiplier m* from excess demand ratio Dt / St
        if d_t <= s_t and effective_water_mm < 0.5 and hour not in [7, 8, 17, 18]:
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
            rain_boost = 0.045 * effective_water_mm + (0.18 if vias_anegadas else 0.0)
            rush_boost = 0.12 if hour in [7, 8, 17, 18] else (0.06 if hour in [12, 13, 19] else 0.0)
            base_m = m + rain_boost + rush_boost + float(np.random.normal(0.0, 0.04))

        if (vias_anegadas or effective_water_mm > 8.0) and hour in [7, 8, 17, 18] and np.random.rand() < 0.22:
            multiplier = float(np.random.uniform(2.60, 3.20))
        else:
            multiplier = float(np.clip(base_m, 1.00, SURGE_MAX))

        return d_t, s_t, round(multiplier, 2)

    def calculate_surge_multiplier(self, precip_mm: float, hour: int) -> float:
        """Backward-compatible helper to calculate dynamic surge multiplier."""
        _, _, m = self.simulate_supply_demand_and_surge(self.zonas[0], precip_mm, precip_mm, precip_mm > 12.0, hour, 2)
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
        effective_water_mm: float = 0.0,
        flood_affected_route: bool = False,
    ) -> tuple[float, float, bool]:
        """Calculate road distance and duration from exact GPS coordinates with flood-induced detours."""
        hav_km = haversine_km(lat_o, lon_o, lat_d, lon_d)

        is_suboptimal = bool(flood_affected_route or (np.random.rand() < 0.16))
        if flood_affected_route:
            circuity_factor = float(np.random.uniform(1.55, 2.02))
        elif is_suboptimal:
            circuity_factor = float(np.random.uniform(1.50, 1.88))
        else:
            circuity_factor = float(np.clip(np.random.normal(1.30, 0.03), 1.24, 1.38))

        dist_km = round(max(0.65, hav_km * circuity_factor), 2)

        rain_speed_penalty = 1.0 + 0.025 * effective_water_mm + (0.28 if flood_affected_route else 0.0)
        effective_speed_kmh = max(8.5, 30.5 / (congestion_idx * rain_speed_penalty))
        duration_min = round(
            max(2.5, (dist_km / effective_speed_kmh) * 60.0 + float(np.random.uniform(1.0, 3.5))),
            2,
        )

        roll = np.random.rand()
        if roll < OUTLIER_AIRPORT_TRIP_PROB:
            dist_km = round(max(dist_km, float(np.random.uniform(18.0, 32.0))), 2)
            duration_min = round(float(dist_km * np.random.uniform(1.6, 2.2) + np.random.uniform(8.0, 18.0)), 2)
            is_suboptimal = True
        elif roll < (OUTLIER_AIRPORT_TRIP_PROB + OUTLIER_GRIDLOCK_DELAY_PROB):
            duration_min = round(float(duration_min + np.random.uniform(30.0, 55.0)), 2)

        return dist_km, duration_min, is_suboptimal

    def evaluate_cancellation(
        self,
        stratum: str,
        metodo_pago: str,
        surge: float,
        tarifa_final: float,
        wait_min: float,
        effective_water_mm: float,
        flood_affected: bool,
        congestion_idx: float,
        hour: int,
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate trip cancellation via micro-behavioral logistic model and assign structured reason."""
        beta_surge = STRATUM_SURGE_BETA.get(stratum, 1.15)
        surge_term = beta_surge * (surge - 1.0)

        cash_term = 0.0
        if metodo_pago == "efectivo":
            if tarifa_final > 500.0:
                cash_term = 2.15
            elif tarifa_final > 200.0:
                cash_term = 1.10

        delay_term = 0.0
        if wait_min > 10.0:
            delay_term = 0.24 * (math.exp(0.22 * min(wait_min - 10.0, 10.0)) - 1.0)

        peak_term = 0.55 if hour in [7, 8, 17, 18] else 0.0
        flood_term = 0.95 if flood_affected else (0.35 if effective_water_mm > 4.0 else (0.18 if congestion_idx > 2.2 else 0.0))

        logit = -3.88 + surge_term + cash_term + delay_term + peak_term + flood_term
        cancel_prob = float(np.clip(1.0 / (1.0 + math.exp(-logit)), 0.015, 0.72))

        if np.random.rand() >= cancel_prob:
            return False, None, None

        if flood_affected or (effective_water_mm > 3.5 and np.random.rand() < 0.55):
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

        roll = np.random.rand()
        if roll < 0.40:
            return True, "cancelado_usuario", "Tarifa dinámica sobrepasa presupuesto"
        elif roll < 0.72:
            return True, "cancelado_usuario", "Tiempo de llegada excesivo"
        elif roll < 0.88:
            return True, "cancelado_usuario", "Conductor no avanza"
        else:
            reason = "Vía anegada / cauce intransitable" if effective_water_mm > 1.5 else "Falla mecánica / imprevisto del conductor"
            return True, "cancelado_conductor", reason

    def run_simulation(
        self,
        weather_df: pd.DataFrame,
    ) -> tuple[list[Viaje], list[TelemetriaConductor]]:
        """Run full year MoviGo simulation coupled to hourly square-quadrant climate and street flood risk."""
        logger.info(f"Starting MoviGo simulation across {len(weather_df)} days...")

        hourly_matrices: dict[str, Any] | None = weather_df.attrs.get("hourly_matrices")
        date_hour_to_idx: dict[tuple[date, int], int] = (
            hourly_matrices["date_hour_to_idx"] if hourly_matrices else {}
        )

        viajes: list[Viaje] = []
        telemetria: list[TelemetriaConductor] = []
        trip_counter = 1
        telemetry_counter = 1

        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
            curr_date: date = row["fecha"]
            daily_precip_mm: float = float(row["precipitacion_mm"])
            daily_cong_idx: float = float(row["indice_congestion"])
            dow: int = curr_date.weekday()

            daily_target = self.calculate_daily_demand(daily_precip_mm, dow)

            for _ in range(daily_target):
                trip_id = trip_counter
                trip_counter += 1

                req_time = self.sample_trip_time(curr_date)
                hour = req_time.hour

                user = np.random.choice(self.usuarios)

                zona_origen = np.random.choice(self.zonas)
                dest_candidates = [z for z in self.zonas if z.id_zona != zona_origen.id_zona]
                zona_destino = np.random.choice(dest_candidates)

                # Street-snapped Origin and Destination GPS coordinates inside exact square cuadrantes
                lat_o, lon_o, q_o, flood_street_o = self.sample_street_coordinate(zona_origen)
                lat_d, lon_d, q_d, flood_street_d = self.sample_street_coordinate(zona_destino)

                # Look up localized hourly weather & cauce runoff for Origin and Destination Square Cuadrantes
                t_idx = date_hour_to_idx.get((curr_date, hour)) if hourly_matrices else None
                if hourly_matrices is not None and t_idx is not None:
                    qo_idx = q_o - 1
                    qd_idx = q_d - 1
                    h_precip_o = float(hourly_matrices["precip"][t_idx, qo_idx])
                    h_esc_o = float(hourly_matrices["runoff"][t_idx, qo_idx])
                    h_cong_o = float(hourly_matrices["congestion"][t_idx, qo_idx])
                    h_aneg_o = bool(hourly_matrices["flooded"][t_idx, qo_idx])

                    h_esc_d = float(hourly_matrices["runoff"][t_idx, qd_idx])
                    h_cong_d = float(hourly_matrices["congestion"][t_idx, qd_idx])
                    h_aneg_d = bool(hourly_matrices["flooded"][t_idx, qd_idx])

                    effective_congestion = round(0.60 * h_cong_o + 0.40 * h_cong_d, 2)
                    effective_water_mm = max(h_precip_o, h_esc_o, 0.80 * h_esc_d)
                    flood_affected = bool(
                        h_aneg_o
                        or h_aneg_d
                        or ((flood_street_o or flood_street_d) and effective_water_mm >= 3.0)
                    )
                else:
                    h_precip_o = daily_precip_mm / 8.0 if hour in range(13, 21) else 0.0
                    h_esc_o = h_precip_o
                    effective_congestion = daily_cong_idx
                    effective_water_mm = h_precip_o
                    flood_affected = bool((flood_street_o or flood_street_d) and daily_precip_mm > 15.0)
                    h_aneg_o = flood_affected

                # Supply & Demand state at request time and equilibrium surge multiplier
                d_t, s_t, surge = self.simulate_supply_demand_and_surge(
                    zona_origen, h_precip_o, h_esc_o, h_aneg_o, hour, dow
                )

                metodo_pago = self.sample_payment_method_for_stratum(zona_origen.estrato_socioeconomico)

                dist_km, dur_min, is_suboptimal = self.estimate_distance_and_duration(
                    lat_o, lon_o, lat_d, lon_d, effective_congestion, effective_water_mm, flood_affected
                )

                tarifa_bajada = round(float(zona_origen.tarifa_base_bajada_bandera), 2)
                cargo_dist = round(dist_km * BASE_PER_KM_NIO, 2)
                cargo_tpo = round(dur_min * BASE_PER_MINUTE_NIO, 2)
                tarifa_base = round(tarifa_bajada + cargo_dist + cargo_tpo, 2)
                tarifa_final = round(tarifa_base * surge, 2)

                imbalance_ratio = d_t / max(1.0, float(s_t))
                base_wait = (
                    float(np.random.uniform(2.5, 6.2))
                    + 1.4 * max(0.0, imbalance_ratio - 0.9)
                    + 1.2 * (effective_congestion - 1.0)
                    + (3.2 if flood_affected else 0.0)
                )
                if effective_water_mm > 4.0 or hour in [7, 8, 17, 18]:
                    base_wait += float(np.random.exponential(2.0))
                wait_min = round(float(np.clip(base_wait, 1.5, 25.0)), 2)

                conductor = np.random.choice(self.active_conductores)

                is_canceled, cancel_state, motivo = self.evaluate_cancellation(
                    stratum=zona_origen.estrato_socioeconomico,
                    metodo_pago=metodo_pago,
                    surge=surge,
                    tarifa_final=tarifa_final,
                    wait_min=wait_min,
                    effective_water_mm=effective_water_mm,
                    flood_affected=flood_affected,
                    congestion_idx=effective_congestion,
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
                        id_cuadrante_origen=q_o,
                        id_cuadrante_destino=q_d,
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
                if not is_canceled and np.random.rand() < 0.08:
                    avg_speed_kmh = max(9.0, min(75.0, (dist_km / max(0.05, dur_min / 60.0))))
                    detour_lat_offset = float(np.random.choice([-0.008, 0.008])) if is_suboptimal else 0.0
                    detour_lon_offset = float(np.random.choice([-0.009, 0.009])) if is_suboptimal else 0.0

                    approach_lat, approach_lon, approach_q, _ = self.sample_street_coordinate(zona_origen)
                    telemetria.append(
                        TelemetriaConductor(
                            id_telemetria=telemetry_counter,
                            id_conductor=conductor.id_conductor,
                            id_viaje=trip_id,
                            id_zona=zona_origen.id_zona,
                            id_cuadrante=approach_q,
                            fecha_hora=req_time + timedelta(minutes=round(wait_min * 0.5, 2)),
                            latitud=approach_lat,
                            longitud=approach_lon,
                            velocidad_kmh=round(float(np.clip(avg_speed_kmh * np.random.uniform(0.75, 1.15), 8.0, 65.0)), 2),
                            estado_disponibilidad="en_camino_recogida",
                        )
                    )
                    telemetry_counter += 1

                    for frac in (0.15, 0.55, 0.90):
                        raw_lat = lat_o + frac * (lat_d - lat_o) + (detour_lat_offset if frac == 0.55 else 0.0)
                        raw_lon = lon_o + frac * (lon_d - lon_o) + (detour_lon_offset if frac == 0.55 else 0.0)
                        fallback_z = zona_origen if frac < 0.5 else zona_destino
                        wp_lat, wp_lon, wp_zone_id, wp_quad_id = self.snap_to_nearest_street_and_cuadrante(
                            raw_lat, raw_lon, fallback_z
                        )

                        speed_roll = np.random.rand()
                        if flood_affected and frac == 0.55:
                            wp_speed = float(np.random.uniform(3.5, 11.5))
                        elif speed_roll < 0.08:
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
                                id_cuadrante=wp_quad_id,
                                fecha_hora=start_time + timedelta(minutes=round(dur_min * frac, 2)),
                                latitud=wp_lat,
                                longitud=wp_lon,
                                velocidad_kmh=round(wp_speed, 2),
                                estado_disponibilidad="ocupado",
                            )
                        )
                        telemetry_counter += 1

                elif np.random.rand() < 0.06:
                    idle_lat, idle_lon, idle_q, _ = self.sample_street_coordinate(zona_origen)
                    telemetria.append(
                        TelemetriaConductor(
                            id_telemetria=telemetry_counter,
                            id_conductor=conductor.id_conductor,
                            id_viaje=None,
                            id_zona=zona_origen.id_zona,
                            id_cuadrante=idle_q,
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
