-- ==============================================================================
-- PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
-- Caso 3: MoviGo (Transporte Urbano por Aplicación - Managua)
-- Archivo: queries/03_movigo.sql
-- Propósito: Consultas de referencia y validación sobre esquema OLTP 3NF
-- ==============================================================================

SET search_path TO raw_staging_movigo, public;

-- ------------------------------------------------------------------------------
-- 1. Exploración Inicial y Verificación de Conteos de Tablas (14 tablas OLTP 3NF)
-- ------------------------------------------------------------------------------
SELECT 'urban_zones' AS table_name, COUNT(*) AS total_rows FROM urban_zones
UNION ALL
SELECT 'quadrants', COUNT(*) FROM quadrants
UNION ALL
SELECT 'drainage_channels', COUNT(*) FROM drainage_channels
UNION ALL
SELECT 'users', COUNT(*) FROM users
UNION ALL
SELECT 'drivers', COUNT(*) FROM drivers
UNION ALL
SELECT 'vehicles', COUNT(*) FROM vehicles
UNION ALL
SELECT 'vehicle_maintenance', COUNT(*) FROM vehicle_maintenance
UNION ALL
SELECT 'incentive_campaigns', COUNT(*) FROM incentive_campaigns
UNION ALL
SELECT 'quadrant_weather', COUNT(*) FROM quadrant_weather
UNION ALL
SELECT 'trips', COUNT(*) FROM trips
UNION ALL
SELECT 'trip_payments', COUNT(*) FROM trip_payments
UNION ALL
SELECT 'trip_ratings', COUNT(*) FROM trip_ratings
UNION ALL
SELECT 'trip_cancellations', COUNT(*) FROM trip_cancellations
UNION ALL
SELECT 'driver_telemetry', COUNT(*) FROM driver_telemetry;

-- ------------------------------------------------------------------------------
-- 2. Análisis de Matriz Origen-Destino (Joins 3NF: trips -> quadrants -> urban_zones + trip_payments)
-- ------------------------------------------------------------------------------
SELECT 
    zo.zone_name AS origin_zone,
    zd.zone_name AS destination_zone,
    COUNT(t.trip_id) AS total_trips,
    ROUND(AVG(t.distance_km)::numeric, 2) AS avg_distance_km,
    ROUND(AVG(t.duration_minutes)::numeric, 2) AS avg_duration_min,
    ROUND(AVG(p.final_fare)::numeric, 2) AS avg_fare_nio
FROM trips t
JOIN quadrants qo ON t.origin_quadrant_id = qo.quadrant_id
JOIN urban_zones zo ON qo.zone_id = zo.zone_id
JOIN quadrants qd ON t.destination_quadrant_id = qd.quadrant_id
JOIN urban_zones zd ON qd.zone_id = zd.zone_id
JOIN trip_payments p ON t.trip_id = p.trip_id
WHERE t.trip_status = 'completado'
GROUP BY zo.zone_name, zd.zone_name
ORDER BY total_trips DESC
LIMIT 10;

-- ------------------------------------------------------------------------------
-- 3. Prueba de Desglose Tarifario Derivado en SQL y Función Determinista: fn_calculate_trip_fare
-- Deriva flag_drop_fare desde urban_zones, distance_charge (km * 18.0) y time_charge (min * 4.5)
-- ------------------------------------------------------------------------------
SELECT 
    t.trip_id,
    zo.base_flag_drop_fare AS derived_flag_drop_fare,
    ROUND((t.distance_km * 18.00)::numeric, 2) AS derived_distance_charge,
    ROUND((t.duration_minutes * 4.50)::numeric, 2) AS derived_time_charge,
    p.base_fare,
    p.surge_multiplier,
    p.final_fare AS recorded_fare,
    ROUND(fn_calculate_trip_fare(
        zo.base_flag_drop_fare,
        t.distance_km,
        t.duration_minutes,
        p.surge_multiplier
    )::numeric, 2) AS calculated_fare_plpgsql,
    ROUND(ABS(p.final_fare - fn_calculate_trip_fare(
        zo.base_flag_drop_fare,
        t.distance_km,
        t.duration_minutes,
        p.surge_multiplier
    ))::numeric, 2) AS discrepancy
FROM trips t
JOIN quadrants qo ON t.origin_quadrant_id = qo.quadrant_id
JOIN urban_zones zo ON qo.zone_id = zo.zone_id
JOIN trip_payments p ON t.trip_id = p.trip_id
WHERE t.trip_status = 'completado'
LIMIT 5;

-- ------------------------------------------------------------------------------
-- 4. Análisis Micro-Conductual de Cancelaciones y Equilibrio Oferta/Demanda (trip_cancellations + trip_payments)
-- ------------------------------------------------------------------------------
SELECT
    c.cancellation_reason,
    c.cancelled_by,
    t.trip_status,
    COUNT(*) AS total_canceled,
    ROUND(AVG(p.surge_multiplier)::numeric, 2) AS avg_surge,
    ROUND(AVG(c.wait_time_minutes)::numeric, 2) AS avg_wait_min,
    ROUND(AVG(c.origin_active_requests)::numeric, 1) AS active_demand_dt,
    ROUND(AVG(c.origin_available_drivers)::numeric, 1) AS available_drivers_st
