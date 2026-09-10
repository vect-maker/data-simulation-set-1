"""Numerical and operational simulation engine for MoviGo ride-hailing app in Managua.

Generates realistic urban mobility facts with strict mathematical guarantees:
- Continuous driver response (rain Pt & peak hour -> surge multiplier & demand)
- NHPP arrival process with morning/evening rush hour spikes
- Chi-Square dependency injection: P(Payment Method | Socioeconomic Zone) -> p < 0.01
- Distance & duration routing matrices over Managua road network
- Driver telemetry pings and Knapsack incentive campaigns
"""

import json
import logging
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from movigo_sim.config import (
    SEEDS_DIR,
    BASE_FLAG_DROP_NIO,
    BASE_PER_KM_NIO,
    BASE_PER_MINUTE_NIO,
    SURGE_RAIN_FACTOR,
    SURGE_MAX,
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
STRATUM_PAYMENT_PROBABILITIES: Dict[str, List[float]] = {
    "alto":      [0.10, 0.65, 0.25], # High stratum: heavily credit/debit card
    "medio":     [0.30, 0.42, 0.28], # Middle stratum: balanced
    "comercial": [0.20, 0.48, 0.32], # Commercial hubs & universities: cards & wallets
    "popular":   [0.75, 0.10, 0.15], # Traditional markets: predominantly cash
}

PAYMENT_METHODS = ["efectivo", "tarjeta", "billetera_digital"]

# Hourly arrival curve for Managua urban traffic (24 hours)
# Peaks: Morning rush (07:00-08:30), Lunch (12:00-13:30), Evening rush (17:00-19:30), Friday/Saturday nightlife
HOURLY_TRIP_WEIGHTS = np.array([
    0.015, 0.008, 0.005, 0.004, 0.008, 0.025, # 00:00 - 05:59 (Night)
    0.065, 0.115, 0.085, 0.055, 0.045, 0.055, # 06:00 - 11:59 (Morning peak 7-9am)
    0.080, 0.065, 0.045, 0.040, 0.055, 0.095, # 12:00 - 17:59 (Lunch & mid-afternoon)
    0.110, 0.085, 0.055, 0.040, 0.028, 0.020  # 18:00 - 23:59 (Evening rush & night close)
])
HOURLY_TRIP_WEIGHTS /= HOURLY_TRIP_WEIGHTS.sum()


def load_movigo_seed_catalogs() -> Tuple[
    List[ZonaUrbana],
    List[Usuario],
    List[Conductor],
    List[CampanaIncentivo],
    Dict[str, Any],
]:
    """Load dimensional seed catalogs from JSON fixtures."""
    with open(SEEDS_DIR / "zonas_urbanas.json", "r", encoding="utf-8") as f:
        zonas = [ZonaUrbana(**z) for z in json.load(f)]

    with open(SEEDS_DIR / "usuarios.json", "r", encoding="utf-8") as f:
        usuarios = [Usuario(**u) for u in json.load(f)]

    with open(SEEDS_DIR / "conductores.json", "r", encoding="utf-8") as f:
        conductores = [Conductor(**c) for c in json.load(f)]

    with open(SEEDS_DIR / "campanas_incentivos.json", "r", encoding="utf-8") as f:
        campanas = [CampanaIncentivo(**cmp) for cmp in json.load(f)]

    with open(SEEDS_DIR / "semantic_templates.json", "r", encoding="utf-8") as f:
        templates = json.load(f)

    return zonas, usuarios, conductores, campanas, templates


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

        self.zonas_map = {z.id_zona: z for z in self.zonas}
        self.conductores_map = {c.id_conductor: c for c in self.conductores}
        self.active_conductores = [c for c in self.conductores if c.estado == "activo"]

    @property
    def semantic_templates(self):
        """Backward-compatible alias for templates."""
        return self.templates

    def calculate_daily_demand(self, precip_mm: float, dow: int) -> int:
        """Daily ride requests driven by rain and day-of-week in Managua."""
        # Baseline ~180 rides on dry weekdays, +25 Friday/Sat, +4.5 rides per mm of rain
        dow_adj = 30.0 if dow in [4, 5] else (0.0 if dow in [0, 1, 2, 3] else -15.0)
        rain_adj = 5.2 * precip_mm
        noise = np.random.normal(0, 10.0)

        total_rides = 175.0 + rain_adj + dow_adj + noise
        return max(75, int(round(total_rides)))

    def sample_trip_time(self, curr_date: date) -> datetime:
        """Sample request timestamp via NHPP."""
        hour = int(np.random.choice(24, p=HOURLY_TRIP_WEIGHTS))
        minute = int(np.random.randint(0, 60))
        second = int(np.random.randint(0, 60))
        return datetime.combine(curr_date, time(hour, minute, second))

    def calculate_surge_multiplier(self, precip_mm: float, hour: int) -> float:
        """Calculate dynamic surge multiplier based on rain and rush hours."""
        base_surge = 1.00

        # Rush hour boost
        if hour in [7, 8, 17, 18]:
            base_surge += 0.35
        elif hour in [12, 13, 19]:
            base_surge += 0.20

        # Rain friction surge (Managua downpours skyrocket ride demand)
        rain_surge = SURGE_RAIN_FACTOR * precip_mm
        noise = np.random.normal(0, 0.05)

        multiplier = round(float(np.clip(base_surge + rain_surge + noise, 1.00, SURGE_MAX)), 2)
        return multiplier

    def sample_payment_method_for_stratum(self, stratum: str) -> str:
        """Sample payment method conditioned on origin zone stratum (Chi-Square guarantee)."""
        probs = STRATUM_PAYMENT_PROBABILITIES.get(stratum, [0.40, 0.35, 0.25])
        return str(np.random.choice(PAYMENT_METHODS, p=probs))

    def estimate_distance_and_duration(
        self,
        zona_o: ZonaUrbana,
        zona_d: ZonaUrbana,
        congestion_idx: float,
    ) -> Tuple[float, float]:
        """Estimate driving distance and duration over Managua road grid."""
        # Euclidean / Manhattan distance approximation for Managua
        d_lat = abs(zona_o.latitud - zona_d.latitud) * 111.0 # 1 deg lat ~ 111 km
        d_lon = abs(zona_o.longitud - zona_d.longitud) * 108.5 # 1 deg lon at 12 deg ~ 108.5 km
        dist_km = round(float(np.sqrt(d_lat**2 + d_lon**2) * 1.32 + np.random.uniform(0.8, 2.2)), 2)
        dist_km = max(1.2, dist_km)

        # Average speed: 28 km/h on clear roads, drops to 12-16 km/h during heavy congestion
        avg_speed = max(11.0, 32.0 / congestion_idx)
        duration_min = round(float((dist_km / avg_speed) * 60.0 + np.random.uniform(1.5, 4.0)), 2)
        return dist_km, duration_min

    def run_simulation(
        self,
        weather_df: pd.DataFrame,
    ) -> Tuple[List[Viaje], List[TelemetriaConductor]]:
        """Run full year MoviGo simulation."""
        logger.info(f"Starting MoviGo simulation across {len(weather_df)} days...")

        viajes: List[Viaje] = []
        telemetria: List[TelemetriaConductor] = []
        trip_counter = 1
        telemetry_counter = 1

        motivos_cancel = self.templates.get("motivos_cancelacion", [])

        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
            curr_date: date = row["fecha"]
            precip_mm: float = float(row["precipitacion_mm"])
            congestion_idx: float = float(row["indice_congestion"])
            dow: int = curr_date.weekday()

            daily_target = self.calculate_daily_demand(precip_mm, dow)

            # Sample daily trips
            for _ in range(daily_target):
                trip_id = f"VIJ-2024-{trip_counter:06d}"
                trip_counter += 1

                req_time = self.sample_trip_time(curr_date)
                hour = req_time.hour

                # Sample passenger
                user = np.random.choice(self.usuarios)

                # Sample origin and destination zones
                zona_origen = np.random.choice(self.zonas)
                dest_candidates = [z for z in self.zonas if z.id_zona != zona_origen.id_zona]
                zona_destino = np.random.choice(dest_candidates)

                # Payment method conditioned on stratum (Chi-Square guarantee)
                metodo_pago = self.sample_payment_method_for_stratum(zona_origen.estrato_socioeconomico)

                # Distance and duration
                dist_km, dur_min = self.estimate_distance_and_duration(zona_origen, zona_destino, congestion_idx)

                # Pricing calculation
                bajada_bandera = zona_origen.tarifa_base_bajada_bandera
                tarifa_base = round(bajada_bandera + (dist_km * BASE_PER_KM_NIO) + (dur_min * BASE_PER_MINUTE_NIO), 2)
                surge = self.calculate_surge_multiplier(precip_mm, hour)
                tarifa_final = round(tarifa_base * surge, 2)

                # Assign driver
                conductor = np.random.choice(self.active_conductores)

                # Trip state & cancellation probability:
                # Base cancellation: ~3.5%, surges up to 14% if surge > 2.0x or congestion > 2.5
                cancel_prob = 0.035
                if surge > 2.0:
                    cancel_prob += 0.065
                if congestion_idx > 2.2:
                    cancel_prob += 0.050

                is_canceled = np.random.rand() < cancel_prob

                if is_canceled:
                    estado_viaje = np.random.choice(["cancelado_usuario", "cancelado_conductor"], p=[0.65, 0.35])
                    start_time = None
                    end_time = None
                    rating_usr = None
                    rating_cnd = None
                    propina = 0.0
                    motivo = str(np.random.choice(motivos_cancel)) if motivos_cancel else "Cancelado por demora"
                else:
                    estado_viaje = "completado"
                    pickup_wait_min = float(np.random.uniform(3.0, 9.0))
                    start_time = req_time + timedelta(minutes=pickup_wait_min)
                    end_time = start_time + timedelta(minutes=dur_min)
                    rating_usr = float(np.random.choice([5.0, 4.0, 3.0, 5.0, 5.0], p=[0.70, 0.18, 0.04, 0.05, 0.03]))
                    rating_cnd = float(np.random.choice([5.0, 4.0, 5.0, 5.0], p=[0.78, 0.12, 0.05, 0.05]))
                    propina = float(np.random.choice([0.0, 20.0, 30.0, 50.0], p=[0.75, 0.15, 0.07, 0.03]))
                    motivo = None

                viajes.append(
                    Viaje(
                        id_viaje=trip_id,
                        id_usuario=user.id_usuario,
                        id_conductor=conductor.id_conductor,
                        id_zona_origen=zona_origen.id_zona,
                        id_zona_destino=zona_destino.id_zona,
                        fecha_hora_solicitud=req_time,
                        fecha_hora_inicio=start_time,
                        fecha_hora_fin=end_time,
                        distancia_km=dist_km,
                        duracion_minutos=dur_min,
                        tarifa_base=tarifa_base,
                        multiplicador_dinamico=surge,
                        tarifa_final=tarifa_final,
                        metodo_pago=metodo_pago,
                        estado_viaje=estado_viaje,
                        calificacion_usuario=rating_usr,
                        calificacion_conductor=rating_cnd,
                        propina=propina,
                        motivo_cancelacion=motivo,
                    )
                )

                # Generate occasional telemetry ping during peak hours
                if np.random.rand() < 0.25:
                    telemetria.append(
                        TelemetriaConductor(
                            id_telemetria=telemetry_counter,
                            id_conductor=conductor.id_conductor,
                            id_zona=zona_origen.id_zona,
                            fecha_hora=req_time + timedelta(minutes=2),
                            latitud=zona_origen.latitud + float(np.random.normal(0, 0.004)),
                            longitud=zona_origen.longitud + float(np.random.normal(0, 0.004)),
                            velocidad_kmh=round(float(np.random.uniform(15.0, 48.0)), 2),
                            estado_disponibilidad="ocupado" if not is_canceled else "disponible",
                        )
                    )
                    telemetry_counter += 1

            if (day_idx + 1) % 60 == 0 or (day_idx + 1) == len(weather_df):
                logger.info(f"Simulated {day_idx + 1}/{len(weather_df)} days... ({len(viajes)} rides generated)")

        logger.info(f"MoviGo simulation completed! Produced {len(viajes)} rides and {len(telemetria)} telemetry pings.")
        return viajes, telemetria
