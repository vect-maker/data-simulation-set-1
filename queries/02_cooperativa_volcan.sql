-- ==============================================================================
-- PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
-- Caso 2: Cooperativa El Volcán (Café de Exportación de Altura - Jinotega)
-- Archivo: queries/02_cooperativa_volcan.sql
-- Propósito: Consultas de referencia y validación de objetos de base de datos
-- ==============================================================================

SET search_path TO raw_staging_volcan, public;

-- ------------------------------------------------------------------------------
-- 1. Exploración Inicial y Verificación de Conteos de Tablas
-- ------------------------------------------------------------------------------
SELECT 'fincas' AS tabla, COUNT(*) AS total_registros FROM fincas
UNION ALL
SELECT 'variedades_cafe', COUNT(*) FROM variedades_cafe
UNION ALL
SELECT 'beneficios', COUNT(*) FROM beneficios
UNION ALL
SELECT 'cuadrillas_corte', COUNT(*) FROM cuadrillas_corte
UNION ALL
SELECT 'clima_zonas_cafetaleras', COUNT(*) FROM clima_zonas_cafetaleras
UNION ALL
SELECT 'lotes_acopio', COUNT(*) FROM lotes_acopio
UNION ALL
SELECT 'procesamiento_beneficio', COUNT(*) FROM procesamiento_beneficio
UNION ALL
SELECT 'subastas_especiales', COUNT(*) FROM subastas_especiales
UNION ALL
SELECT 'embarques_exportacion', COUNT(*) FROM embarques_exportacion;

-- ------------------------------------------------------------------------------
-- 2. Análisis de Rendimiento y Calidad por Región Cafetalera
-- ------------------------------------------------------------------------------
SELECT 
    f.region,
    COUNT(DISTINCT f.id_finca) AS total_fincas,
    ROUND(AVG(f.altitud_msnm), 1) AS altitud_media_msnm,
    COUNT(l.id_lote) AS total_lotes,
    ROUND(AVG(l.puntaje_catacion_scaa)::numeric, 2) AS scaa_promedio,
    ROUND(SUM(l.peso_bruto_quintales)::numeric, 2) AS volumen_total_qq
FROM fincas f
JOIN lotes_acopio l ON f.id_finca = l.id_finca
GROUP BY f.region
ORDER BY scaa_promedio DESC;

-- ------------------------------------------------------------------------------
-- 3. Demostración del Procedimiento Almacenado: sp_cerrar_etapa_beneficio
-- Actualiza merma, peso de salida y estado del proceso en transacción segura.
-- ------------------------------------------------------------------------------
-- A. Ver estado inicial de un proceso
SELECT id_proceso, id_lote, tipo_etapa, peso_entrada_qq, peso_salida_qq, estado_proceso
FROM procesamiento_beneficio
WHERE estado_proceso = 'en_proceso'
LIMIT 1;

-- B. Ejecutar el procedimiento almacenado (ejemplo con ID de proceso)
DO $$
DECLARE
    v_id VARCHAR(15);
BEGIN
    SELECT id_proceso INTO v_id 
    FROM procesamiento_beneficio 
    WHERE estado_proceso = 'en_proceso' 
    LIMIT 1;

    IF v_id IS NOT NULL THEN
        CALL sp_cerrar_etapa_beneficio(v_id, 4.5, 45.5);
        RAISE NOTICE 'Procedimiento ejecutado exitosamente para el proceso %', v_id;
    END IF;
END $$;

-- ------------------------------------------------------------------------------
-- 4. Demostración del Trigger de Auditoría de Lotes (trg_auditar_lotes)
-- ------------------------------------------------------------------------------
UPDATE lotes_acopio 
SET estado_lote = 'exportado'
WHERE id_lote = (SELECT id_lote FROM lotes_acopio LIMIT 1);

SELECT * FROM auditoria_lotes ORDER BY fecha_cambio DESC LIMIT 5;

-- ------------------------------------------------------------------------------
-- 5. Consulta a la Vista Materializada: mv_resumen_exportacion_pais
-- ------------------------------------------------------------------------------
SELECT 
    pais_destino,
    cliente_importador,
    total_embarques,
    total_sacos_69kg,
    ROUND(fob_total_usd::numeric, 2) AS total_exportado_usd,
    ROUND(precio_promedio_fob_libra::numeric, 2) AS precio_prom_fob_libra
FROM mv_resumen_exportacion_pais
ORDER BY fob_total_usd DESC;

REFRESH MATERIALIZED VIEW mv_resumen_exportacion_pais;

-- ------------------------------------------------------------------------------
-- 6. Dataset de Handoff para Estadística II: Altitud vs Puntaje SCAA
-- Alimenta la regresión lineal simple y las pruebas ANOVA por variedad botánica.
-- ------------------------------------------------------------------------------
SELECT 
    l.id_lote,
    f.nombre_finca,
    f.region,
    f.altitud_msnm,
    v.nombre_variedad,
    l.humedad_porcentaje,
    l.puntaje_catacion_scaa,
    l.precio_liquidado_qq_usd
FROM lotes_acopio l
JOIN fincas f ON l.id_finca = f.id_finca
JOIN variedades_cafe v ON l.id_variedad = v.id_variedad
ORDER BY f.altitud_msnm DESC;
