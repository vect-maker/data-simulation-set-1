# Motores de Simulación de Datos Sintéticos (Proyecto Integrador - Nicaragua)

Repositorio de generación y simulación de datos transaccionales realistas para el **Proyecto Integrador: De los Datos a la Decisión**, ambientado en el contexto socioeconómico y productivo de **Nicaragua**. El proyecto cubre de manera rigurosa las **6 asignaturas de la columna vertebral académica**:

1. **Bases de Datos Relacionales:** Modelado relacional normalizado (3NF), claves foráneas con integridad referencial, restricciones `CHECK`, funciones PL/pgSQL, procedimientos almacenados (`sp`), tablas de auditoría y triggers (`AFTER UPDATE`, `BEFORE INSERT`).
2. **Diseño y Uso de Bases de Datos Analíticas:** Esquemas staging (`raw_staging`), vistas materializadas analíticas con refresco e índices únicos para reporting, control de acceso basado en roles (`rol_ingesta_dataops`, `rol_analista_datos`) y optimización de consultas.
3. **Automatización y Scripting:** CLI unificada (`data-sim`), automatización de tareas con `just`, ingesta de APIs REST con reintentos y caché local, pipelines de generación transaccional reproducible y exportación estándar a CSV y SQL DDL.
4. **Estadística II:** Regresión lineal simple y múltiple con tabla ANOVA completa (SCA, SCE, SCT, $F$, $p$-valor, $R^2$), verificación de supuestos de Gauss-Markov (normalidad de Shapiro-Wilk, homocedasticidad de Breusch-Pagan, autocorrelación de Durbin-Watson), 3 pruebas formales de hipótesis ($t$-Student, $z$-proporciones, ANOVA de un factor) y pruebas de independencia Ji-Cuadrado ($\chi^2$).
5. **Métodos Numéricos:** Búsqueda de raíces de ecuaciones no lineales (Bisección y Newton-Raphson), cálculo numérico de derivadas y elasticidad-precio de la demanda mediante diferencias finitas centradas, e integración numérica (Regla de Simpson 1/3 y regla Trapezoidal).
6. **Optimización:** Programación lineal continua (Simplex), modelos de redes y transporte (Método de Aproximación de Vogel - VAM), asignación óptima de recursos (Algoritmo Húngaro), caminos más cortos (Dijkstra sobre grafos urbanos), programación entera (Problema de la Mochila 0/1) y gestión de proyectos (Método de la Ruta Crítica - CPM/PERT).

---

## Casos de Estudio Implementados

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ CASO 1: Antojitos Express (Cocina Fantasma / Delivery en Managua)           │
│  - Driver: Precipitación diaria en Managua (Open-Meteo)                     │
│  - Ji-Cuadrado: Categoría de platillo vs. Zona urbana de Managua            │
│  - Estadística: Regresión Lluvia vs. Órdenes, Supuestos Gauss-Markov        │
│  - Métodos Numéricos: Raíces (Equilibrio de cocina), Elasticidad de precios │
│  - Optimización: Asignación Húngara couriers, Simplex insumos de cocina     │
│  - Base de Datos: Triggers de auditoría y validación cronológica, MV ventas │
│  - CLI: antojitos-sim                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ CASO 2: Cooperativa El Volcán (Café de Exportación de Altura)               │
│  - Driver: Clima agropecuario Jinotega (Open-Meteo) y cotización mercado C  │
│  - Ji-Cuadrado: Variedad botánica vs. Región cafetalera                     │
│  - Estadística: Regresión Altitud vs. SCAA, 3 Pruebas de Hipótesis          │
│  - Métodos Numéricos: Cinética de secado M(t)=M0*e^(-kt), Newton-Raphson    │
│  - Optimización: Modelo Vogel (Fincas->Beneficios->Corinto), Mochila, CPM   │
│  - Base de Datos: SP cierre beneficio, Trigger auditoría, MV exportaciones  │
│  - CLI: volcan-sim                                                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ CASO 3: MoviGo (Transporte por Aplicación - Managua)                        │
│  - Driver: Precipitación y congestión vial en Managua (Open-Meteo)          │
│  - Ji-Cuadrado: Método de pago vs. Estrato socioeconómico de origen         │
│  - Estadística: Regresión Lluvia vs. Viajes, ANOVA duración por estrato     │
│  - Métodos Numéricos: Multiplicador de equilibrio oferta/demanda (Bisección)│
│  - Optimización: Algoritmo Húngaro conductores, Dijkstra rutas críticas     │
│  - Base de Datos: Trigger auditoría estados, Función liquidación, MV KPIs   │
│  - CLI: movigo-sim                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Alineación Curricular Detallada

