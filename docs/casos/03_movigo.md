# Guía del Proyecto: Caso 3 - MoviGo (Transporte Urbano por Aplicación - Managua)

## 1. Contexto del Negocio

**MoviGo** es una plataforma tecnológica de transporte urbano por aplicación móvil que conecta usuarios y conductores particulares en el casco metropolitano de **Managua, Nicaragua**. Opera servicios diferenciados: *MoviGo Estándar*, *MoviGo Comfort* y *MoviGo Moto*.

Principales desafíos operativos:
1. **Puntos Críticos de Tráfico:** Managua carece de transporte masivo guiado y depende de corredores viales centrales con rotondas críticas propensas a colapsos en horas pico (Rotonda Rubén Darío, Rotonda Centroamérica, Metrocentro, Pista Juan Pablo II).
2. **Impacto de Lluvias Torrenciales:** Las lluvias provocan corrientes y anegamientos en las partes bajas de la capital, lo que dispara exponencialmente la demanda de usuarios y reduce la oferta de conductores activos.
3. **Tarifa Dinámica (Surge Pricing):** Para equilibrar oferta y demanda en momentos de alta fricción, el algoritmo ajusta un multiplicador continuo ($1.0\times$ a $3.2\times$).
4. **Segmentación Socioeconómica:** Heterogeneidad en los métodos de pago (efectivo vs. tarjetas bancarias vs. billeteras móviles como Billetera Banpro/Kash) según el estrato socioeconómico de la zona de origen.

---

## 2. Diccionario de Datos Relacional 3NF (`raw_staging_movigo`)

| Tabla | Clave Primaria | Claves Foráneas | Descripción |
| :--- | :--- | :--- | :--- |
| `urban_zones` | `zone_id` | - | Las 12 zonas comerciales/residenciales de Managua (`socioeconomic_stratum`: alto, medio, popular, comercial) con tarifa base de bajada de bandera (`base_flag_drop_fare`). |
| `quadrants` | `quadrant_id` | `zone_id` | Grilla continua de 92 cuadrantes cuadrados (`~0.88 km × 0.88 km`) agrupados por zona urbana, con límites `lat_min..lat_max`, `lon_min..lon_max`, altitud media (`mean_altitude_masl`), riesgo de inundación (`flood_risk`) y cauces principales (`main_drainage_channels`). |
| `users` | `user_id` | - | Usuarios registrados, método de pago habitual (`preferred_payment_method`) y calificación (`average_rating`). |
| `drivers` | `driver_id` | - | Perfil operativo del conductor afiliado con calificación promedio (`average_rating`), tasa histórica de aceptación (`acceptance_rate_pct`) y estado (`status`). |
| `vehicles` | `vehicle_id` | `driver_id` | Unidad vehicular asignada al conductor con categoría de servicio (`service_type`), modelo (`vehicle_model`), año (`vehicle_year`) y matrícula (`license_plate`). |
| `incentive_campaigns` | `campaign_id` | `target_zone_id` | Programas estacionales de bonos a conductores vinculados a su zona objetivo (`target_zone_id`), con presupuesto (`budget_cost_nio`) y horas de conexión estimadas (`online_hours_increase`). |
| `quadrant_weather` | `weather_id` | `quadrant_id` | Serie horaria por cuadrante cuadrado con precipitación local (`precipitation_mm`), escorrentía de cauces (`channel_runoff_mm`), anegamiento vial (`flooded_roads`) e índice de congestión (`congestion_index`). |
| `trips` | `trip_id` | `user_id`, `driver_id`, `origin_quadrant_id`, `destination_quadrant_id` | Cabecera transaccional esbelta (3NF) de viajes con cuadrantes de origen/destino (las zonas se resuelven vía `quadrants.zone_id`), coordenadas GPS en vía pública (`origin_latitude`, `origin_longitude`, `destination_latitude`, `destination_longitude`), marcas de tiempo (`requested_at`, `started_at`, `completed_at`), distancia (`distance_km`), duración (`duration_minutes`) y estado (`trip_status`). |
| `trip_payments` | `payment_id` | `trip_id` | Transacción de liquidación y cobro del viaje: método de pago (`payment_method`), tarifa base (`base_fare`), multiplicador dinámico (`surge_multiplier`), propina (`tip_amount`), monto final (`final_fare`) y estado de pago (`payment_status`: `pagado` o `anulado`). |
| `trip_ratings` | `rating_id` | `trip_id` | Calificaciones bilaterales post-viaje (`user_rating`, `driver_rating`), registradas exclusivamente para viajes completados (`trip_status = 'completado'`). |
| `trip_cancellations` | `cancellation_id` | `trip_id` | Bitácora de cancelaciones (registrada exclusivamente para viajes cancelados) con actor (`cancelled_by`: `usuario` o `conductor`), motivo (`cancellation_reason`), tiempo de espera transcurrido (`wait_time_minutes`) e instantánea de fricción de mercado (`origin_active_requests`, `origin_available_drivers`). |
| `driver_telemetry` | `telemetry_id` | `driver_id`, `trip_id`, `quadrant_id` | Registros de trayectoria GPS en calles de Managua (`trip_id` nulo cuando está `disponible`, poblado durante `en_camino_recogida` y `ocupado`), velocidad instantánea (`speed_kmh`) y estado de disponibilidad (`availability_status`). |
| `trip_audit_logs` | `audit_id` | - | Tabla de auditoría poblada automáticamente ante transiciones de estado de viaje. |

