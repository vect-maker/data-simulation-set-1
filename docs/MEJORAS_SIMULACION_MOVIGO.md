# Documento de Mejoras y Expansión Multidisciplinar: Caso MoviGo

Este documento detalla la evolución arquitectónica, las mejoras implementadas y la hoja de ruta de expansión del caso de estudio **MoviGo (Transporte Urbano por Aplicación - Managua)**.

El objetivo de esta modernización es transformar a MoviGo de un ejercicio enfocado en una sola asignatura a una **plataforma académica integral y multidisciplinar**, capaz de servir como laboratorio práctico para diversas carreras y cursos avanzados:
* **Ciencia de Datos & Inteligencia Artificial** (Machine Learning, Econometría Espacial, Análisis de Series de Tiempo).
* **Ingeniería de Datos & Big Data** (Sistemas Distribuidos, Procesamiento de Eventos en Tiempo Real con Kafka/Flink, Modelado OLAP/dbt).
* **Sistemas de Información Geográfica (GIS) & Planificación Urbana** (Análisis de Redes, Vulnerabilidad Hidrológica, Autocorrelación Espacial).
* **Investigación de Operaciones & Logística** (Optimización de Flotas, Programación de Mantenimiento Preventivo, Despacho Estocástico).
* **Finanzas Corporativas & Actuaría** (Depreciación de Activos, Nómina Laboral Nicaragüense [INSS/IR], Análisis de Riesgo y Cobertura de Combustible).

---

## 1. Principios de Diseño Arquitectónico

Para preservar el rigor pedagógico y el realismo de la industria, toda mejora sigue tres principios fundamentales:

### 1.1. Separación Estricta de la API Operacional
* **Regla:** La API REST de MoviGo expone **únicamente endpoints transaccionales y operativos** (tablas del modelo relacional 3NF).
* **Razón:** Los estudiantes deben enfrentarse al dato crudo, transformarlo y calcular los algoritmos analíticos (matrices origen-destino, modelos de gravedad, autocorrelación de Moran, regresiones de demanda). La API **nunca** expone endpoints de solución analítica (`/moran`, `/od-matrix`, etc.), garantizando que los alumnos desarrollen sus propios pipelines.

### 1.2. Cero Datos Sintéticos Hardcodeados (Autenticidad Vectorial OSM)
* **Regla:** Ningún elemento físico o geográfico debe ser inventado con coordenadas arbitrarias o puntos ficticios en el código cuando existan datos reales disponibles.
* **Implementación:** La hidrología, red vial y zonificación de Managua se extraen directamente de la geometría vectorial de **OpenStreetMap** (`managua_osm_raw.json`). Los cálculos espaciales emplean distancias perpendiculares punto-a-línea (Point-to-LineString) sobre los 485 tramos de cauces reales de la capital.

### 1.3. Benchmarking y Clave de Solución Docente (Ground Truth)
* **Regla:** El motor de simulación calcula métricas estadísticas, espaciales y analíticas deterministas que se exportan a `simulation_summary.json`.
* **Propósito:** Permite a los docentes contar con una clave de respuesta exacta (*Ground Truth*) para calificación automatizada de tareas y proyectos, comparando los resultados calculados por los alumnos contra la solución de referencia de la simulación.

---

## 2. Mejoras Implementadas (Track 1: GIS Espacial & Desgaste Operativo)

### 2.1. Hidrología Vectorial Auténtica de Managua
* **Extracción de OpenStreetMap:** Se procesaron 485 vías fluviales (`LineString`, 3,519 segmentos de línea) de Managua a partir de datos reales de OSM.
* **Corredores Hidráulicos Nombrados:** Se identificaron y mapearon los 14 principales cauces de la capital:
  1. *Cauce Occidental*
  2. *Cauce Oriental*
  3. *Cauce Interceptor Tiscapa*
  4. *Cauce Cuajachillo*
  5. *Cauce Pochocuape*
  6. *Cauce Santo Domingo*
  7. *Cauce Altamira*
  8. *Cauce Sabana Grande*
  9. *Cauce Las Piedrecitas*
  10. *Cauce Américas*
  11. *Cauce Batahola*
  12. *Cauce San Isidro*
  13. *Cauce Waspán*
  14. *Cauce Valle Dorado*
* **Nueva Tabla 3NF (`drainage_channels`):** Almacena ID canónico, nombre formal, longitud surveyed en km, número de segmentos OSM, coordenadas de centroide y riesgo base de anegamiento.
* **Capas GeoJSON Exportadas:**
  * `artifacts/movigo/spatial/managua_cauces.geojson`: 485 geometrías vectoriales de cauces.
  * `artifacts/movigo/spatial/managua_quadrants.geojson`: 92 polígonos de cuadrantes urbanos.
  * `artifacts/movigo/spatial/managua_zones.geojson`: Polígonos de amortiguamiento de las 12 zonas socioeconómicas.
  * `artifacts/movigo/spatial/managua_hex_grid.geojson`: Malla hexagonal regular H3/Uber-style (120 hexágonos) para análisis geoespacial moderno.

