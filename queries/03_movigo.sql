-- ==============================================================================
-- PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
-- Caso 3: MoviGo (Transporte Urbano por Aplicación - Managua)
-- Archivo: queries/03_movigo.sql
-- Propósito: Consultas de referencia y validación de objetos de base de datos
-- ==============================================================================

SET search_path TO raw_staging_movigo, public;

-- ------------------------------------------------------------------------------
-- 1. Exploración Inicial y Verificación de Conteos de Tablas
-- ------------------------------------------------------------------------------
SELECT 'quadrants' AS table_name, COUNT(*) AS total_rows FROM quadrants
UNION ALL
SELECT 'urban_zones', COUNT(*) FROM urban_zones
UNION ALL
SELECT 'users', COUNT(*) FROM users
UNION ALL
SELECT 'drivers', COUNT(*) FROM drivers
UNION ALL
SELECT 'incentive_campaigns', COUNT(*) FROM incentive_campaigns
UNION ALL
SELECT 'quadrant_weather', COUNT(*) FROM quadrant_weather
UNION ALL
SELECT 'trips', COUNT(*) FROM trips
UNION ALL
SELECT 'driver_telemetry', COUNT(*) FROM driver_telemetry;

-- ------------------------------------------------------------------------------
-- 2. Análisis de Matriz Origen-Destino y Coordenadas GPS en Vías de Managua
-- ------------------------------------------------------------------------------
SELECT 
    zo.zone_name AS origin_zone,
    zd.zone_name AS destination_zone,
    COUNT(t.trip_id) AS total_trips,
    ROUND(AVG(t.distance_km)::numeric, 2) AS avg_distance_km,
    ROUND(AVG(t.duration_minutes)::numeric, 2) AS avg_duration_min,
    ROUND(AVG(t.final_fare)::numeric, 2) AS avg_fare_nio
FROM trips t
JOIN urban_zones zo ON t.origin_zone_id = zo.zone_id
JOIN urban_zones zd ON t.destination_zone_id = zd.zone_id
WHERE t.trip_status = 'completado'
GROUP BY zo.zone_name, zd.zone_name
ORDER BY total_trips DESC
LIMIT 10;

-- ------------------------------------------------------------------------------
-- 3. Prueba de Desglose Tarifario y Función Determinista: fn_calculate_trip_fare
-- Valida: base_fare = flag_drop_fare + distance_charge + time_charge
--         final_fare = ROUND(base_fare * surge_multiplier, 2)
-- ------------------------------------------------------------------------------
SELECT 
    t.trip_id,
    t.flag_drop_fare,
    t.distance_charge,
    t.time_charge,
    t.base_fare,
    t.surge_multiplier,
    t.final_fare AS recorded_fare,
    ROUND(fn_calculate_trip_fare(
        t.flag_drop_fare,
        t.distance_km,
        t.duration_minutes,
        t.surge_multiplier
    )::numeric, 2) AS calculated_fare_plpgsql,
    ROUND(ABS(t.final_fare - fn_calculate_trip_fare(
        t.flag_drop_fare,
        t.distance_km,
        t.duration_minutes,
        t.surge_multiplier
    ))::numeric, 2) AS discrepancy
FROM trips t
WHERE t.trip_status = 'completado'
LIMIT 5;

-- ------------------------------------------------------------------------------
-- 4. Análisis Micro-Conductual de Cancelaciones y Equilibrio Oferta/Demanda
-- ------------------------------------------------------------------------------
SELECT
    t.cancellation_reason,
    t.trip_status,
    COUNT(*) AS total_canceled,
    ROUND(AVG(t.surge_multiplier)::numeric, 2) AS avg_surge,
    ROUND(AVG(t.wait_time_minutes)::numeric, 2) AS avg_wait_min,
    ROUND(AVG(t.origin_active_requests)::numeric, 1) AS active_demand_dt,
    ROUND(AVG(t.origin_available_drivers)::numeric, 1) AS available_drivers_st
FROM trips t
WHERE t.trip_status IN ('cancelado_usuario', 'cancelado_conductor')
GROUP BY t.cancellation_reason, t.trip_status
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
-- 6. Dataset de Handoff Horario por Cuadrante: Lluvia, Escorrentía de Cauces y Demanda
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
    ROUND(AVG(t.surge_multiplier)::numeric, 3) AS avg_surge_multiplier,
    ROUND(SUM(t.final_fare)::numeric, 2) AS gross_revenue_nio
FROM trips t
JOIN urban_zones zo ON t.origin_zone_id = zo.zone_id
JOIN quadrants q ON t.origin_quadrant_id = q.quadrant_id
LEFT JOIN quadrant_weather w 
    ON q.quadrant_id = w.quadrant_id 
   AND DATE(t.requested_at) = w.date 
   AND EXTRACT(HOUR FROM t.requested_at)::int = w.hour
GROUP BY zo.zone_name, q.quadrant_code, q.flood_risk, w.date, w.hour, w.precipitation_mm, w.channel_runoff_mm, w.flooded_roads, w.congestion_index
ORDER BY w.date, w.hour, q.quadrant_code;