---

## 3. Objetos Avanzados de Base de Datos

* **Trigger de Auditoría (`trg_audit_trips`):** Registra cambios en el estado del viaje (`trip_status`).
* **Función PL/pgSQL Determinista (`fn_calculate_trip_fare`):** Calcula la tarifa final en córdobas: $(FlagDropFare + km \cdot 18 + min \cdot 4.5) \cdot SurgeMultiplier$.
* **Vista Materializada Analítica (`mv_hourly_mobility_kpis`):** Agrupa métricas de movilidad por hora y estrato socioeconómico (uniendo `trips`, `quadrants`, `urban_zones` y `trip_payments`) con índices únicos para optimizar consultas de BI.

---

## 4. Retos y Entregables por Asignatura

### A. Bases de Datos Relacionales & Analíticas
1. Modelar el *Star Schema* en **dbt** (`fact_trips`, `dim_origin_zone`, `dim_destination_zone`, `dim_user`, `dim_driver`, `dim_time`) desnormalizando el esquema OLTP 3NF (`trips`, `trip_payments`, `trip_ratings`, `trip_cancellations`, `quadrants`, `urban_zones`, `drivers`, `vehicles`) y derivando el desglose tarifario (`flag_drop_fare`, `distance_charge`, `time_charge`) y el tiempo de espera (`wait_time_minutes`).
2. Implementar pruebas de integridad referencial y tests de dbt sobre tarifas no negativas y multiplicadores $\ge 1.0$.
3. Crear un dashboard en **Metabase** con mapas de calor de orígenes-destinos y horas con mayor tarifa dinámica.

### B. Shell Scripting (DataOps)
1. Desarrollar un script en Bash que monitoree la utilización de recursos de la base de datos y alerte ante aumentos bruscos de viajes cancelados.
2. Crear un pipeline de extracción periódica de viajes hacia archivos Parquet/CSV con sumas de comprobación SHA-256.

### C. Estadística II
1. **Regresión Lineal Simple y Múltiple:** Modelar la demanda diaria de viajes en función de la precipitación ($mm$) y el índice de congestión vial.
2. **Tabla ANOVA Completa:** Calcular la varianza explicada ($SCA$), residual ($SCE$) y el estadístico $F$.
3. **Verificación de Supuestos Gauss-Markov:** Evaluar normalidad (Shapiro-Wilk), homocedasticidad (Breusch-Pagan) e independencia temporal (Durbin-Watson).
4. **Pruebas de Hipótesis Formales:**
   - $t$-Student: ¿Eleva significativamente el multiplicador dinámico la tarifa media pagada por el usuario?
   - $z$-proporciones: ¿Es la tasa de cancelación en horas pico significativamente más alta que en horas valle?
   - ANOVA de un factor: ¿Varía la duración media de los viajes significativamente según el estrato socioeconómico de origen/destino?
5. **Prueba Ji-Cuadrado ($\chi^2$):** Demostrar la correlación entre el método de pago seleccionado (`trip_payments.payment_method`) y el estrato socioeconómico de la zona (`urban_zones.socioeconomic_stratum`, $p < 0.01$).

### D. Métodos Numéricos
1. **Búsqueda de Raíces:** Encontrar el multiplicador dinámico de equilibrio $m^*$ donde la función de exceso de demanda $f(m) = Demanda(m) - Oferta(m) = 0$ mediante los métodos de **Bisección** y **Newton-Raphson**.
2. **Diferenciación Numérica:** Evaluar la elasticidad-precio de la tarifa mediante diferencias finitas centradas de orden $\mathcal{O}(h^2)$ para determinar si la demanda de transporte en Managua es elástica o inelástica.
3. **Integración Numérica:** Estimar el volumen total de viajes completados a lo largo del día aplicando la regla de Simpson 1/3 sobre la función horaria de intensidad de viajes.

### E. Optimización
1. **Algoritmo Húngaro (Asignación):** Resolver el despacho óptimo que empareja conductores disponibles con viajes solicitados minimizando el tiempo total de llegada.
2. **Caminos Más Cortos (Dijkstra):** Encontrar la ruta óptima sobre el grafo vial de Managua comparando el tiempo estimado en condiciones secas vs. lluvia torrencial.
3. **Problema de la Mochila (Knapsack 0/1):** Maximizar las horas-hombre de conexión de conductores seleccionando el mejor portafolio de campañas de bonos bajo un presupuesto mensual limitado de C$ 120,000 NIO.

---

## 5. Consultas SQL de Inicio Rápido
Consulte el archivo `queries/03_movigo.sql` para ejemplos funcionales sobre PostgreSQL.