FROM trip_cancellations c
JOIN trips t ON c.trip_id = t.trip_id
JOIN trip_payments p ON t.trip_id = p.trip_id
GROUP BY c.cancellation_reason, c.cancelled_by, t.trip_status
ORDER BY total_canceled DESC;

-- ------------------------------------------------------------------------------
-- 5. Consulta a la Vista Materializada: mv_hourly_mobility_kpis
-- ------------------------------------------------------------------------------
SELECT 
    hour_of_day,
    socioeconomic_stratum,
    total_requests,
    completed_trips,
    ROUND(avg_surge_multiplier::numeric, 2) AS avg_surge,
    ROUND(avg_fare_nio::numeric, 2) AS avg_fare_nio
FROM mv_hourly_mobility_kpis
ORDER BY hour_of_day ASC, socioeconomic_stratum ASC
LIMIT 15;

REFRESH MATERIALIZED VIEW mv_hourly_mobility_kpis;

-- ------------------------------------------------------------------------------
-- 6. Dataset de Handoff Horario por Cuadrante: Lluvia, Escorrentía de Cauces y Demanda (3NF Joins)
-- ------------------------------------------------------------------------------
SELECT 
    zo.zone_name AS origin_zone,
    q.quadrant_code,
    q.flood_risk,
    w.date,
    w.hour,
    w.precipitation_mm,
    w.channel_runoff_mm,
    w.flooded_roads,
    w.congestion_index,
    COUNT(t.trip_id) AS requested_trips,
    ROUND(AVG(p.surge_multiplier)::numeric, 3) AS avg_surge_multiplier,
    ROUND(SUM(p.final_fare)::numeric, 2) AS gross_revenue_nio
FROM trips t
JOIN quadrants q ON t.origin_quadrant_id = q.quadrant_id
JOIN urban_zones zo ON q.zone_id = zo.zone_id
JOIN trip_payments p ON t.trip_id = p.trip_id
LEFT JOIN quadrant_weather w 
    ON q.quadrant_id = w.quadrant_id 
   AND DATE(t.requested_at) = w.date 
   AND EXTRACT(HOUR FROM t.requested_at)::int = w.hour
GROUP BY zo.zone_name, q.quadrant_code, q.flood_risk, w.date, w.hour, w.precipitation_mm, w.channel_runoff_mm, w.flooded_roads, w.congestion_index
ORDER BY w.date, w.hour, q.quadrant_code;

-- ------------------------------------------------------------------------------
-- 7. Campañas Estacionales de Incentivos y Zonas Objetivo (incentive_campaigns -> urban_zones)
-- ------------------------------------------------------------------------------
SELECT
    ic.campaign_id,
    ic.bonus_name,
    ic.incentive_type,
    uz.zone_name AS target_zone,
    uz.socioeconomic_stratum,
    ic.budget_cost_nio,
    ic.online_hours_increase,
    ic.start_date,
    ic.end_date,
    ic.status
FROM incentive_campaigns ic
JOIN urban_zones uz ON ic.target_zone_id = uz.zone_id
ORDER BY ic.start_date ASC;

-- ------------------------------------------------------------------------------
-- 8. Mantenimiento Preventivo de Flota y Exposición a Cauces (vehicle_maintenance + vehicles)
-- ------------------------------------------------------------------------------
SELECT 
    v.service_type,
    v.vehicle_model,
    COUNT(m.service_id) AS total_services,
    SUM(CASE WHEN m.service_type = 'preventivo' THEN 1 ELSE 0 END) AS preventive_services,
    SUM(CASE WHEN m.service_type = 'correctivo' THEN 1 ELSE 0 END) AS corrective_services,
    ROUND(AVG(m.odometer_km)::numeric, 1) AS avg_odometer_km,
    ROUND(SUM(m.cost_nio)::numeric, 2) AS total_maintenance_cost_nio,
    ROUND(AVG(m.flood_exposure_trips)::numeric, 1) AS avg_flood_exposure_trips,
    ROUND(SUM(m.downtime_hours)::numeric, 1) AS total_downtime_hours
FROM vehicle_maintenance m
JOIN vehicles v ON m.vehicle_id = v.vehicle_id
GROUP BY v.service_type, v.vehicle_model
ORDER BY total_maintenance_cost_nio DESC;

-- ------------------------------------------------------------------------------
-- 9. Catálogo de Corredores de Drenaje Pluvial (OpenStreetMap waterways)
-- ------------------------------------------------------------------------------
SELECT 
    channel_id,
    channel_name,
    length_km,
    osm_way_count,
    base_flood_risk,
    osm_centroid_lat,
    osm_centroid_lon
FROM drainage_channels
ORDER BY length_km DESC;
