"""Comprehensive SQL Audit Suite for MoviGo Simulation Data.

Uses DuckDB with the PostgreSQL extension attached to integrador_db
to execute deep relational, physical, temporal, spatial, and financial checks.
"""

from __future__ import annotations

import sys
import duckdb
from typing import Any, List, Dict


def create_connection():
    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(
        "ATTACH 'dbname=integrador_db user=postgres password=postgres host=localhost port=5432' AS pg (TYPE POSTGRES);"
    )
    return con


def run_check(
    con: duckdb.DuckDBPyConnection,
    category: str,
    title: str,
    query: str,
    expected_condition: str = "row_count == 0",
) -> Dict[str, Any]:
    try:
        df = con.execute(query).fetchdf()
        row_count = len(df)
        passed = (row_count == 0) if expected_condition == "row_count == 0" else eval(expected_condition, {"row_count": row_count, "df": df})
        
        sample = df.head(5).to_dict(orient="records") if row_count > 0 else []
        return {
            "category": category,
            "title": title,
            "query": query.strip(),
            "passed": passed,
            "row_count": row_count,
            "sample": sample,
            "error": None,
        }
    except Exception as e:
        return {
            "category": category,
            "title": title,
            "query": query.strip(),
            "passed": False,
            "row_count": -1,
            "sample": [],
            "error": str(e),
        }


