"""Agent/Entity definitions for MoviGo ride-hailing simulation.

Models autonomous participants:
- DriverAgent: Operational vehicle operator maintaining physical coordinate position,
  clock availability, operational shifts, and cruising/dispatch responses.
- RiderAgent: Urban commuter with registration date constraints, payment preferences,
  and demand propensities.
- RiderPersona: Archetype-specific mobility routine with anchor coordinates and commute hours.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, time
from typing import Any
import numpy as np

from movigo_sim.models import Driver, Vehicle, User


@dataclass
class DriverAgent:
    """Autonomous driver agent operating under formal company employment and shift regulations."""

    driver_id: int
    driver_model: Driver
    vehicle_model: Vehicle
    current_node: int
    available_at: datetime
    status: str
    acceptance_rate_pct: float
    home_zone_id: int
    home_quadrant_id: int
    shift_name: str = "matutino" # matutino, vespertino, nocturno
    shift_start_hour: int = 6
    shift_end_hour: int = 14
    meal_break_start: time = time(10, 40)
    meal_break_end: time = time(11, 20)
    weekly_rest_dow: int = 0 # 0=Monday .. 6=Sunday
    odometer_km: float = 35000.0
    km_since_service: float = 0.0
    cumulative_fuel_liters: float = 0.0
    maintenance_until: datetime = datetime.min
    flood_exposure_count: int = 0
    risk_aversion: float = 0.50
    shift_trips_completed: int = 0
    shift_minutes_worked: float = 0.0
    traffic_stress_accumulated: float = 0.0
    total_offers: int = 0
    total_rejections: int = 0
    current_shift_date: date | None = None

    def __post_init__(self) -> None:
        if self.risk_aversion == 0.50:
            st = self.vehicle_model.service_type
            if st == "movigo_moto":
                self.risk_aversion = 0.85
            elif st == "movigo_comfort":
                self.risk_aversion = 0.25
            else:
                self.risk_aversion = 0.65

    @property
    def is_operational(self) -> bool:
        """Driver is operational if not permanently inactive."""
        return self.status != "inactivo"

    def is_in_maintenance(self, dt: datetime) -> bool:
        """Driver is currently in maintenance bay if workshop busy clock has not expired."""
        return self.maintenance_until > dt

    def is_on_duty(self, dt: datetime) -> bool:
        """Verify if driver is on their assigned work shift and not on their weekly rest day."""
        if not self.is_operational:
            return False
        if dt.weekday() == self.weekly_rest_dow:
            return False

        h = dt.hour
        if self.shift_name == "matutino":
            return 6 <= h < 14
        elif self.shift_name == "vespertino":
            return 14 <= h < 22
        elif self.shift_name == "nocturno":
            return h >= 22 or h < 6
        return True

    def is_in_meal_break(self, dt: datetime) -> bool:
        """Verify if driver is currently taking their mandatory 40-minute meal break."""
        t = dt.time()
        return self.meal_break_start <= t <= self.meal_break_end

    def is_available_at(self, req_time: datetime) -> bool:
        """Check if driver has finished prior commitments by req_time."""
        return self.available_at <= req_time

    def is_dispatchable(self, req_time: datetime) -> bool:
        """Driver is dispatchable if operational, on duty, not in meal break, not in workshop, and available."""
        return (
            self.is_operational
            and self.is_on_duty(req_time)
            and not self.is_in_meal_break(req_time)
            and not self.is_in_maintenance(req_time)
            and self.is_available_at(req_time)
        )

    def compute_trip_fuel_liters(
        self,
        distance_km: float,
        duration_min: float,
        congestion_idx: float = 1.0,
        flooded: bool = False,
    ) -> float:
        """Compute trip fuel consumption in liters incorporating vehicle type, traffic congestion, and flood resistance."""
        st = self.vehicle_model.service_type
        if st == "movigo_moto":
            base_rate = 0.028 # ~35.7 km/l
            idle_burn_per_hr = 0.15
        elif st == "movigo_comfort":
            base_rate = 0.105 # ~9.5 km/l
            idle_burn_per_hr = 1.25
        else: # movigo_estandar
            base_rate = 0.075 # ~13.3 km/l
            idle_burn_per_hr = 0.85

        flood_mult = 1.35 if flooded else 1.00
        cong_mult = 1.0 + 0.12 * max(0.0, congestion_idx - 1.0)

        free_flow_min = (distance_km / 35.0) * 60.0
        idle_hrs = max(0.0, (duration_min - free_flow_min) / 60.0)

        fuel = (distance_km * base_rate * flood_mult * cong_mult) + (idle_hrs * idle_burn_per_hr)
        return round(float(fuel), 3)

    def accumulate_distance_and_fuel(
        self,
        distance_km: float,
        fuel_liters: float,
        flooded: bool = False,
        duration_min: float = 0.0,
        congestion_idx: float = 1.0,
    ) -> None:
        """Update vehicle wear metrics, cumulative odometer, shift workload, and flood exposures."""
        self.odometer_km = round(self.odometer_km + distance_km, 2)
        self.km_since_service = round(self.km_since_service + distance_km, 2)
        self.cumulative_fuel_liters = round(self.cumulative_fuel_liters + fuel_liters, 2)
        self.shift_trips_completed += 1
        self.shift_minutes_worked += duration_min
        self.traffic_stress_accumulated += max(0.0, congestion_idx - 1.0) * (duration_min / 30.0)
        if flooded:
            self.flood_exposure_count += 1

    def reset_shift_if_needed(self, dt: datetime) -> None:
        """Reset shift counters when a new calendar day / shift begins."""
        if self.current_shift_date != dt.date():
            self.current_shift_date = dt.date()
            self.shift_trips_completed = 0
            self.shift_minutes_worked = 0.0
            self.traffic_stress_accumulated = 0.0

    def get_shift_hours_worked(self, dt: datetime) -> float:
        """Calculate elapsed hours on duty in the current shift."""
        self.reset_shift_if_needed(dt)
        if self.shift_name == "matutino":
            elapsed = (dt.hour - 6) + (dt.minute / 60.0)
        elif self.shift_name == "vespertino":
            elapsed = (dt.hour - 14) + (dt.minute / 60.0)
        else:  # nocturno
            h = dt.hour
            elapsed = (h - 22 if h >= 22 else h + 2) + (dt.minute / 60.0)
        return max(0.0, float(elapsed))

    def get_fatigue_level(self, dt: datetime) -> float:
        """Calculate dynamic driver fatigue index in [0.0, 1.0]."""
        hours = self.get_shift_hours_worked(dt)
        if hours <= 3.0:
            base = hours * 0.08
        elif hours <= 5.5:
            base = 0.24 + (hours - 3.0) * 0.12
        else:
            base = 0.54 + (hours - 5.5) * 0.18
        stress = min(0.25, self.traffic_stress_accumulated * 0.03)
        return float(np.clip(base + stress, 0.0, 1.0))

    def get_reaction_time_delay(self, dt: datetime) -> float:
        """Cognitive reaction and dispatch acceptance latency in minutes."""
        fatigue = self.get_fatigue_level(dt)
        return round(0.20 + 2.30 * (fatigue ** 2), 2)

    def record_offer_result(self, accepted: bool) -> None:
        """Track dispatch offers, rejections, and update acceptance rate."""
        self.total_offers += 1
        if not accepted:
            self.total_rejections += 1
        if self.total_offers > 0:
            rate = (1.0 - (self.total_rejections / self.total_offers)) * 100.0
            self.acceptance_rate_pct = max(50.0, round(float(rate), 2))

    def evaluate_trip_offer(
        self,
        pickup_km: float,
        trip_dist_km: float,
        trip_dur_min: float,
        fare: float,
        is_route_overflow: bool,
        dest_zone_id: int,
        req_time: datetime,
        rng: np.random.Generator,
    ) -> tuple[bool, str | None]:
        """Micro-behavioral decision model for trip offer acceptance vs strategic refusal.

        Evaluates:
        1. Hydrological risk aversion (raging / overflowing cauces).
        2. Shift fatigue & burnout (shift hours >= 5.5 or high fatigue).
        3. Deadhead distance refusal (pickup > 4km into low-demand destinations).
        """
        self.reset_shift_if_needed(req_time)

        # 1. Hydrological risk aversion
        if is_route_overflow:
            st = self.vehicle_model.service_type
            if st == "movigo_moto":
                p_reject = min(0.98, 0.70 + 0.30 * self.risk_aversion)
            elif st == "movigo_comfort":
                p_reject = min(0.35, 0.10 + 0.25 * self.risk_aversion)
            else:  # movigo_estandar
                p_reject = min(0.85, 0.45 + 0.40 * self.risk_aversion)

            if rng.random() < p_reject:
                return False, "Riesgo de inundación / cauce desbordado (rechazo conductor)"

        # 2. Accumulated shift fatigue & burnout
        hours = self.get_shift_hours_worked(req_time)
        fatigue = self.get_fatigue_level(req_time)
        if hours >= 5.5 or fatigue >= 0.65:
            fatigue_roll = float(rng.random())
            p_fatigue_reject = float(np.clip(
                0.22 * (hours - 5.0) + 0.28 * fatigue + (0.06 * max(0.0, pickup_km - 2.0)),
                0.0,
                0.88,
            ))
            if fatigue_roll < p_fatigue_reject:
                return False, "Conductor fatigado / fin de turno"

        # 3. Deadhead distance & low-demand destination refusal
        high_demand_zones = {1, 4, 6, 9, 11}
        if pickup_km > 4.0 and dest_zone_id not in high_demand_zones:
            p_deadhead_reject = float(np.clip(0.60 + 0.08 * (pickup_km - 4.0), 0.60, 0.94))
            if rng.random() < p_deadhead_reject:
                return False, "Desplazamiento en vacío excesivo (>4km a zona baja demanda)"

        return True, None

    def send_to_maintenance(self, completion_time: datetime) -> None:
        """Reset service interval counter and hold vehicle in workshop bay until completion_time."""
        self.km_since_service = 0.0
        self.maintenance_until = completion_time
        self.available_at = max(self.available_at, completion_time)

    def idle_minutes(self, req_time: datetime) -> float:
        """Number of minutes this driver has been waiting since previous availability."""
        if self.available_at == datetime.min:
            return 999.0
        return max(0.0, (req_time - self.available_at).total_seconds() / 60.0)

    def cruise_to(self, target_node: int, available_time: datetime) -> None:
        """Reposition driver to a new street node while idle."""
        self.current_node = target_node
        self.available_at = available_time

    def assign_trip(self, destination_node: int, available_time: datetime) -> None:
        """Update driver's spatial position and busy clock upon completing or handling a trip."""
        self.current_node = destination_node
        self.available_at = available_time


@dataclass
class RiderPersona:
    """Distinct urban commuter routine and behavioral profile."""

    archetype: str # oficinista, estudiante, comerciante, salud_servicios, compras_hogar, vida_nocturna
    home_zone_id: int
    home_quadrant_id: int
    home_node: int
    home_lat: float
    home_lon: float
    anchor_zone_id: int
    anchor_quadrant_id: int
    anchor_node: int
    anchor_lat: float
    anchor_lon: float
    commute_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    outbound_hours: list[int] = field(default_factory=lambda: [7, 8])
    return_hours: list[int] = field(default_factory=lambda: [17, 18])
    routine_probability: float = 0.70


@dataclass
class RiderAgent:
    """Urban commuter requesting mobility services."""

    user_id: int
    user_model: User
    registration_date: date
    preferred_payment_method: str
    base_weight: float = 1.0
    persona: RiderPersona | None = None

    def is_registered_on(self, target_date: date) -> bool:
        """Verify user registration date constraint."""
        return self.registration_date <= target_date
