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
    ) -> None:
        """Update vehicle wear metrics, cumulative odometer, and flood exposures."""
        self.odometer_km = round(self.odometer_km + distance_km, 2)
        self.km_since_service = round(self.km_since_service + distance_km, 2)
        self.cumulative_fuel_liters = round(self.cumulative_fuel_liters + fuel_liters, 2)
        if flooded:
            self.flood_exposure_count += 1

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