### 2.2. Motor de Vulnerabilidad y Desgaste Físico
* **Distancia Perpendicular Vectorizada:** Cálculo sub-milisegundo de distancia euclidiana proyectada punto-a-segmento entre cualquier coordenada GPS de viaje o centroide de cuadrante y los cauces activos.
* **Riesgo Dinámico en Calles:** Los tramos viales a menos de 50 metros de un cauce activo elevan su probabilidad de anegamiento (`is_fl = 1`) y modifican las rutas de Dijkstra durante episodios de precipitación severa.
* **Mantenimiento y Desgaste Vehicular (`vehicle_maintenance`):** Registro de intervenciones mecánicas preventivas (cada 5,000 km) y correctivas (fallas aceleradas por cruce de cuadrantes anegados), con consumo de combustible diferenciado por categoría vehicular (`moto`: 2.8 L/100km, `standard`: 7.2 L/100km, `comfort`: 9.5 L/100km).

### 2.3. Suite Analítica Espacial & Econometría
Implementada en `src/movigo_sim/spatial_analytics.py`:
* **Matriz Origen-Destino (OD Matrix):** Flujo de viajes inter-zonas e intra-zonas con desglose de tarifas medias y tiempos de recorrido.
* **Modelo de Gravedad Espacial de Wilson:** Calibración log-lineal del parámetro de fricción de distancia ($\gamma$):
  $$T_{ij} = k \cdot \frac{O_i^\alpha D_j^\beta}{d_{ij}^\gamma}$$
* **Matriz de Pesos Espaciales ($W$):** Construcción de contigüidad espacial de tipo Reina (*Queen*) y banda de distancia, estandarizada por filas.
* **Autocorrelación Espacial Global (I de Moran):** Evaluación de clustering espacial de la demanda con cómputo de $z$-score y $p$-value.
* **Indicadores Locales de Asociación Espacial (LISA):** Clasificación de cuadrantes en cuadrantes *High-High* (puntos calientes), *Low-Low* (puntos fríos), *High-Low* y *Low-High*.
* **Índice de Vulnerabilidad Hidráulica ($FHI$):** Cuantificación de exposición por cuadrante ($0.0 \le FHI \le 1.0$) en función de la pendiente topográfica y la proximidad a cauces principales.

---

## 3. Hoja de Ruta de Expansión Multidisciplinar (Nuevos Tracks)

Para extender el caso de estudio a futuras asignaturas y facultades, se han diseñado los siguientes 4 módulos complementarios:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ARQUITECTURA EXPANDIDA MOVIGO                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Track 1] GIS Espacial & Econometría       ──► COMPLETO (OSM, OD, Moran)   │
│  [Track 2] Machine Learning & Predicción    ──► Modelos ETA, Fuga, Cancel   │
│  [Track 3] Streaming & Sistemas Distribuidos──► Bus Telemetría 1-5Hz Kafka  │
│  [Track 4] Investigación de Operaciones     ──► LP Mantenimiento & Despacho │
│  [Track 5] Finanzas Corporativas & Actuaría ──► Nómina INSS/IR, Deprec.     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Track 2: Ciencia de Datos & Aprendizaje Automático (Machine Learning)
1. **Regresión Dinámica de ETA (Tiempo Estimado de Llegada):**
   * *Problema:* Predecir el tiempo de viaje (`duration_minutes`) dadas las características de origen/destino, hora del día, lluvia acumulada ($mm$), índice de congestión vial y distancia ($km$).
   * *Reto Estudiantil:* Construir pipelines con `scikit-learn` o `XGBoost`, comparar modelos lineales vs. árboles de decisión y evaluar con métricas $MAE$ y $RMSE$.
2. **Clasificación de Propensión a Cancelación de Viajes:**
   * *Problema:* Predecir la probabilidad de que un viaje sea cancelado en función del tiempo de espera, la tarifa dinámica y la fricción de mercado.
   * *Reto Estudiantil:* Manejo de clases desbalanceadas (10% de cancelaciones), curvas ROC-AUC y análisis de importancia de variables con valores SHAP.
3. **Predicción de Abandono de Conductores (Driver Churn / Burnout):**
   * *Problema:* Clasificar si un conductor reducirá drásticamente sus horas de conexión semanal debido a bajas calificaciones o exposición excesiva a zonas de alto riesgo de anegamiento.

### Track 3: Ingeniería de Datos & Sistemas Distribuidos (Streaming)
1. **Generador de Eventos de Telemetría en Tiempo Real:**
   * Simulación continua de coordenadas GPS de los conductores emitiendo eventos a 1 Hz o 5 Hz hacia un broker de mensajería (Kafka, Redpanda o MQTT).
   * Cargas de eventos JSON: `{ driver_id, lat, lon, speed, heading, trip_id, status, timestamp }`.
2. **Procesamiento de Flujo con Apache Flink / Spark Streaming:**
   * *Geofencing en Vivo:* Detección de entrada y salida de cuadrantes o zonas de alta demanda en ventanas de tiempo deslizantes (*tumbling / sliding windows*).
   * *Cálculo de Surge en Streaming:* Actualización reactiva del multiplicador dinámico por cuadrante en ventanas de 2 minutos basándose en el balance de oferta/demanda en tiempo real.
