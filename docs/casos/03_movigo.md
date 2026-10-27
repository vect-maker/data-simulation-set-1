# Guía del Proyecto: Caso 3 - MoviGo (Transporte Urbano por Aplicación - Managua)

## 1. Contexto del Negocio

**MoviGo** es una plataforma tecnológica de transporte urbano por aplicación móvil y gestión de flota vehicular propia y tercerizada que conecta usuarios y conductores en el casco metropolitano de **Managua, Nicaragua**. La plataforma opera tres categorías diferenciadas de servicio: *MoviGo Estándar*, *MoviGo Comfort* y *MoviGo Moto*.

A diferencia de modelos convencionales de intermediación pura, MoviGo administra unidades automotrices como activos corporativos formales, asumiendo la gestión operativa del combustible, el desgaste por kilometraje y el mantenimiento preventivo y correctivo de la flota.

### Principales Desafíos Operativos y de Negocio

1. **Topografía e Impacto de Lluvias Torrenciales:** Managua presenta una pendiente descendente desde las sierras del sur hacia el Lago Xolotlán (de ~500 msnm a ~50 msnm), atravesada por una red de cauces naturales y revestidos que evacúan el drenaje pluvial. Durante la temporada lluviosa (mayo a noviembre), los aguaceros provocan intensas corrientes de escorrentía, anegamiento de vías críticas y cruces peligrosos, disparando la demanda de viajes y colapsando la oferta de conductores.
2. **Puntos Críticos de Fricción Vial:** La capital carece de transporte ferroviario masivo y depende de corredores viales principales con rotondas y pistas arteriales propensas a la saturación en horas pico (Rotonda Rubén Darío, Rotonda Centroamérica, Rotonda Cristo Rey, Pista Juan Pablo II, Metrocentro, Mercado Oriental).
3. **Tarifa Dinámica Adaptativa (*Surge Pricing*):** Para estabilizar el equilibrio entre la oferta vehicular y la demanda instantánea de pasajeros, un algoritmo dinámico calcula un multiplicador continuo ($1.0\times$ a $3.2\times$) en función de la densidad de solicitudes y el índice local de congestión.
4. **Heterogeneidad Socioeconómica y Métodos de Pago:** La ciudad exhibe marcados contrastes socioeconómicos entre zonas (altos ingresos, estratos medios, sectores populares y centros comerciales/gubernamentales), lo que condiciona la adopción de métodos de pago (efectivo, tarjetas bancarias y billeteras digitales móviles como Billetera Banpro o Kash).
5. **Degradación de Flota, Combustible y Mantenimiento:** El kilometraje acumulado, las horas en ralentí en embotellamientos y el tránsito a través de cuadrantes vulnerables a corrientes de agua generan fatiga mecánica acelerada, requiriendo servicios programados de mantenimiento (cambio de aceite, frenos y suspensión cada 5,000 km) y reparaciones correctivas por anegamiento.

---

## 2. Diccionario de Datos Relacional 3NF (`raw_staging_movigo`)

El esquema relacional de MoviGo está estrictamente normalizado en **Tercera Forma Normal (3NF)** y consta de 14 tablas interconectadas:

