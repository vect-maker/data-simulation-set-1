"""MoviGo simulation clock, background catch-up worker, and temporal validation manager."""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from fastapi import HTTPException
import psycopg2
from psycopg2.extras import execute_values

from src.api.database import get_db_connection, get_pool
from movigo_sim.generator import MoviGoSimulationEngine
from movigo_sim.weather_client import weather_client

logger = logging.getLogger("api.movigo_clock")

SCHEMA = "raw_staging_movigo"
ADVISORY_LOCK_ID = 742109


class MoviGoClockManager:
    """Manages the persistent simulation clock in PostgreSQL, background hourly simulation, and time-bound query validation."""

    def __init__(self) -> None:
        self.earliest_datetime: datetime = datetime(2024, 1, 1, 0, 0, 0)
        self.latest_datetime: datetime = datetime(2024, 1, 1, 0, 0, 0)
        self.current_status: str = "ready"
        self.total_hours_simulated: int = 0
        self.total_trips_simulated: int = 0
        self.is_leader: bool = False
        self._engine: MoviGoSimulationEngine | None = None
        self._running: bool = False
        self._max_ids: dict[str, int] = {
            "trip_id": 0,
            "payment_id": 0,
            "rating_id": 0,
            "cancellation_id": 0,
            "telemetry_id": 0,
            "maintenance_id": 0,
            "weather_id": 0,
        }

    def initialize_from_db(self) -> None:
        """Hydrate clock state and max entity IDs from PostgreSQL."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Ensure simulation_clock table exists
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {SCHEMA}.simulation_clock (
                            clock_id INT PRIMARY KEY DEFAULT 1,
                            earliest_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                            latest_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                            current_status VARCHAR(30) NOT NULL DEFAULT 'ready' CHECK (current_status IN ('ready', 'catching_up', 'hourly_wait')),
                            total_hours_simulated INT NOT NULL DEFAULT 0,
                            total_trips_simulated BIGINT NOT NULL DEFAULT 0,
                            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                            CONSTRAINT chk_single_clock_row CHECK (clock_id = 1)
                        );
                    """)

                    cur.execute(f"""
                        SELECT earliest_datetime, latest_datetime, current_status, total_hours_simulated, total_trips_simulated
                        FROM {SCHEMA}.simulation_clock
                        WHERE clock_id = 1;
                    """)
                    row = cur.fetchone()
                    if row:
                        self.earliest_datetime = row[0]
                        self.latest_datetime = row[1]
                        self.current_status = row[2]
                        self.total_hours_simulated = int(row[3])
                        self.total_trips_simulated = int(row[4])
                        logger.info(
                            "Loaded simulation_clock from DB: earliest=%s, latest=%s, status=%s, trips=%d",
                            self.earliest_datetime, self.latest_datetime, self.current_status, self.total_trips_simulated,
                        )
                    else:
                        # Inspect trips table for initial boundaries
                        cur.execute(f"""
                            SELECT 
                                COALESCE(MIN(requested_at), '2024-01-01 00:00:00'::timestamp),
                                COALESCE(MAX(requested_at), '2024-01-01 00:00:00'::timestamp),
                                COUNT(DISTINCT DATE_TRUNC('hour', requested_at)),
                                COUNT(*)
                            FROM {SCHEMA}.trips;
                        """)
                        t_min, t_max, h_count, t_count = cur.fetchone()
                        self.earliest_datetime = t_min
                        self.latest_datetime = t_max
                        self.total_hours_simulated = int(h_count or 0)
                        self.total_trips_simulated = int(t_count or 0)
                        self.current_status = "ready"

                        cur.execute(f"""
                            INSERT INTO {SCHEMA}.simulation_clock 
                            (clock_id, earliest_datetime, latest_datetime, current_status, total_hours_simulated, total_trips_simulated, updated_at)
                            VALUES (1, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (clock_id) DO UPDATE SET
                                earliest_datetime = EXCLUDED.earliest_datetime,
                                latest_datetime = EXCLUDED.latest_datetime,
                                current_status = EXCLUDED.current_status,
                                total_hours_simulated = EXCLUDED.total_hours_simulated,
                                total_trips_simulated = EXCLUDED.total_trips_simulated,
                                updated_at = NOW();
                        """, (self.earliest_datetime, self.latest_datetime, self.current_status, self.total_hours_simulated, self.total_trips_simulated))
                        logger.info(
                            "Bootstrapped simulation_clock in DB: earliest=%s, latest=%s",
                            self.earliest_datetime, self.latest_datetime,
                        )

                    # Retrieve maximum allocated IDs to guarantee monotonic sequence continuity
                    cur.execute(f"""
                        SELECT 
                            (SELECT COALESCE(MAX(trip_id), 0) FROM {SCHEMA}.trips),
                            (SELECT COALESCE(MAX(payment_id), 0) FROM {SCHEMA}.trip_payments),
                            (SELECT COALESCE(MAX(rating_id), 0) FROM {SCHEMA}.trip_ratings),
                            (SELECT COALESCE(MAX(cancellation_id), 0) FROM {SCHEMA}.trip_cancellations),
                            (SELECT COALESCE(MAX(telemetry_id), 0) FROM {SCHEMA}.driver_telemetry),
                            (SELECT COALESCE(MAX(maintenance_id), 0) FROM {SCHEMA}.vehicle_maintenance),
                            (SELECT COALESCE(MAX(weather_id), 0) FROM {SCHEMA}.quadrant_weather);
                    """)
                    id_row = cur.fetchone()
                    if id_row:
                        self._max_ids = {
                            "trip_id": int(id_row[0]),
                            "payment_id": int(id_row[1]),
                            "rating_id": int(id_row[2]),
                            "cancellation_id": int(id_row[3]),
                            "telemetry_id": int(id_row[4]),
                            "maintenance_id": int(id_row[5]),
                            "weather_id": int(id_row[6]),
                        }
                        logger.info("Allocated maximum entity IDs: %s", self._max_ids)
        except Exception as exc:
            logger.warning("Could not initialize simulation_clock from DB (will use defaults): %s", exc)

    def validate_time_bounds(self, start_time: datetime | None = None, end_time: datetime | None = None) -> None:
        """Validate requested time window against currently available simulation bounds."""
        if start_time is not None:
            # Handle naive vs aware
            st = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
            if st < self.earliest_datetime:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Parámetro 'start_time' ({st.isoformat()}) es anterior al límite inicial de datos "
                        f"disponibles ({self.earliest_datetime.isoformat()})."
                    ),
                )
            if st > self.latest_datetime:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Parámetro 'start_time' ({st.isoformat()}) aún no ha sido generado en la simulación. "
                        f"Límite máximo generado actual: {self.latest_datetime.isoformat()}."
                    ),
                )

        if end_time is not None:
            et = end_time.replace(tzinfo=None) if end_time.tzinfo else end_time
            if et > self.latest_datetime:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Parámetro 'end_time' ({et.isoformat()}) supera la última hora generada por la plataforma. "
                        f"Límite máximo generado actual: {self.latest_datetime.isoformat()}."
                    ),
                )
            if start_time is not None:
                st = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
                if et < st:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Parámetro 'end_time' ({et.isoformat()}) no puede ser anterior a 'start_time' ({st.isoformat()})."
                        ),
                    )

    def get_status(self) -> dict[str, Any]:
        """Return current simulation clock metadata."""
        now = datetime.now()
        target = now.replace(minute=0, second=0, microsecond=0)
        remaining_hours = max(0, int((target - self.latest_datetime).total_seconds() // 3600)) if self.latest_datetime else 0
        return {
            "case_name": "Caso 3: MoviGo (Transporte Urbano en Managua)",
            "current_status": self.current_status,
            "earliest_datetime": self.earliest_datetime.isoformat() if self.earliest_datetime else None,
            "latest_datetime": self.latest_datetime.isoformat() if self.latest_datetime else None,
            "target_datetime": target.isoformat(),
            "hours_remaining_catch_up": remaining_hours,
            "total_hours_simulated": self.total_hours_simulated,
            "total_trips_simulated": self.total_trips_simulated,
            "is_leader": self.is_leader,
        }

    def _persist_hourly_batch(
        self,
        target_dt: datetime,
        trips: list[Any],
        payments: list[Any],
        ratings: list[Any],
        cancellations: list[Any],
        telemetry: list[Any],
        maintenance: list[Any],
        weather: list[Any],
    ) -> None:
        """Atomically persist an hourly simulation batch and advance latest_datetime in PostgreSQL."""
        with get_db_connection() as conn:
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    # 1. Insert trips
                    if trips:
                        trip_rows = [
                            (
                                t.trip_id, t.user_id, t.driver_id, t.origin_quadrant_id, t.destination_quadrant_id,
                                t.origin_latitude, t.origin_longitude, t.destination_latitude, t.destination_longitude,
                                t.requested_at, t.started_at, t.completed_at, t.distance_km, t.duration_minutes, t.trip_status,
                            )
                            for t in trips
                        ]
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {SCHEMA}.trips (
                                trip_id, user_id, driver_id, origin_quadrant_id, destination_quadrant_id,
                                origin_latitude, origin_longitude, destination_latitude, destination_longitude,
                                requested_at, started_at, completed_at, distance_km, duration_minutes, trip_status
                            ) VALUES %s ON CONFLICT (trip_id) DO NOTHING;
                            """,
                            trip_rows,
                        )

                    # 2. Insert payments
                    if payments:
                        pay_rows = [
                            (
                                p.payment_id, p.trip_id, p.payment_method, p.base_fare, p.surge_multiplier,
                                p.tip_amount, p.final_fare, p.payment_status,
                            )
                            for p in payments
                        ]
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {SCHEMA}.trip_payments (
                                payment_id, trip_id, payment_method, base_fare, surge_multiplier, tip_amount, final_fare, payment_status
                            ) VALUES %s ON CONFLICT (payment_id) DO NOTHING;
                            """,
                            pay_rows,
                        )

                    # 3. Insert ratings
                    if ratings:
                        rat_rows = [(r.rating_id, r.trip_id, r.user_rating, r.driver_rating) for r in ratings]
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {SCHEMA}.trip_ratings (
                                rating_id, trip_id, user_rating, driver_rating
                            ) VALUES %s ON CONFLICT (rating_id) DO NOTHING;
                            """,
                            rat_rows,
                        )

                    # 4. Insert cancellations
                    if cancellations:
                        canc_rows = [
                            (
                                c.cancellation_id, c.trip_id, c.cancelled_by, c.cancellation_reason,
                                c.wait_time_minutes, c.origin_active_requests, c.origin_available_drivers,
                            )
                            for c in cancellations
                        ]
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {SCHEMA}.trip_cancellations (
                                cancellation_id, trip_id, cancelled_by, cancellation_reason,
                                wait_time_minutes, origin_active_requests, origin_available_drivers
                            ) VALUES %s ON CONFLICT (cancellation_id) DO NOTHING;
                            """,
                            canc_rows,
                        )

                    # 5. Insert telemetry
                    if telemetry:
                        tel_rows = [
                            (
                                tel.telemetry_id, tel.driver_id, tel.trip_id, tel.quadrant_id,
                                tel.recorded_at, tel.latitude, tel.longitude, tel.speed_kmh, tel.availability_status,
                            )
                            for tel in telemetry
                        ]
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {SCHEMA}.driver_telemetry (
                                telemetry_id, driver_id, trip_id, quadrant_id, recorded_at, latitude, longitude, speed_kmh, availability_status
                            ) VALUES %s ON CONFLICT (telemetry_id) DO NOTHING;
                            """,
                            tel_rows,
                        )

                    # 6. Insert maintenance
                    if maintenance:
                        maint_rows = [
                            (
                                m.maintenance_id, m.vehicle_id, m.service_date, m.maintenance_type,
                                m.odometer_km, m.description, m.cost_nio, m.downtime_hours, m.workshop_name,
                            )
                            for m in maintenance
                        ]
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {SCHEMA}.vehicle_maintenance (
                                maintenance_id, vehicle_id, service_date, maintenance_type,
                                odometer_km, description, cost_nio, downtime_hours, workshop_name
                            ) VALUES %s ON CONFLICT (maintenance_id) DO NOTHING;
                            """,
                            maint_rows,
                        )

                    # 7. Insert quadrant weather
                    if weather:
                        w_rows = [
                            (
                                w.weather_id, w.quadrant_id, w.recorded_at, w.date, w.hour,
                                w.precipitation_mm, w.channel_runoff_mm, w.temperature_c,
                                w.congestion_index, w.flooded_roads, w.sky_condition,
                            )
                            for w in weather
                        ]
                        execute_values(
                            cur,
                            f"""
                            INSERT INTO {SCHEMA}.quadrant_weather (
                                weather_id, quadrant_id, recorded_at, date, hour,
                                precipitation_mm, channel_runoff_mm, temperature_c,
                                congestion_index, flooded_roads, sky_condition
                            ) VALUES %s ON CONFLICT (weather_id) DO NOTHING;
                            """,
                            w_rows,
                        )

                    # 8. Advance simulation_clock atomically
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.simulation_clock
                        SET latest_datetime = %s,
                            current_status = %s,
                            total_hours_simulated = total_hours_simulated + 1,
                            total_trips_simulated = total_trips_simulated + %s,
                            updated_at = NOW()
                        WHERE clock_id = 1;
                        """,
                        (target_dt, self.current_status, len(trips)),
                    )

                conn.commit()
                self.latest_datetime = target_dt
                self.total_hours_simulated += 1
                self.total_trips_simulated += len(trips)
            except Exception as exc:
                conn.rollback()
                logger.error("Failed persisting hourly simulation batch for %s: %s", target_dt, exc)
                raise
            finally:
                conn.autocommit = True

    async def run(self) -> None:
        """Main background loop: acquires advisory lock and runs catch-up / real-time hourly simulation."""
        self._running = True
        logger.info("MoviGoClockManager background worker started.")

        # Give DB connection pool a brief moment to stabilize
        await asyncio.sleep(1.0)
        self.initialize_from_db()

        # Attempt to acquire advisory lock for leadership
        leader_conn = None
        try:
            pool = get_pool()
            leader_conn = pool.getconn()
            leader_conn.autocommit = True
            with leader_conn.cursor() as cur:
                cur.execute(f"SELECT pg_try_advisory_lock({ADVISORY_LOCK_ID});")
                locked = cur.fetchone()[0]
                if not locked:
                    logger.info("Another process holds the MoviGo simulation advisory lock. Running as replica.")
                    self.is_leader = False
                    return
                self.is_leader = True
                logger.info("Acquired PostgreSQL advisory lock (%d). Operating as simulation leader.", ADVISORY_LOCK_ID)
        except Exception as exc:
            logger.warning("Could not acquire advisory lock (standalone/test mode): %s", exc)
            self.is_leader = True

        # Initialize simulation engine
        self._engine = MoviGoSimulationEngine(random_seed=42)

        try:
            while self._running:
                now = datetime.now()
                target_hour = now.replace(minute=0, second=0, microsecond=0)

                # Check if we need to catch up
                if self.latest_datetime is None or self.latest_datetime < target_hour:
                    self.current_status = "catching_up"
                    next_dt = (
                        (self.latest_datetime + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                        if self.latest_datetime
                        else target_hour
                    )

                    logger.info("Catch-up: Simulating hour %s...", next_dt)
                    w = weather_client.get_hourly_weather(next_dt)

                    starting_ids = {k: v + 1 for k, v in self._max_ids.items()}
                    trips, payments, ratings, cancellations, telemetry, maintenance, weather_records = (
                        self._engine.simulate_hourly_slice(next_dt, w, starting_ids=starting_ids)
                    )

                    # Update internal tracking max IDs
                    if trips:
                        self._max_ids["trip_id"] = trips[-1].trip_id
                    if payments:
                        self._max_ids["payment_id"] = payments[-1].payment_id
                    if ratings:
                        self._max_ids["rating_id"] = ratings[-1].rating_id
                    if cancellations:
                        self._max_ids["cancellation_id"] = cancellations[-1].cancellation_id
                    if telemetry:
                        self._max_ids["telemetry_id"] = telemetry[-1].telemetry_id
                    if maintenance:
                        self._max_ids["maintenance_id"] = maintenance[-1].maintenance_id
                    if weather_records:
                        self._max_ids["weather_id"] = weather_records[-1].weather_id

                    # Persist batch to DB
                    self._persist_hourly_batch(
                        target_dt=next_dt,
                        trips=trips,
                        payments=payments,
                        ratings=ratings,
                        cancellations=cancellations,
                        telemetry=telemetry,
                        maintenance=maintenance,
                        weather=weather_records,
                    )

                    # Yield execution briefly for responsive event loop (accelerated catch-up)
                    await asyncio.sleep(0.05)
                else:
                    self.current_status = "ready"
                    # Calculate wait time until the next clock hour arrives
                    next_clock_hour = (now + timedelta(hours=1)).replace(minute=0, second=5, microsecond=0)
                    sleep_secs = max(5.0, min(300.0, (next_clock_hour - now).total_seconds()))
                    logger.debug("MoviGo clock caught up to real-time. Sleeping %.1fs until next hour.", sleep_secs)
                    await asyncio.sleep(sleep_secs)
        except asyncio.CancelledError:
            logger.info("MoviGoClockManager worker task was cancelled.")
        except Exception as exc:
            logger.error("Unhandled error in MoviGoClockManager worker loop: %s", exc, exc_info=True)
        finally:
            if leader_conn:
                try:
                    with leader_conn.cursor() as cur:
                        cur.execute(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_ID});")
                    pool.putconn(leader_conn)
                    logger.info("Released PostgreSQL advisory lock.")
                except Exception:
                    pass

    def stop(self) -> None:
        """Stop background worker loop."""
        self._running = False


# Global singleton clock manager
movigo_clock = MoviGoClockManager()
