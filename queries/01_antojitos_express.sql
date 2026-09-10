-- ==============================================================================
-- PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
-- Caso 1: Antojitos Express (Cocina Fantasma y Delivery en Managua)
-- Archivo: queries/01_antojitos_express.sql
-- Propósito: Consultas de referencia y validación de objetos de base de datos
-- ==============================================================================

SET search_path TO raw_staging, public;

-- ------------------------------------------------------------------------------
-- 1. Exploración Inicial y Verificación de Conteos de Tablas
-- ------------------------------------------------------------------------------
SELECT 'zonas' AS tabla, COUNT(*) AS total_registros FROM zonas
UNION ALL
SELECT 'repartidores', COUNT(*) FROM repartidores
UNION ALL
SELECT 'categorias_platillo', COUNT(*) FROM categorias_platillo
UNION ALL
SELECT 'platillos', COUNT(*) FROM platillos
UNION ALL
SELECT 'promociones', COUNT(*) FROM promociones
UNION ALL
SELECT 'clima_diario', COUNT(*) FROM clima_diario
UNION ALL
SELECT 'ordenes', COUNT(*) FROM ordenes
UNION ALL
SELECT 'detalle_ordenes', COUNT(*) FROM detalle_ordenes;

-- ------------------------------------------------------------------------------
-- 2. Verificación de Integridad Referencial: Top 5 Platillos más Vendidos
-- ------------------------------------------------------------------------------
SELECT 
    p.nombre_platillo,
    c.nombre_categoria,
    SUM(d.cantidad) AS total_unidades,
    SUM(d.subtotal) AS ingreso_total_nio
FROM detalle_ordenes d
JOIN platillos p ON d.id_platillo = p.id_platillo
JOIN categorias_platillo c ON p.id_categoria = c.id_categoria
GROUP BY p.nombre_platillo, c.nombre_categoria
ORDER BY total_unidades DESC
LIMIT 5;

-- ------------------------------------------------------------------------------
-- 3. Prueba de la Función Almacenada: fn_calcular_total_orden
-- Recalcula el total de una orden consolidando subtotal de ítems, envío y propina.
-- ------------------------------------------------------------------------------
SELECT 
    o.id_orden,
    o.total_orden AS total_guardado,
    fn_calcular_total_orden(o.id_orden) AS total_calculado_plpgsql,
    ABS(o.total_orden - fn_calcular_total_orden(o.id_orden)) AS diferencia
FROM ordenes o
LIMIT 5;

-- ------------------------------------------------------------------------------
-- 4. Demostración del Trigger de Auditoría (trg_auditar_ordenes)
-- Al cambiar el estado de una orden, se debe registrar automáticamente en auditoria_ordenes.
-- ------------------------------------------------------------------------------
-- A. Ver estado inicial de una orden
SELECT id_orden, estado_orden FROM ordenes LIMIT 1;

-- B. Actualizar el estado para disparar el trigger
UPDATE ordenes 
SET estado_orden = 'entregada'
WHERE id_orden = (SELECT id_orden FROM ordenes LIMIT 1);

-- C. Consultar la tabla de auditoría para verificar la captura del evento
SELECT * FROM auditoria_ordenes ORDER BY fecha_cambio DESC LIMIT 5;

-- ------------------------------------------------------------------------------
-- 5. Demostración del Trigger de Validación Cronológica (trg_validar_cronologia_orden)
-- Este INSERT DEBE FALLAR con excepción porque fecha_hora_entrega es anterior a creacion.
-- ------------------------------------------------------------------------------
/*
INSERT INTO ordenes (
    id_orden, id_zona, id_repartidor, fecha_hora_creacion, fecha_hora_entrega,
    metodo_pago, estado_orden, total_orden, costo_envio, propina
) VALUES (
    999999, 1, 1, 
    '2024-06-15 14:00:00', '2024-06-15 13:00:00', -- Fecha de entrega anterior a creación!
    'efectivo', 'entregada', 250.00, 45.00, 10.00
);
-- ERROR esperado: Inconsistencia temporal: la fecha de entrega (...) no puede ser anterior a la creacion (...)
*/

-- ------------------------------------------------------------------------------
-- 6. Consulta a la Vista Materializada Analítica y Refresco
-- ------------------------------------------------------------------------------
SELECT 
    fecha,
    nombre_zona,
    total_pedidos,
    ingreso_bruto_nio,
    ROUND(tiempo_promedio_entrega_min::numeric, 2) AS tiempo_medio_entrega_min
FROM mv_resumen_diario_ventas
ORDER BY fecha DESC, total_pedidos DESC
LIMIT 10;

-- Refrescar la vista materializada tras nuevas inserciones
REFRESH MATERIALIZED VIEW mv_resumen_diario_ventas;

-- ------------------------------------------------------------------------------
-- 7. Dataset de Handoff para Estadística II: Lluvia vs Pedidos Diarios
-- Consulta que alimenta el modelo de regresión OLS y supuestos de Gauss-Markov.
-- ------------------------------------------------------------------------------
SELECT 
    c.fecha,
    c.precipitacion_mm,
    c.temperatura_c,
    c.condicion_cielo,
    COUNT(o.id_orden) AS total_pedidos_dia,
    COALESCE(SUM(o.total_orden), 0) AS ventas_diarias_nio
FROM clima_diario c
LEFT JOIN ordenes o ON c.fecha = DATE(o.fecha_hora_creacion)
GROUP BY c.fecha, c.precipitacion_mm, c.temperatura_c, c.condicion_cielo
ORDER BY c.fecha;
