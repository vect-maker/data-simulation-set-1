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
SELECT 'zonas_urbanas' AS tabla, COUNT(*) AS total_registros FROM zonas_urbanas
UNION ALL
SELECT 'usuarios', COUNT(*) FROM usuarios
UNION ALL
SELECT 'conductores', COUNT(*) FROM conductores
UNION ALL
SELECT 'campanas_incentivos', COUNT(*) FROM campanas_incentivos
UNION ALL
SELECT 'clima_cuadrantes', COUNT(*) FROM clima_cuadrantes
UNION ALL
SELECT 'viajes', COUNT(*) FROM viajes
UNION ALL
SELECT 'telemetria_conductores', COUNT(*) FROM telemetria_conductores;

-- ------------------------------------------------------------------------------
-- 2. Análisis de Matriz Origen-Destino y Coordenadas GPS en Vías de Managua
-- ------------------------------------------------------------------------------
SELECT 
    zo.nombre_zona AS origen,
    zd.nombre_zona AS destino,
    COUNT(v.id_viaje) AS total_viajes,
    ROUND(AVG(v.distancia_km)::numeric, 2) AS distancia_promedio_km,
    ROUND(AVG(v.duracion_minutos)::numeric, 2) AS duracion_promedio_min,
    ROUND(AVG(v.tarifa_final)::numeric, 2) AS tarifa_promedio_nio
FROM viajes v
JOIN zonas_urbanas zo ON v.id_zona_origen = zo.id_zona
JOIN zonas_urbanas zd ON v.id_zona_destino = zd.id_zona
WHERE v.estado_viaje = 'completado'
GROUP BY zo.nombre_zona, zd.nombre_zona
ORDER BY total_viajes DESC
LIMIT 10;

-- ------------------------------------------------------------------------------
-- 3. Prueba de Desglose Tarifario y Función Determinista: fn_liquidar_tarifa_viaje
-- Valida: tarifa_base = tarifa_bajada_bandera + cargo_distancia + cargo_tiempo
--         tarifa_final = ROUND(tarifa_base * multiplicador_dinamico, 2)
-- ------------------------------------------------------------------------------
SELECT 
    v.id_viaje,
    v.tarifa_bajada_bandera,
    v.cargo_distancia,
    v.cargo_tiempo,
    v.tarifa_base,
    v.multiplicador_dinamico,
    v.tarifa_final AS tarifa_registrada,
    ROUND(fn_liquidar_tarifa_viaje(
        v.tarifa_bajada_bandera,
        v.distancia_km,
        v.duracion_minutos,
        v.multiplicador_dinamico
    )::numeric, 2) AS tarifa_calculada_plpgsql,
    ROUND(ABS(v.tarifa_final - fn_liquidar_tarifa_viaje(
        v.tarifa_bajada_bandera,
        v.distancia_km,
        v.duracion_minutos,
        v.multiplicador_dinamico
    ))::numeric, 2) AS discrepancia
FROM viajes v
WHERE v.estado_viaje = 'completado'
LIMIT 5;

-- ------------------------------------------------------------------------------
-- 4. Análisis Micro-Conductual de Cancelaciones y Equilibrio Oferta/Demanda
-- ------------------------------------------------------------------------------
SELECT
    v.motivo_cancelacion,
    v.estado_viaje,
    COUNT(*) AS total_cancelados,
    ROUND(AVG(v.multiplicador_dinamico)::numeric, 2) AS surge_promedio,
    ROUND(AVG(v.tiempo_espera_minutos)::numeric, 2) AS espera_promedio_min,
    ROUND(AVG(v.solicitudes_activas_origen)::numeric, 1) AS demanda_activa_dt,
    ROUND(AVG(v.conductores_disponibles_origen)::numeric, 1) AS oferta_conductores_st
FROM viajes v
WHERE v.estado_viaje IN ('cancelado_usuario', 'cancelado_conductor')
GROUP BY v.motivo_cancelacion, v.estado_viaje
ORDER BY total_cancelados DESC;

-- ------------------------------------------------------------------------------
-- 5. Consulta a la Vista Materializada: mv_kpis_movilidad_horaria
-- ------------------------------------------------------------------------------
SELECT 
    fecha,
    hora_del_dia,
    total_solicitudes,
    viajes_completados,
    ROUND(tasa_cancelacion_pct::numeric, 2) AS cancelacion_pct,
    ROUND(multiplicador_medio::numeric, 2) AS surge_medio,
    ROUND(ingreso_bruto_nio::numeric, 2) AS facturacion_nio
FROM mv_kpis_movilidad_horaria
ORDER BY fecha DESC, hora_del_dia ASC
LIMIT 15;

REFRESH MATERIALIZED VIEW mv_kpis_movilidad_horaria;

-- ------------------------------------------------------------------------------
-- 6. Dataset de Handoff para Estadística II: Lluvia vs Demanda y Multiplicador
-- ------------------------------------------------------------------------------
SELECT 
    DATE(v.fecha_hora_solicitud) AS fecha,
    c.precipitacion_mm,
    c.indice_congestion_pct,
    COUNT(v.id_viaje) AS viajes_solicitados,
    ROUND(AVG(v.multiplicador_dinamico)::numeric, 3) AS multiplicador_promedio,
    ROUND(SUM(v.tarifa_total_nio)::numeric, 2) AS facturacion_total_nio
FROM viajes v
LEFT JOIN clima_cuadrantes c ON DATE(v.fecha_hora_solicitud) = c.fecha AND v.id_zona_origen = c.id_zona
GROUP BY DATE(v.fecha_hora_solicitud), c.precipitacion_mm, c.indice_congestion_pct
ORDER BY fecha;