### A. Bases de Datos Relacionales & Analíticas
Cada caso genera un esquema DDL completo (`schema_and_data.sql`) cargable directamente en PostgreSQL:
* **Integridad y Restricciones:** Claves primarias sintéticas o compuestas, claves foráneas con restricciones de integridad y cláusulas `CHECK` en columnas de estado.
* **Auditoría con Triggers:**
  * `trg_auditar_ordenes` / `trg_auditar_lotes` / `trg_auditar_viajes`: Capturan de forma transparente cualquier cambio de estado del registro, insertando fecha exacta, usuario de base de datos (`CURRENT_USER`) y valores anterior/nuevo en tablas de auditoría independientes.
  * `trg_validar_cronologia_orden`: Trigger de negocio `BEFORE INSERT OR UPDATE` que impide inconsistencias temporales (e.g. hora de entrega previa a la creación).
* **Lógica Almacenada (PL/pgSQL):**
  * `fn_calcular_total_orden(p_id_orden)`: Calcula el total neto consolidando ítems, promociones, envío y propina.
  * `sp_cerrar_etapa_beneficio(p_id_proceso, p_merma, p_peso_salida)`: Procedimiento almacenado transaccional para actualizar rendimientos de secado/trillado.
  * `fn_liquidar_tarifa_viaje(p_base, p_dist, p_dur, p_mult)`: Función determinista de liquidación de viajes.
* **Vistas Materializadas e Índices:**
  * `mv_resumen_diario_ventas`, `mv_resumen_exportacion_pais`, `mv_kpis_movilidad_horaria`.
  * Índices únicos sobre las claves lógicas de agregación y B-tree sobre claves foráneas y fechas para optimización del plan de ejecución (`EXPLAIN ANALYZE`).
* **Seguridad y Roles (RBAC):**
  * Creación y asignación de permisos mínimos para `rol_ingesta_dataops` (escritura en staging) y `rol_analista_datos` (lectura analítica y acceso a vistas materializadas).

### B. Automatización, Pipelines y CLI
Arquitectura modular en Python con automatización centralizada vía `justfile` y CLI `data-sim`:
* **Cliente HTTP Meteorológico:** Descarga datos desde la API Archive de Open-Meteo con caché local y reintentos, más fallback sintético determinista.
* **Pipelines de Carga a Base de Datos:** Carga directa a PostgreSQL con soporte para `psql` nativo y `podman compose exec`.
* **Automatización con Just:** Recetas para instalación, generación, inspección visual en consola, tests unitarios y limpieza de entorno.

### C. Estadística II
Módulos `analytics.py` en cada motor que calculan métricas rigurosas expuestas tanto en formato Rich (consola) como en JSON:
* **Tabla ANOVA de Regresión:** Sumas de cuadrados (Regresión, Residual, Total), grados de libertad, cuadrados medios, estadístico $F$, $p$-valor y coeficientes ($R^2$, $R^2$ ajustado).
* **Diagnóstico de Supuestos Gauss-Markov:**
  * **Normalidad:** Test de Shapiro-Wilk sobre los residuos ($W$, $p$-valor).
  * **Homocedasticidad:** Test de Breusch-Pagan / Lagrange Multiplier ($LM$, $p$-valor).
  * **Independencia:** Estadístico de Durbin-Watson ($d$).
* **3 Pruebas de Hipótesis Formales por Motor:**
  1. Diferencia de medias con $t$-Student independiente ($t$, $p$-valor).
  2. Diferencia de proporciones con prueba $z$ ($z$, $p$-valor).
  3. ANOVA de un factor para comparación múltiple de grupos ($F$, $p$-valor).
* **Prueba de Independencia Ji-Cuadrado ($\chi^2$):** Validación con tablas de contingencia cruzando variables categóricas ($p < 0.01$).