| Tabla | Clave Primaria | Claves Foráneas | Descripción |
| :--- | :--- | :--- | :--- |
| `urban_zones` | `zone_id` | - | 12 zonas metropolitanas de Managua (`socioeconomic_stratum`: alto, medio, popular, comercial) con tarifa base de bajada de bandera (`base_flag_drop_fare`). |
| `quadrants` | `quadrant_id` | `zone_id` | Malla continua de 92 cuadrantes rectangulares (`~0.88 km × 0.88 km`) con límites geográficos (`lat_min..lat_max`, `lon_min..lon_max`), altitud media (`mean_altitude_masl`), riesgo de anegamiento (`flood_risk`) y cauces cercanos (`main_drainage_channels`). |
| `drainage_channels` | `channel_id` | - | Catálogo de los 14 principales corredores hidráulicos/cauces de Managua derivados de OpenStreetMap (longitud surveyed en km, número de tramos OSM, coordenadas de centroide y riesgo base de anegamiento). |
| `users` | `user_id` | - | Usuarios registrados en la plataforma, método de pago habitual (`preferred_payment_method`) y calificación promedio acumulada (`average_rating`). |
| `drivers` | `driver_id` | - | Conductores afiliados con calificación histórica (`average_rating`), tasa de aceptación de solicitudes (`acceptance_rate_pct`), horas semanales promedio de conexión y estado (`status`). |
| `vehicles` | `vehicle_id` | `driver_id` | Unidades de la flota asignadas a conductores con categoría de servicio (`service_type`), modelo (`vehicle_model`), año (`vehicle_year`), placa (`license_plate`), odómetro (`mileage_km`), capacidad de tanque de combustible (`fuel_tank_liters`), tasa de consumo nominal (`fuel_consumption_rate` L/km) y kilometraje del último servicio (`last_service_km`). |
| `vehicle_maintenance` | `service_id` | `vehicle_id` | Historial de mantenimiento de la flota: fecha de servicio (`service_date`), tipo de servicio (`preventivo`, `correctivo`), kilometraje al momento del ingreso (`odometer_km`), costo facturado (`cost_nio`), exposición acumulada a anegamientos (`flood_exposure_trips`), horas de inactividad (`downtime_hours`) y diagnóstico del taller (`notes`). |
| `incentive_campaigns` | `campaign_id` | `target_zone_id` | Programas de bonos e incentivos económicos dirigidos a zonas estratégicas (`target_zone_id`), con presupuesto asignado (`budget_cost_nio`) y horas de conexión estimadas (`online_hours_increase`). |
| `quadrant_weather` | `weather_id` | `quadrant_id` | Series horarias meteorológicas por cuadrante con precipitación local (`precipitation_mm`), escorrentía en cauces (`channel_runoff_mm`), estado de anegamiento de calles (`flooded_roads`) e índice de congestión vial (`congestion_index`). |
| `trips` | `trip_id` | `user_id`, `driver_id`, `origin_quadrant_id`, `destination_quadrant_id` | Cabecera transaccional esbelta de viajes con coordenadas GPS precisas sobre la red vial (`origin_latitude`, `origin_longitude`, `destination_latitude`, `destination_longitude`), marcas de tiempo (`requested_at`, `started_at`, `completed_at`), distancia euclidiana/vial recorrida (`distance_km`), duración (`duration_minutes`) y estado (`trip_status`). |
| `trip_payments` | `payment_id` | `trip_id` | Liquidación financiera del viaje: método de pago utilizado (`payment_method`), tarifa base calculada (`base_fare`), multiplicador dinámico aplicado (`surge_multiplier`), propina voluntaria (`tip_amount`), cobro final (`final_fare`) y estado (`payment_status`: `pagado` o `anulado`). |
| `trip_ratings` | `rating_id` | `trip_id` | Calificaciones bilaterales post-viaje (`user_rating`, `driver_rating`) registradas exclusivamente para servicios completados (`trip_status = 'completado'`). |
| `trip_cancellations` | `cancellation_id` | `trip_id` | Bitácora de cancelaciones registradas para viajes abortados, identificando actor (`cancelled_by`: `usuario` o `conductor`), motivo (`cancellation_reason`), tiempo de espera transcurrido (`wait_time_minutes`) y fricción de oferta/demanda al instante del desestimiento (`origin_active_requests`, `origin_available_drivers`). |
| `driver_telemetry` | `telemetry_id` | `driver_id`, `trip_id`, `quadrant_id` | Registros de trayectoria GPS continua (`speed_kmh`, coordenadas lat/lon, estado de servicio `disponible`, `en_camino_recogida` u `ocupado`). |
| `trip_audit_logs` | `audit_id` | - | Registro inmutable de auditoría generado por triggers de base de datos ante cambios de estado de viajes. |

---

## 3. Capas Cartográficas Vectoriales (GIS)

A diferencia de simulaciones convencionales con puntos sintéticos aproximados, MoviGo extrae su infraestructura física directamente de **OpenStreetMap** (`managua_osm_raw.json`):

1. **`artifacts/movigo/spatial/managua_cauces.geojson`**:
   * Contiene **485 geometrías vectoriales `LineString`** (3,519 segmentos de línea) que representan el sistema de drenaje pluvial real de Managua (incluyendo el Cauce Occidental, Cauce Oriental, Interceptor Tiscapa, Cauce Pochocuape, etc.).
2. **`artifacts/movigo/spatial/managua_quadrants.geojson`**:
   * Polígonos de los 92 cuadrantes de la grilla metropolitana con atributos de altitud media, riesgo de inundación y cauces asignados.
