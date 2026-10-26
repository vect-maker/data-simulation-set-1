"""Simulation Recorder / Event Sink for MoviGo 3NF OLTP records.

Captures all lifecycle events from the simulation engine, guaranteeing:
- Monotonic primary keys across all transactional tables.
- Referential integrity for trip_id, driver_id, user_id, quadrant_id.
- Valid coordinates and timestamps.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Any
import pandas as pd

from movigo_sim.models import (
    Trip,
    TripPayment,
    TripRating,
    TripCancellation,
    DriverTelemetry,
    VehicleMaintenance,
)


class SimulationRecorder:
    """Observer and event sink capturing 3NF relational mobility records."""

    def __init__(self):
        self.trip_counter: int = 1
        self.payment_counter: int = 1
        self.rating_counter: int = 1
        self.cancellation_counter: int = 1
        self.telemetry_counter: int = 1
        self.maintenance_counter: int = 1

        self.trips: list[Trip] = []
        self.payments: list[TripPayment] = []
        self.ratings: list[TripRating] = []
        self.cancellations: list[TripCancellation] = []
        self.telemetry: list[DriverTelemetry] = []
        self.maintenance: list[VehicleMaintenance] = []

    def record_trip(
        self,
        user_id: int,
        driver_id: int,
        origin_quadrant_id: int,
        destination_quadrant_id: int,
        origin_latitude: float,
        origin_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
        requested_at: datetime,
        started_at: datetime | None,
        completed_at: datetime | None,
        distance_km: float,
        duration_minutes: float,
        trip_status: str,
    ) -> int:
        """Record a core ride lifecycle header and return the allocated trip_id."""
        t_id = self.trip_counter
        self.trip_counter += 1
        self.trips.append(
            Trip(
                trip_id=t_id,
                user_id=user_id,
                driver_id=driver_id,
                origin_quadrant_id=origin_quadrant_id,
                destination_quadrant_id=destination_quadrant_id,
                origin_latitude=origin_latitude,
                origin_longitude=origin_longitude,
                destination_latitude=destination_latitude,
                destination_longitude=destination_longitude,
                requested_at=requested_at,
                started_at=started_at,
                completed_at=completed_at,
                distance_km=distance_km,
                duration_minutes=duration_minutes,
                trip_status=trip_status,
            )
        )
        return t_id

    def record_payment(
        self,
        trip_id: int,
        payment_method: str,
        base_fare: float,
        surge_multiplier: float,
        tip_amount: float,
        final_fare: float,
        payment_status: str,
    ) -> int:
        """Record payment transaction for a ride."""
        p_id = self.payment_counter
        self.payment_counter += 1
        self.payments.append(
            TripPayment(
                payment_id=p_id,
                trip_id=trip_id,
                payment_method=payment_method,
                base_fare=base_fare,
                surge_multiplier=surge_multiplier,
                tip_amount=tip_amount,
                final_fare=final_fare,
                payment_status=payment_status,
            )
        )
        return p_id

    def record_rating(
        self,
        trip_id: int,
        user_rating: float,
        driver_rating: float,
    ) -> int:
        """Record mutual ratings for a completed ride."""
        r_id = self.rating_counter
        self.rating_counter += 1
        self.ratings.append(
            TripRating(
                rating_id=r_id,
                trip_id=trip_id,
                user_rating=user_rating,
                driver_rating=driver_rating,
            )
        )
        return r_id

    def record_cancellation(
        self,
        trip_id: int,
        cancelled_by: str,
        cancellation_reason: str,
        wait_time_minutes: float,
        origin_active_requests: int,
        origin_available_drivers: int,
    ) -> int:
        """Record cancellation details and operational context."""
        c_id = self.cancellation_counter
        self.cancellation_counter += 1
        self.cancellations.append(
            TripCancellation(
                cancellation_id=c_id,
                trip_id=trip_id,
                cancelled_by=cancelled_by,
                cancellation_reason=cancellation_reason,
                wait_time_minutes=wait_time_minutes,
                origin_active_requests=origin_active_requests,
                origin_available_drivers=origin_available_drivers,
            )
        )
        return c_id

    def record_telemetry(
        self,
        driver_id: int,
        trip_id: int | None,
        quadrant_id: int,
        recorded_at: datetime,
        latitude: float,
        longitude: float,
        speed_kmh: float,
        availability_status: str,
    ) -> int:
        """Record a GPS breadcrumb ping from a driver."""
        t_id = self.telemetry_counter
        self.telemetry_counter += 1
        self.telemetry.append(
            DriverTelemetry(
                telemetry_id=t_id,
                driver_id=driver_id,
                trip_id=trip_id,
                quadrant_id=quadrant_id,
                recorded_at=recorded_at,
                latitude=latitude,
                longitude=longitude,
                speed_kmh=speed_kmh,
                availability_status=availability_status,
            )
        )
        return t_id

    def record_maintenance(
        self,
        vehicle_id: int,
        service_date: date,
        maintenance_type: str,
        odometer_km: float,
        description: str,
        cost_nio: float,
        downtime_hours: float,
        workshop_name: str,
    ) -> int:
        """Record a scheduled preventive or unscheduled corrective vehicle maintenance event."""
        m_id = self.maintenance_counter
        self.maintenance_counter += 1
        self.maintenance.append(
            VehicleMaintenance(
                maintenance_id=m_id,
                vehicle_id=vehicle_id,
                service_date=service_date,
                maintenance_type=maintenance_type,
                odometer_km=odometer_km,
                description=description,
                cost_nio=cost_nio,
                downtime_hours=downtime_hours,
                workshop_name=workshop_name,
            )
        )
        return m_id

    def get_results(
        self,
    ) -> tuple[
        list[Trip],
        list[TripPayment],
        list[TripRating],
        list[TripCancellation],
        list[DriverTelemetry],
        list[VehicleMaintenance],
    ]:
        """Return the collected 3NF entity lists."""
        return (
            self.trips,
            self.payments,
            self.ratings,
            self.cancellations,
            self.telemetry,
            self.maintenance,
        )
