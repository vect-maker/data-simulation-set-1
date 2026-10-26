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

    @property
    def is_operational(self) -> bool:
        """Driver is operational if not permanently inactive."""
        return self.status != "inactivo"

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
        """Driver is dispatchable if on duty, not in meal break, and available."""
        return (
            self.is_on_duty(req_time)
            and not self.is_in_meal_break(req_time)
            and self.is_available_at(req_time)
        )

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