3. **Almacenamiento Lakehouse / Medallion:**
   * Arquitectura Delta Lake / DuckDB estructurada en capas *Bronze* (telemetría cruda en streaming), *Silver* (viajes limpios y enriquecidos con clima) y *Gold* (KPIs agregados de movilidad).

### Track 4: Investigación de Operaciones & Logística
1. **Programación Lineal (LP / MIP) para Mantenimiento Preventivo:**
   * *Problema:* Asignar fechas y talleres de mantenimiento preventivo a la flota vehicular para minimizar costos de taller sin reducir la cobertura mínima requerida de conductores activos durante las horas pico de Managua.
2. **Despacho Estocástico Bipartito (Asignación Óptima):**
   * Implementación de algoritmos de emparejamiento con penalizaciones de distancia y riesgo hidrológico, resolviendo el problema con solvers como PuLP o Google OR-Tools.
3. **Ruteo de Vehículos con Ventanas de Tiempo y Restricción de Inundación (VRPTW):**
   * Cálculo de rutas de rescate y reubicación de flota moto hacia zonas altas durante tormentas tropicales.

### Track 5: Finanzas Corporativas, Economía Laboral & Actuaría
1. **Nómina y Fiscalidad Laboral Nicaragüense:**
   * Implementación de retenciones formales: INSS laboral (7%), INSS patronal (22.5%) y cálculo de retención en la fuente de Impuesto sobre la Renta (IR) con tarifa progresiva conforme a la Ley de Concertación Tributaria (Ley 822).
   * Liquidación neta de comisiones y pago por millaje a conductores.
2. **Modelos de Depreciación de Activos Vehiculares:**
   * Comparativa de métodos contables: depreciación lineal vs. suma de dígitos de los años vs. método MACRS sobre la flota vehicular.
3. **Análisis de Sensibilidad y Cobertura de Combustible:**
   * Simulación Monte Carlo del impacto del alza en el precio internacional del crudo sobre el margen operativo de MoviGo en Nicaragua.

---

## 4. Matriz de Aplicabilidad Académica por Carrera

| Carrera / Asignatura | Módulo de MoviGo a Utilizar | Entregable Típico del Estudiante |
| :--- | :--- | :--- |
| **Ingeniería en Ciencia de Datos** | Modelado 3NF, dbt, SQL Analítico | Star Schema con dbt, tablas de hechos y dimensiones en PostgreSQL / DuckDB. |
| **Ciencia de Datos / IA** | Machine Learning, Modelado de Demanda | Modelos predictivos de ETA y cancelación con evaluación ROC-AUC y validación cruzada. |
| **Ingeniería de Datos** | Telemetría Streaming, Data Lakehouse | Pipeline de Kafka + Flink / Spark Streaming consumiendo pings GPS en tiempo real. |
| **Geografía / Urbanismo / GIS** | Capas GeoJSON, Moran's I, LISA | Cartografía temática en QGIS, matrices de interacción espacial y mapas de calor. |
| **Investigación de Operaciones** | Optimización de Flotas, Mantenimiento | Modelo LP/MIP en Python (PuLP/SciPy) para programación de mantenimiento vehicular. |
| **Estadística / Econometría** | Regresión OLS, Gauss-Markov, ANOVA | Informe formal con validación de supuestos de regresión múltiple y pruebas de hipótesis. |
| **Contabilidad & Finanzas** | Nómina Nicaragua (INSS/IR), Activos | Módulo contable de liquidación de flota y análisis de punto de equilibrio financiero. |

---

## 5. Estructura de Entregables de la Simulación

Al ejecutar la simulación anual (`movigo-sim generate --seed 42 --days 366`), el sistema genera automáticamente:

* **Tablas Relacionales (CSV & SQL):**
  * `artifacts/movigo/csv/trips.csv`
  * `artifacts/movigo/csv/trip_payments.csv`
  * `artifacts/movigo/csv/trip_ratings.csv`
  * `artifacts/movigo/csv/trip_cancellations.csv`
  * `artifacts/movigo/csv/driver_telemetry.csv`
  * `artifacts/movigo/csv/vehicle_maintenance.csv`
  * `artifacts/movigo/csv/drainage_channels.csv`
  * `artifacts/movigo/sql/schema_and_data.sql`
* **Capas Cartográficas Vectoriales (GeoJSON):**
  * `artifacts/movigo/spatial/managua_cauces.geojson` (485 LineStrings de OSM)
  * `artifacts/movigo/spatial/managua_quadrants.geojson` (92 polígonos)
  * `artifacts/movigo/spatial/managua_zones.geojson` (12 zonas)
  * `artifacts/movigo/spatial/managua_hex_grid.geojson` (120 hexágonos regulares)
* **Clave de Solución Docente (Ground Truth JSON):**
  * `artifacts/movigo/simulation_summary.json` (incluye sección `"analitica_espacial_gis"` con Moran's I, LISA, matriz OD y coeficientes de gravedad).