3. **`artifacts/movigo/spatial/managua_zones.geojson`**:
   * Polígonos de amortiguamiento de las 12 zonas socioeconómicas oficiales de Managua.
4. **`artifacts/movigo/spatial/managua_hex_grid.geojson`**:
   * Malla hexagonal regular (120 celdas hexagonales tipo H3) para ejercicios modernos de agregación geoespacial y mapas de calor.

---

## 4. Arquitectura de la API REST Operacional (FastAPI)

El servidor expone **30 colecciones transaccionales** bajo el prefijo `/movigo/`:
* `/movigo/quadrants` (Catálogo de cuadrantes urbanos)
* `/movigo/zones` (Zonas metropolitanas y estrato)
* `/movigo/drainage_channels` (Corredores hidráulicos reales)
* `/movigo/users` (Usuarios registrados)
* `/movigo/drivers` (Conductores afiliados)
* `/movigo/vehicles` (Flota vehicular y métricas de consumo)
* `/movigo/maintenance` (Servicios de taller y desgaste mecánico)
* `/movigo/campaigns` (Campañas de incentivos a conductores)
* `/movigo/weather` (Clima y anegamiento horario)
* `/movigo/trips` (Cabeceras transaccionales de viajes)
* `/movigo/payments` (Transacciones de pago)
* `/movigo/ratings` (Evaluaciones bilaterales)
* `/movigo/cancellations` (Bitácora de cancelaciones)
* `/movigo/telemetry` (Pings GPS de trayectoria de conductores)

> [!IMPORTANT]
> **Separación Pedagógica Estricta de la API:**
> La API REST es **100% operacional**. No expone endpoints analíticos de conveniencia (`/moran`, `/od-matrix`, `/grafos`, etc.). Los estudiantes deben consumir las tablas transaccionales crudas o archivos generados e implementar sus propios algoritmos y transformaciones en Python, SQL, R o Julia.

---

## 5. Objetos Avanzados de Base de Datos

* **Trigger de Auditoría (`trg_audit_trips`):** Registra de forma inmutable cada transición del ciclo de vida del viaje (`solicitado` $\rightarrow$ `en_camino_recogida` $\rightarrow$ `en_curso` $\rightarrow$ `completado` / `cancelado`).
* **Función PL/pgSQL Determinista (`fn_calculate_trip_fare`):** Calcula la tarifa final en córdobas nicaragüenses:
  $$\text{Tarifa Final} = (\text{FlagDropFare} + \text{km} \cdot 18.00 + \text{min} \cdot 4.50) \cdot \text{SurgeMultiplier}$$
* **Vista Materializada Analítica (`mv_hourly_mobility_kpis`):** Agrupa métricas por hora del día y estrato socioeconómico uniendo `trips`, `quadrants`, `urban_zones` y `trip_payments`, con índices únicos sobre `(hour_of_day, socioeconomic_stratum)` para acelerar consultas analíticas.

---

## 6. Retos y Entregables por Asignatura (Enfoque Multidisciplinar)