### D. Métodos Numéricos
Implementaciones explícitas sin dependencias opacas:
* **Búsqueda de Raíces:** Algoritmos de Bisección y Newton-Raphson para encontrar puntos de equilibrio económico ($R(q) - C(q) = 0$), tiempos de secado de café hasta el 11.5% de humedad, y multiplicador dinámico óptimo de transporte ($S(m) - D(m) = 0$).
* **Diferenciación Numérica:** Aproximación por diferencias finitas centradas de orden $\mathcal{O}(h^2)$ para calcular la elasticidad-precio puntual $\epsilon_p = \frac{dq}{dp}\frac{p}{q}$.
* **Integración Numérica:** Regla compuesta de Simpson 1/3 y regla Trapezoidal para integración de flujos continuos de demanda y masa de café recolectada.
* **Linealización:** Ajuste exponencial de cinética de deshidratación $\ln M(t) = \ln M_0 - kt$ mediante mínimos cuadrados ordinarios.

### E. Optimización
Modelos prescriptivos aplicados al negocio:
* **Programación Lineal (Simplex):** Maximización de margen bruto sujeto a capacidad horaria de freidoras, hornos y horas-hombre en cocina.
* **Modelo de Transporte (Vogel - VAM):** Distribución de carga óptima minimizando fletes de café desde centros de acopio hacia beneficios y Puerto Corinto.
* **Algoritmo Húngaro (Asignación):** Emparejamiento biyectivo óptimo que minimiza el tiempo total de espera entre repartidores/conductores y solicitudes.
* **Ruta Más Corta (Dijkstra):** Selección de trayectos óptimos sobre la red vial de Managua comparando tiempos en condiciones secas vs. lluvia torrencial.
* **Problema de la Mochila (Knapsack 0/1):** Selección de lotes especiales de café para subastas internacionales o campañas de incentivos a conductores maximizando retorno bajo presupuesto limitado.
* **Gestión de Proyectos (CPM / PERT):** Determinación de la ruta crítica y holguras sobre la cadena de valor de beneficio y exportación de café (12 actividades).

---

## 2. Comandos Principales (`justfile`)

| Comando | Descripción |
| :--- | :--- |
| `just` | Lista todas las recetas disponibles |
| `just install` | Instala paquetes y dependencias en modo editable (`pip install -e .`) |
| `just test-unit` | Ejecuta suite de pruebas unitarias (Stats, Métodos Numéricos, Optimización, Integridad) |
| `just test` | Ejecuta suite unitaria + simulación rápida de 3 días + inspección analítica |
| `just generate-all [days]` | Ejecuta las simulaciones para los 3 casos (ej. `just generate-all 7`) |
| `just inspect-all` | Despliega tablas Rich con estadística, métodos numéricos y optimización |
| `just load-all` | Carga esquemas, triggers, procedimientos, CSVs y vistas materializadas en PostgreSQL |
| `just db-up` / `just db-down` | Levanta o apaga el contenedor de PostgreSQL 18 Alpine |
| `just db-psql` | Abre una sesión interactiva `psql` dentro de la base de datos |
| `just api-up` / `just api-down` | Levanta o apaga todos los servicios (PostgreSQL + FastAPI API en puerto 8000) |
| `just api-logs` | Visualiza los logs en tiempo real del contenedor FastAPI |
| `just api-run` | Inicia la API localmente con Uvicorn y recarga en caliente para desarrollo |
| `just api-eval [case]` | Evalúa la integridad de los datos de la API contra los CSVs generados |
| `just clean` | Limpia artefactos generados, cachés temporales y archivos `.pyc` |

---

## 3. CLI Unificada (`data-sim`) y Motores Especializados

El proyecto cuenta con un punto de entrada unificado `data-sim` en Python y mantiene compatibilidad total con los CLIs independientes:

```bash
# Uso del CLI unificado:
data-sim generate --case all --days 30   # Genera los 3 casos (o --case antojitos / volcan / movigo)
data-sim inspect --case all             # Muestra métricas, tablas ANOVA y modelos prescriptivos
data-sim load --case all                # Carga datos en PostgreSQL (local psql o Podman)
data-sim weather --case all             # Descarga o verifica series meteorológicas

# O usando los CLIs específicos:
antojitos-sim generate --days 30 && antojitos-sim inspect
volcan-sim generate --days 30 && volcan-sim inspect
movigo-sim generate --days 30 && movigo-sim inspect
```