def main():
    print("=" * 80)
    print("  MOVIGO SIMULATION DATA AUDIT - DUCKDB & POSTGRES EXTENSION")
    print("=" * 80)

    con = create_connection()
    checks: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. REFERENTIAL INTEGRITY & CARDINALITY (3NF)
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Referential Integrity",
        "Orphan Trips (invalid user_id)",
        """
        SELECT t.trip_id, t.user_id 
        FROM pg.raw_staging_movigo.trips t
        LEFT JOIN pg.raw_staging_movigo.users u ON t.user_id = u.user_id
        WHERE u.user_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Referential Integrity",
        "Orphan Trips (invalid driver_id when assigned)",
        """
        SELECT t.trip_id, t.driver_id 
        FROM pg.raw_staging_movigo.trips t
        LEFT JOIN pg.raw_staging_movigo.drivers d ON t.driver_id = d.driver_id
        WHERE t.driver_id IS NOT NULL AND d.driver_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Referential Integrity",
        "Orphan Trips (invalid origin or destination quadrant)",
        """
        SELECT t.trip_id, t.origin_quadrant_id, t.destination_quadrant_id
        FROM pg.raw_staging_movigo.trips t
        LEFT JOIN pg.raw_staging_movigo.quadrants qo ON t.origin_quadrant_id = qo.quadrant_id
        LEFT JOIN pg.raw_staging_movigo.quadrants qd ON t.destination_quadrant_id = qd.quadrant_id
        WHERE qo.quadrant_id IS NULL OR qd.quadrant_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Referential Integrity",
        "Orphan Payments (invalid trip_id)",
        """
        SELECT p.payment_id, p.trip_id 
        FROM pg.raw_staging_movigo.trip_payments p
        LEFT JOIN pg.raw_staging_movigo.trips t ON p.trip_id = t.trip_id
        WHERE t.trip_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Referential Integrity",
        "Orphan Ratings (invalid trip_id)",
        """
        SELECT r.rating_id, r.trip_id 
        FROM pg.raw_staging_movigo.trip_ratings r
        LEFT JOIN pg.raw_staging_movigo.trips t ON r.trip_id = t.trip_id
        WHERE t.trip_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Referential Integrity",
        "Orphan Cancellations (invalid trip_id)",
        """
        SELECT c.cancellation_id, c.trip_id 
        FROM pg.raw_staging_movigo.trip_cancellations c
        LEFT JOIN pg.raw_staging_movigo.trips t ON c.trip_id = t.trip_id
        WHERE t.trip_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Referential Integrity",
        "Orphan Telemetry (invalid driver_id or quadrant_id)",
        """
        SELECT tel.telemetry_id, tel.driver_id, tel.quadrant_id
        FROM pg.raw_staging_movigo.driver_telemetry tel
        LEFT JOIN pg.raw_staging_movigo.drivers d ON tel.driver_id = d.driver_id
        LEFT JOIN pg.raw_staging_movigo.quadrants q ON tel.quadrant_id = q.quadrant_id
        WHERE d.driver_id IS NULL OR q.quadrant_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Referential Integrity",
        "Quadrant to Urban Zone Integrity",
        """
        SELECT q.quadrant_id, q.zone_id 
        FROM pg.raw_staging_movigo.quadrants q
        LEFT JOIN pg.raw_staging_movigo.urban_zones z ON q.zone_id = z.zone_id
        WHERE z.zone_id IS NULL;
        """
    ))

    # -------------------------------------------------------------------------
    # 2. STATUS & BUSINESS LOGIC CARDINALITY
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Business Logic Cardinality",
        "Duplicate Payments for a single trip",
        """
        SELECT trip_id, COUNT(*) as cnt 
        FROM pg.raw_staging_movigo.trip_payments
        GROUP BY trip_id
        HAVING COUNT(*) > 1;
        """
    ))

    checks.append(run_check(
        con,
        "Business Logic Cardinality",
        "Completed trips without exactly 1 payment record",
        """
        SELECT t.trip_id, t.trip_status, COUNT(p.payment_id) as p_cnt
        FROM pg.raw_staging_movigo.trips t
        LEFT JOIN pg.raw_staging_movigo.trip_payments p ON t.trip_id = p.trip_id
        WHERE t.trip_status = 'completado'
        GROUP BY t.trip_id, t.trip_status
        HAVING COUNT(p.payment_id) != 1;
        """
    ))

    checks.append(run_check(
        con,
        "Business Logic Cardinality",
        "Cancelled trips with rating records (Ratings on non-completed trips)",
        """
        SELECT t.trip_id, t.trip_status, r.rating_id
        FROM pg.raw_staging_movigo.trips t
        INNER JOIN pg.raw_staging_movigo.trip_ratings r ON t.trip_id = r.trip_id
        WHERE t.trip_status != 'completado';
        """
    ))

    checks.append(run_check(
        con,
        "Business Logic Cardinality",
        "Completed trips with cancellation records",
        """
        SELECT t.trip_id, t.trip_status, c.cancellation_id
        FROM pg.raw_staging_movigo.trips t
        INNER JOIN pg.raw_staging_movigo.trip_cancellations c ON t.trip_id = c.trip_id
        WHERE t.trip_status = 'completado';
        """
    ))

    checks.append(run_check(
        con,
        "Business Logic Cardinality",
        "Cancelled trips missing cancellation details",
        """
        SELECT t.trip_id, t.trip_status
        FROM pg.raw_staging_movigo.trips t
        LEFT JOIN pg.raw_staging_movigo.trip_cancellations c ON t.trip_id = c.trip_id
        WHERE t.trip_status LIKE 'cancelado%' AND c.cancellation_id IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "Business Logic Cardinality",
        "Completed trips with NULL completed_at or NULL driver_id",
        """
        SELECT trip_id, trip_status, driver_id, completed_at
        FROM pg.raw_staging_movigo.trips
        WHERE trip_status = 'completado' AND (completed_at IS NULL OR driver_id IS NULL);
        """
    ))

    # -------------------------------------------------------------------------
    # 3. SPATIAL CONSISTENCY & BOUNDS
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Spatial Integrity",
        "Trips with Origin coordinates outside assigned Quadrant bounding box",
        """
        SELECT t.trip_id, t.origin_quadrant_id, t.origin_latitude, t.origin_longitude,
               q.lat_min, q.lat_max, q.lon_min, q.lon_max
        FROM pg.raw_staging_movigo.trips t
        JOIN pg.raw_staging_movigo.quadrants q ON t.origin_quadrant_id = q.quadrant_id
        WHERE t.origin_latitude < q.lat_min - 0.0001
           OR t.origin_latitude > q.lat_max + 0.0001
           OR t.origin_longitude < q.lon_min - 0.0001
           OR t.origin_longitude > q.lon_max + 0.0001;
        """
    ))

    checks.append(run_check(
        con,
        "Spatial Integrity",
        "Trips with Destination coordinates outside assigned Quadrant bounding box",
        """
        SELECT t.trip_id, t.destination_quadrant_id, t.destination_latitude, t.destination_longitude,
               q.lat_min, q.lat_max, q.lon_min, q.lon_max
        FROM pg.raw_staging_movigo.trips t
        JOIN pg.raw_staging_movigo.quadrants q ON t.destination_quadrant_id = q.quadrant_id
        WHERE t.destination_latitude < q.lat_min - 0.0001
           OR t.destination_latitude > q.lat_max + 0.0001
           OR t.destination_longitude < q.lon_min - 0.0001
           OR t.destination_longitude > q.lon_max + 0.0001;
        """
    ))

    checks.append(run_check(
        con,
        "Spatial Integrity",
        "Driver Telemetry coordinates outside assigned Quadrant bounds",
        """
        SELECT d.telemetry_id, d.quadrant_id, d.latitude, d.longitude,
               q.lat_min, q.lat_max, q.lon_min, q.lon_max
        FROM pg.raw_staging_movigo.driver_telemetry d
        JOIN pg.raw_staging_movigo.quadrants q ON d.quadrant_id = q.quadrant_id
        WHERE d.latitude < q.lat_min - 0.0001
           OR d.latitude > q.lat_max + 0.0001
           OR d.longitude < q.lon_min - 0.0001
           OR d.longitude > q.lon_max + 0.0001;
        """
    ))

    checks.append(run_check(
        con,
        "Spatial Integrity",
        "Zero distance trips with identical origin and destination coordinates",
        """
        SELECT trip_id, trip_status, distance_km, origin_latitude, destination_latitude,
               origin_longitude, destination_longitude
        FROM pg.raw_staging_movigo.trips
        WHERE (distance_km <= 0.05 OR (origin_latitude = destination_latitude AND origin_longitude = destination_longitude))
          AND trip_status = 'completado';
        """
    ))

    checks.append(run_check(
        con,
        "Spatial Integrity",
        "Trips outside Managua Municipal envelope (lat: 12.030-12.185, lon: -86.350 to -86.130)",
        """
        SELECT trip_id, origin_latitude, origin_longitude, destination_latitude, destination_longitude
        FROM pg.raw_staging_movigo.trips
        WHERE origin_latitude < 12.030 OR origin_latitude > 12.185
           OR destination_latitude < 12.030 OR destination_latitude > 12.185
           OR origin_longitude < -86.350 OR origin_longitude > -86.130
           OR destination_longitude < -86.350 OR destination_longitude > -86.130;
        """
    ))

    # -------------------------------------------------------------------------
    # 4. TEMPORAL CONSISTENCY
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Temporal Integrity",
        "Temporal inversion: requested_at > started_at",
        """
        SELECT trip_id, requested_at, started_at
        FROM pg.raw_staging_movigo.trips
        WHERE started_at IS NOT NULL AND requested_at > started_at;
        """
    ))

    checks.append(run_check(
        con,
        "Temporal Integrity",
        "Temporal inversion: started_at > completed_at",
        """
        SELECT trip_id, started_at, completed_at
        FROM pg.raw_staging_movigo.trips
        WHERE completed_at IS NOT NULL AND started_at > completed_at;
        """
    ))

    checks.append(run_check(
        con,
        "Temporal Integrity",
        "Trip duration does not match completed_at - started_at",
        """
        SELECT trip_id, started_at, completed_at, duration_minutes,
               ROUND(EXTRACT(EPOCH FROM (completed_at - started_at)) / 60.0, 2) as delta_minutes
        FROM pg.raw_staging_movigo.trips
        WHERE trip_status = 'completado'
          AND ABS(duration_minutes - ROUND(EXTRACT(EPOCH FROM (completed_at - started_at)) / 60.0, 2)) > 0.1;
        """
    ))

    # -------------------------------------------------------------------------
    # 5. KINEMATICS & PHYSICS
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Physical Plausibility",
        "Unrealistic vehicle speed (> 110 km/h or < 2 km/h for completed trips)",
        """
        SELECT trip_id, distance_km, duration_minutes,
               ROUND((distance_km / (duration_minutes / 60.0)), 2) as implied_speed_kmh
        FROM pg.raw_staging_movigo.trips
        WHERE trip_status = 'completado'
          AND duration_minutes > 0
          AND (
            (distance_km / (duration_minutes / 60.0)) > 110.0
            OR (distance_km / (duration_minutes / 60.0)) < 2.0
          );
        """
    ))

    checks.append(run_check(
        con,
        "Physical Plausibility",
        "Unrealistic telemetry speed (< 0 or > 120 km/h)",
        """
        SELECT telemetry_id, driver_id, speed_kmh
        FROM pg.raw_staging_movigo.driver_telemetry
        WHERE speed_kmh < 0 OR speed_kmh > 120;
        """
    ))

    checks.append(run_check(
        con,
        "Physical Plausibility",
        "Concurrent overlapping trips for the same driver",
        """
        SELECT t1.driver_id, t1.trip_id as trip1, t2.trip_id as trip2,
               t1.started_at as t1_start, t1.completed_at as t1_end,
               t2.started_at as t2_start, t2.completed_at as t2_end
        FROM pg.raw_staging_movigo.trips t1
        JOIN pg.raw_staging_movigo.trips t2 
          ON t1.driver_id = t2.driver_id 
         AND t1.trip_id < t2.trip_id
         AND t1.trip_status = 'completado' 
         AND t2.trip_status = 'completado'
         AND t1.started_at < t2.completed_at 
         AND t2.started_at < t1.completed_at;
        """
    ))

    # -------------------------------------------------------------------------
    # 6. FINANCIAL & FARE CONSISTENCY (3NF trip_payments)
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Financial Consistency",
        "Completed trips with non-positive final_fare in trip_payments",
        """
        SELECT t.trip_id, t.trip_status, p.final_fare
        FROM pg.raw_staging_movigo.trips t
        JOIN pg.raw_staging_movigo.trip_payments p ON t.trip_id = p.trip_id
        WHERE t.trip_status = 'completado' AND (p.final_fare IS NULL OR p.final_fare <= 0);
        """
    ))

    checks.append(run_check(
        con,
        "Financial Consistency",
        "Discrepancy in final_fare math: (base_fare * surge) + tip != final_fare",
        """
        SELECT payment_id, trip_id, base_fare, surge_multiplier, tip_amount, final_fare,
               ROUND((base_fare * surge_multiplier) + tip_amount, 2) as expected_fare
        FROM pg.raw_staging_movigo.trip_payments
        WHERE payment_status = 'completado'
          AND ABS(final_fare - ROUND((base_fare * surge_multiplier) + tip_amount, 2)) > 0.05;
        """
    ))

    checks.append(run_check(
        con,
        "Financial Consistency",
        "Surge multiplier below 1.0 (anti-discount guard)",
        """
        SELECT payment_id, trip_id, surge_multiplier
        FROM pg.raw_staging_movigo.trip_payments
        WHERE surge_multiplier < 1.00;
        """
    ))

    checks.append(run_check(
        con,
        "Financial Consistency",
        "Cancelled trips with non-anulado payment status",
        """
        SELECT t.trip_id, t.trip_status, p.payment_status, p.final_fare
        FROM pg.raw_staging_movigo.trips t
        JOIN pg.raw_staging_movigo.trip_payments p ON t.trip_id = p.trip_id
        WHERE t.trip_status LIKE 'cancelado%'
          AND p.payment_status != 'anulado';
        """
    ))

    # -------------------------------------------------------------------------
    # 7. DISTRICT CONSISTENCY & GEOGRAPHIC SPREAD
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "District Consistency",
        "Quadrants with NULL or invalid district name",
        """
        SELECT quadrant_id, zone_id, district
        FROM pg.raw_staging_movigo.quadrants
        WHERE district IS NULL 
           OR district NOT IN ('Distrito I', 'Distrito II', 'Distrito III', 'Distrito IV', 'Distrito V', 'Distrito VI', 'Distrito VII');
        """
    ))

    checks.append(run_check(
        con,
        "District Consistency",
        "Quadrant district does not match Urban Zone district",
        """
        SELECT q.quadrant_id, q.district as q_dist, z.district as z_dist
        FROM pg.raw_staging_movigo.quadrants q
        JOIN pg.raw_staging_movigo.urban_zones z ON q.zone_id = z.zone_id
        WHERE q.district != z.district;
        """
    ))

    checks.append(run_check(
        con,
        "District Consistency",
        "All 7 districts present in Trip Origins",
        """
        WITH all_districts AS (
            SELECT unnest(['Distrito I', 'Distrito II', 'Distrito III', 'Distrito IV', 'Distrito V', 'Distrito VI', 'Distrito VII']) AS district
        ),
        active_districts AS (
            SELECT DISTINCT q.district
            FROM pg.raw_staging_movigo.trips t
            JOIN pg.raw_staging_movigo.quadrants q ON t.origin_quadrant_id = q.quadrant_id
        )
        SELECT d.district 
        FROM all_districts d
        LEFT JOIN active_districts a ON d.district = a.district
        WHERE a.district IS NULL;
        """
    ))

    checks.append(run_check(
        con,
        "District Consistency",
        "All 7 districts present in Trip Destinations",
        """
        WITH all_districts AS (
            SELECT unnest(['Distrito I', 'Distrito II', 'Distrito III', 'Distrito IV', 'Distrito V', 'Distrito VI', 'Distrito VII']) AS district
        ),
        active_districts AS (
            SELECT DISTINCT q.district
            FROM pg.raw_staging_movigo.trips t
            JOIN pg.raw_staging_movigo.quadrants q ON t.destination_quadrant_id = q.quadrant_id
        )
        SELECT d.district 
        FROM all_districts d
        LEFT JOIN active_districts a ON d.district = a.district
        WHERE a.district IS NULL;
        """
    ))

    # -------------------------------------------------------------------------
    # 8. HYDROLOGICAL & WEATHER INTEGRITY
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Hydrological & Weather",
        "Plausibility of Weather metrics (negative precip, extreme temps)",
        """
        SELECT weather_id, quadrant_id, temperature_c, precipitation_mm, channel_runoff_mm
        FROM pg.raw_staging_movigo.quadrant_weather
        WHERE precipitation_mm < 0 
           OR channel_runoff_mm < 0
           OR temperature_c < 15.0 
           OR temperature_c > 45.0
        LIMIT 10;
        """
    ))

    # -------------------------------------------------------------------------
    # 9. RATINGS BOUNDS & INTEGRITY
    # -------------------------------------------------------------------------
    checks.append(run_check(
        con,
        "Ratings Integrity",
        "Trip ratings out of bounds [1.0, 5.0]",
        """
        SELECT rating_id, trip_id, user_rating, driver_rating
        FROM pg.raw_staging_movigo.trip_ratings
        WHERE user_rating < 1.0 OR user_rating > 5.0
           OR driver_rating < 1.0 OR driver_rating > 5.0;
        """
    ))

    # Summarize and output
    total = len(checks)
    passed = sum(1 for c in checks if c["passed"])
    failed = total - passed

    print(f"\nAudit Execution Completed: {passed}/{total} Checks Passed ({failed} Failed)\n")
    print(f"{'Category':<25} | {'Check Title':<45} | {'Result':<8} | {'Rows/Anomalies'}")
    print("-" * 95)
    for c in checks:
        status_str = "PASS" if c["passed"] else "FAIL"
        print(f"{c['category']:<25} | {c['title'][:45]:<45} | {status_str:<8} | {c['row_count']}")
        if not c["passed"]:
            if c["error"]:
                print(f"    ERROR: {c['error']}")
            elif c["sample"]:
                print(f"    Sample anomalies ({len(c['sample'])}): {c['sample']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