Para ver el detalle completo de la hoja de ruta académica expandida, consulte [docs/MEJORAS_SIMULACION_MOVIGO.md](file:///var/home/ocelot/Repositories/cs-datos-simulations/docs/MEJORAS_SIMULACION_MOVIGO.md).

### A. Bases de Datos Relacionales & Analíticas
1. **Modelado Dimensional en dbt (*Star Schema*):**
   * Construir el modelo analítico con tablas de hechos (`fact_trips`, `fact_vehicle_maintenance`, `fact_driver_telemetry`) y dimensiones (`dim_user`, `dim_driver`, `dim_vehicle`, `dim_quadrant`, `dim_zone`, `dim_date_time`).
   * Desnormalizar el esquema OLTP 3NF y derivar el desglose tarifario (`flag_drop_fare`, `distance_charge`, `time_charge`) y tiempos de espera.
2. **Pruebas de Calidad de Datos (dbt tests):**
   * Escribir validaciones de integridad referencial, valores únicos, montos no negativos y multiplicadores dinámicos $\ge 1.0$.
3. **Tableros de Business Intelligence (Metabase / PowerBI):**
   * Crear dashboards interactivos de volumen de viajes, ingresos brutos, horas de mayor tarifa dinámica y matriz de calor de orígenes/destinos.

### B. Ciencia de Datos Espacial, GIS & Econometría Espacial
1. **Matriz Origen-Destino (OD Matrix):**
   * Generar la matriz completa de desplazamientos entre cuadrantes y zonas de Managua, diferenciando viajes intra-zona vs. inter-zona.
2. **Calibración del Modelo de Gravedad Espacial de Wilson:**
   * Estimar el parámetro de fricción de la distancia ($\gamma$) mediante regresión log-lineal sobre los flujos observados:
     $$\ln\left(\frac{T_{ij}}{O_i D_j}\right) = \ln k - \gamma \ln(d_{ij})$$
3. **Autocorrelación Espacial Global (I de Moran):**
   * Construir una matriz de pesos espaciales de contigüidad Reina (*Queen contiguity*) sobre los 92 cuadrantes.
   * Calcular el estadístico de Moran global ($I$), el valor esperado $E[I]$, su varianza y el $z$-score de significancia estadística.
4. **Indicadores Locales de Asociación Espacial (LISA):**
   * Identificar cuadrantes *High-High* (puntos calientes de demanda) y *Low-Low* (puntos fríos), cartografiando los clusters espaciales sobre QGIS o GeoPandas.
5. **Índice de Vulnerabilidad Hidráulica ($FHI$):**
   * Evaluar el riesgo de anegamiento de la infraestructura vial calculando la distancia perpendicular punto-a-línea contra los 485 tramos de cauces vectoriales de OSM.

### C. Investigación de Operaciones & Logística
1. **Programación Lineal Entera Mixta (MIP) para Mantenimiento Preventivo:**
   * *Problema de la Mochila / Asignación:* Programar las entradas a taller de los vehículos que han acumulado más de 5,000 km o alta exposición a anegamientos, minimizando los costos de taller sin reducir el número mínimo de unidades en servicio durante las horas pico matutinas y vespertinas.
2. **Algoritmo Húngaro (Despacho Bipartito Óptimo):**
   * Resolver el emparejamiento óptimo entre conductores disponibles y solicitudes activas en ventanas de 30 segundos, minimizando el tiempo total de llegada y penalizando asignaciones a través de cuadrantes con anegamiento vial.
3. **Caminos Mínimos en Redes Viales (Dijkstra / A\*):**
   * Encontrar la ruta óptima sobre el grafo vial de Managua comparando el tiempo estimado en condiciones secas vs. tormenta pluvial (donde las calles inundadas tienen velocidad reducida a 5 km/h o corte total).

### D. Ciencia de Datos & Aprendizaje Automático (Machine Learning)
1. **Regresión Dinámica de ETA (Tiempo de Llegada):**
   * Entrenar modelos supervisados (Ridge, Random Forest, XGBoost) para predecir la duración real del viaje (`duration_minutes`) usando variables de distancia, hora, día de la semana, precipitación horaria y proximidad a cauces.
2. **Clasificación de Propensión a Cancelación:**
   * Predecir la probabilidad de cancelación de un viaje antes de su inicio a partir del tiempo de espera transcurrido, multiplicador dinámico y oferta de conductores disponibles (evaluando con métricas ROC-AUC y curvas Precision-Recall ante desbalance de clases).
3. **Predicción de Abandono de Conductores (*Driver Churn / Burnout*):**
   * Modelar la deserción o reducción drástica de horas de trabajo en función de calificaciones bajas, sobreexposición a horas lluviosas y desgaste mecánico vehicular.

### E. Shell Scripting (DataOps) & Sistemas Distribuidos
1. **Extracción y Monitoreo Automatizado (DataOps):**
   * Crear scripts en Bash que extraigan datos de la API REST mediante `curl` y `jq`, validen esquemas JSON, comprueben sumas SHA-256 y envíen alertas por correo o Telegram ante picos repentinos de viajes cancelados.
2. **Ingeniería de Flujo en Tiempo Real (Event Streaming):**
   * Conectar un consumidor en streaming (Kafka / Spark Streaming / DuckDB) que ingeste la telemetría vehicular (`driver_telemetry`) a alta frecuencia, calculando geocercas (*geofencing*) y recalculando tarifas dinámicas en ventanas de tiempo deslizantes.

### F. Estadística II
1. **Regresión Lineal Múltiple:** Modelar la demanda horaria de viajes en función de la precipitación acumulada ($mm$) y el índice de congestión vial.
2. **Tabla ANOVA Completa:** Calcular la varianza explicada ($SCA$), residual ($SCE$) y el estadístico $F$.
3. **Validación de Supuestos de Gauss-Markov:** Evaluar normalidad de residuos (Shapiro-Wilk), homocedasticidad (Breusch-Pagan) e independencia temporal (Durbin-Watson).
4. **Pruebas de Hipótesis Formales:**
   * $t$-Student: ¿Incrementa significativamente la lluvia la tarifa media pagada por el usuario?
   * $z$-proporciones: ¿Es la tasa de cancelación en horas pico significativamente superior a la de horas valle?
   * ANOVA de un factor: ¿Varía la duración media del viaje significativamente según el estrato socioeconómico de origen?
   * Ji-Cuadrado ($\chi^2$): Demostrar la correlación entre el método de pago seleccionado y el estrato socioeconómico de la zona ($p < 0.01$).

### G. Métodos Numéricos
1. **Búsqueda de Raíces:** Hallar el multiplicador dinámico de equilibrio de mercado $m^*$ donde la función de exceso de demanda $f(m) = \text{Demanda}(m) - \text{Oferta}(m) = 0$ mediante los métodos de **Bisección** y **Newton-Raphson**.
2. **Diferenciación Numérica:** Calcular la elasticidad-precio de la demanda mediante diferencias finitas centradas de orden $\mathcal{O}(h^2)$ para determinar si el transporte por aplicación en Managua es elástico o inelástico.
3. **Integración Numérica:** Estimar el volumen acumulado de viajes a lo largo de las 24 horas aplicando la **Regla de Simpson 1/3** sobre la curva horaria de intensidad de demanda.

### H. Finanzas Corporativas & Actuaría
1. **Nómina Laboral Nicaragüense y Retenciones de Ley:**
   * Calcular la deducción del INSS laboral (7%), INSS patronal (22.5%) y la retención del Impuesto sobre la Renta (IR) sobre los ingresos brutos de los conductores conforme a las tarifas progresivas de la Ley 822 (Ley de Concertación Tributaria).
2. **Depreciación y Vida Útil de la Flota:**
   * Construir calendarios de depreciación contable de los vehículos de la empresa comparando el método de línea recta contra depreciación acelerada (MACRS).
3. **Sensibilidad al Precio del Combustible:**
   * Modelar el impacto de la fluctuación del precio internacional del crudo y el combustible en Nicaragua sobre el margen de contribución por kilómetro recorrido.

---

## 7. Ejecución de la Simulación y Artefactos Producidos

Para generar el dataset anual completo de MoviGo (año 2024, 366 días deterministas):

```bash
# Ejecutar generación anual con semilla determinista
uv run movigo-sim generate --seed 42 --days 366
```

### Artefactos Generados en el Repositorio

* **Datos Tabulares (CSV & SQL):**
  * `artifacts/movigo/csv/*.csv` (14 tablas en formato CSV).
  * `artifacts/movigo/sql/schema_and_data.sql` (Script DDL y datos PostgreSQL con claves foráneas, triggers y vistas materializadas).
* **Capas Espaciales Vectoriales (GeoJSON):**
  * `artifacts/movigo/spatial/managua_cauces.geojson` (485 líneas de cauces reales de OSM).
  * `artifacts/movigo/spatial/managua_quadrants.geojson` (92 polígonos de cuadrantes).
  * `artifacts/movigo/spatial/managua_zones.geojson` (12 zonas socioeconómicas).
  * `artifacts/movigo/spatial/managua_hex_grid.geojson` (120 hexágonos regulares).
* **Ground Truth y Solución Docente (JSON):**
  * `artifacts/movigo/simulation_summary.json` (Contiene métricas consolidadas, coeficientes del modelo de gravedad, $I$ de Moran espacial, clusters LISA e índices de vulnerabilidad hidráulica).

---

## 8. Consultas SQL de Inicio Rápido

Consulte el archivo [`queries/03_movigo.sql`](file:///var/home/ocelot/Repositories/cs-datos-simulations/queries/03_movigo.sql) para ejemplos funcionales sobre PostgreSQL que cubren validaciones de integridad, matrices origen-destino, auditoría de cancelaciones y análisis de mantenimiento vehicular.