---

## 4. API REST para Estudiantes (`FastAPI` & Podman Compose)

El repositorio incluye un servicio web REST en FastAPI (`src/api`) conectado directamente a PostgreSQL para que los estudiantes puedan consumir, filtrar y paginar los datos simulados:

* **Documentación Interactiva:** Swagger UI en [`http://localhost:8000/docs`](http://localhost:8000/docs) y ReDoc en [`http://localhost:8000/redoc`](http://localhost:8000/redoc).
* **Seguridad y Acceso:** Acceso público sin autenticación, con CORS completamente abierto (`*`) para consumo directo desde navegadores, Jupyter Notebooks, Google Colab o scripts en Python/R.
* **Paginación Estándar:** Formato envelope `{"items": [...], "count": N, "total": M, "offset": X, "limit": Y}` con parámetros `?limit=50&offset=0` y ordenamiento `?sort=campo` o `?sort=-campo`.
* **Rutas por Caso:**
  * **Caso 1 (Antojitos Express):** `/antojitos/zonas`, `/antojitos/repartidores`, `/antojitos/categorias`, `/antojitos/platillos`, `/antojitos/promociones`, `/antojitos/clima`, `/antojitos/ordenes`, `/antojitos/ordenes/{id_orden}`, `/antojitos/detalles`.
  * **Caso 2 (Cooperativa El Volcán):** `/volcan/fincas`, `/volcan/variedades`, `/volcan/beneficios`, `/volcan/cuadrillas`, `/volcan/clima`, `/volcan/lotes`, `/volcan/lotes/{id_lote}`, `/volcan/procesamiento`, `/volcan/subastas`, `/volcan/embarques`.
  * **Caso 3 (MoviGo):** `/movigo/zonas`, `/movigo/usuarios`, `/movigo/conductores`, `/movigo/campanas`, `/movigo/clima`, `/movigo/viajes`, `/movigo/viajes/{id_viaje}`, `/movigo/telemetria`.

```bash
# Iniciar servicios completos en Podman Compose (Postgres + FastAPI):
just api-up

# Verificar estado de salud y conexión a la base de datos:
curl http://localhost:8000/health
```

---

## 5. Estructura de Salida en `artifacts/`

Toda la simulación genera de manera transparente sus archivos de salida directamente en el directorio `artifacts/`:

```text
artifacts/
├── antojitos/
│   ├── csv/                   # Tablas relacionales normalizadas (3NF) en CSV
│   │   ├── zonas.csv
│   │   ├── repartidores.csv
│   │   ├── categorias_platillo.csv
│   │   ├── platillos.csv
│   │   ├── promociones.csv
│   │   ├── clima_diario.csv
│   │   ├── ordenes.csv
│   │   └── detalle_ordenes.csv
│   ├── sql/
│   │   └── schema_and_data.sql # DDL con llaves, triggers, auditoría y comandos \copy
│   └── simulation_summary.json # Resumen métrico, ANOVA, raíces y optimización
├── volcan/
│   ├── csv/                   # Tablas de acopio, beneficio y exportación de café
│   │   ├── fincas.csv, variedades_cafe.csv, beneficios.csv, cuadrillas_corte.csv
│   │   ├── lotes_acopio.csv, procesamiento_beneficio.csv, subastas_especiales.csv
│   │   └── embarques_exportacion.csv, clima_zonas_cafetaleras.csv
│   ├── sql/
│   │   └── schema_and_data.sql # DDL con procedimientos, triggers y vistas
│   └── simulation_summary.json # Resumen métrico, cinéticas de secado y Vogel VAM
└── movigo/
    ├── csv/                   # Tablas de viajes, movilidad urbana y telemetría
    │   ├── zonas_urbanas.csv, usuarios.csv, conductores.csv, campanas_incentivos.csv
    │   └── viajes.csv, telemetria_conductores.csv, clima_cuadrantes.csv
    ├── sql/
    │   └── schema_and_data.sql # DDL con funciones de liquidación y auditoría
    └── simulation_summary.json # Resumen métrico, elasticidad y Dijkstra
```

---

## 6. Documentación y Consultas de Inicio

* **Guía Docente y Estudiante:** [`docs/GUIA_DOCENTE_Y_ESTUDIANTE.md`](docs/GUIA_DOCENTE_Y_ESTUDIANTE.md) (Rúbricas, lineamientos por asignatura, preguntas de investigación y entregables).
* **Guías de Casos de Negocio:**
  * Caso 1: [`docs/casos/01_antojitos_express.md`](docs/casos/01_antojitos_express.md)
  * Caso 2: [`docs/casos/02_cooperativa_volcan.md`](docs/casos/02_cooperativa_volcan.md)
  * Caso 3: [`docs/casos/03_movigo.md`](docs/casos/03_movigo.md)
* **Consultas SQL Starter:**
  * [`queries/01_antojitos_express.sql`](queries/01_antojitos_express.sql)
  * [`queries/02_cooperativa_volcan.sql`](queries/02_cooperativa_volcan.sql)
  * [`queries/03_movigo.sql`](queries/03_movigo.sql)

---

## 7. Estructura del Repositorio

```text
├── Dockerfile                       # Contenedor de la API REST FastAPI (Podman/Docker)
├── compose.yml                      # PostgreSQL 18 Alpine + FastAPI API
├── justfile                         # Automatización centralizada
├── pyproject.toml                   # Configuración del paquete y CLIs
├── antojitos.dbml                   # Esquema DBML Caso 1 (Antojitos Express)
├── cooperativa.dbml                 # Esquema DBML Caso 2 (Cooperativa El Volcán)
├── movigo.dbml                      # Esquema DBML Caso 3 (MoviGo)
├── docs/                            # Documentación académica y de casos
│   ├── GUIA_DOCENTE_Y_ESTUDIANTE.md # Manual maestro del proyecto integrador
│   └── casos/                       # Briefs detallados para estudiantes
├── queries/                         # Consultas SQL starter por caso
├── scripts/                         # Generadores de Semillas y Catálogos Sintéticos
│   ├── common.py                    # Utilidades de generación semántica
│   └── generate_all_seeds.py        # Generador de catálogos con Gemini API
├── src/
│   ├── api/                         # Servicio REST FastAPI público para estudiantes
│   │   ├── main.py                  # Entrypoint de FastAPI y configuración CORS
│   │   ├── database.py              # Pool de conexiones PostgreSQL
│   │   ├── schemas.py               # Modelos Pydantic y sobres de paginación
│   │   ├── utils.py                 # Query builder seguro, ordenamiento y filtros
│   │   └── routers/                 # Routers por caso (/antojitos, /volcan, /movigo)
│   ├── data_sim/                    # Núcleo unificado y compartido
│   │   ├── cli.py                   # CLI unificada 'data-sim'
│   │   └── core/                    # Módulos matemáticos, estadísticos y base
│   │       ├── stats.py             # ANOVA, Gauss-Markov, Welch t, Chi2, Prop-z
│   │       ├── numerics.py          # Bisección, Newton, Diferencias finitas, Simpson
│   │       ├── optimization.py      # Simplex con precios sombra, Vogel, Húngaro, Dijkstra, CPM
│   │       ├── weather.py           # Cliente HTTP Open-Meteo con caché y fallback
│   │       ├── database.py          # Conectores y ejecutores PostgreSQL/Podman
│   │       ├── exporter.py          # Exportadores CSV y generadores SQL DDL
│   │       └── reporting.py         # Visualizadores Rich en consola
│   ├── antojitos_sim/               # Motor Caso 1 (Cocina Fantasma Delivery)
│   ├── volcan_sim/                  # Motor Caso 2 (Café de Exportación)
│   └── movigo_sim/                  # Motor Caso 3 (Transporte Urbano MoviGo)
├── tests/                           # Suite de pruebas unitarias e integración
│   ├── test_core_stats.py
│   ├── test_core_numerics.py
│   ├── test_core_optimization.py
│   ├── test_relational_integrity.py
│   └── test_cli.py
├── artifacts/                       # Salida de simulación (CSVs, SQL, JSON)
└── data/raw/                        # Series climáticas descargadas
```
