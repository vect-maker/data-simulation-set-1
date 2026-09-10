# Motores de Simulación de Datos Sintéticos (Proyecto Integrador - Nicaragua)

Repositorio de generación y simulación de datos transaccionales realistas para el **Proyecto Integrador: De los Datos a la Decisión**, ambientado en el contexto socioeconómico y productivo de **Nicaragua**. El proyecto cubre de manera rigurosa las **6 asignaturas de la columna vertebral académica**:

1. **Bases de Datos Relacionales:** Modelado relacional normalizado (3NF), claves foráneas con integridad referencial, restricciones `CHECK`, funciones PL/pgSQL, procedimientos almacenados (`sp`), tablas de auditoría y triggers (`AFTER UPDATE`, `BEFORE INSERT`).
2. **Diseño y Uso de Bases de Datos Analíticas:** Esquemas staging (`raw_staging`), vistas materializadas analíticas con refresco e índices únicos para reporting, control de acceso basado en roles (`rol_ingesta_dataops`, `rol_analista_datos`) y optimización de consultas.
3. **Programación en Scripting (DataOps):** Pipeline de automatización en Bash POSIX con manejo robusto de errores (`set -euo pipefail`), descarga de APIs con `curl`, reintentos exponenciales, procesamiento de datos con `jq`, `awk` y `sed`, monitor de telemetría de sistema con `trap`, orquestador interactivo y empaquetado seguro con sumas de verificación SHA-256.
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

### B. Programación en Scripting (DataOps en Linux)
Pipeline modular ubicado en `scripts/` compatible con POSIX Bash:
* `scripts/ingesta.sh`: Descarga datos meteorológicos en tiempo real desde la API Archive de Open-Meteo con reintentos exponenciales, validación JSON y extracción de métricas con `jq`, `awk` y `sed`.
* `scripts/orquestador.sh`: Menú interactivo en terminal ANSI para ejecutar pasos pre-vuelo, generación, pruebas y carga sin fricción.
* `scripts/monitor.sh`: Daemon de monitoreo de telemetría de CPU, memoria, almacenamiento y estado de contenedores Docker con captura de señales POSIX (`trap`).
* `scripts/exportar_resultados.sh`: Empaquetado versionado `.tar.gz` de artefactos CSV y SQL con manifiesto de firmas de integridad SHA-256 (`sha256sum`).

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
| `just generate-all [days]` | Ejecuta las simulaciones para los 3 casos (ej. `just generate-all 7`) |
| `just inspect-all` | Despliega tablas Rich con estadística, métodos numéricos y optimización |
| `just load-all` | Carga esquemas, triggers, procedimientos, CSVs y vistas materializadas en PostgreSQL |
| `just test` | Ejecuta verificación de extremo a extremo (3 días por motor, validación y limpieza) |
| `just orchestrate` | Inicia el orquestador interactivo de DataOps en consola Bash |
| `just ingest [target]` | Descarga variables driver meteorológicas vía API (`all`, `antojitos`, `volcan`, `movigo`) |
| `just monitor` | Inicia el monitor en vivo de consumo de CPU, RAM, disco y PostgreSQL |
| `just export` | Empaqueta artefactos generados en `.tar.gz` versionado con firmas SHA-256 |
| `just db-up` / `just db-down` | Levanta o apaga el contenedor de PostgreSQL 18 Alpine |
| `just db-psql` | Abre una sesión interactiva `psql` dentro de la base de datos |
| `just clean` | Limpia artefactos generados, cachés temporales y archivos `.pyc` |

---

## 3. Guía de Ejecución Rápida

### Requisitos Previos
* Linux / macOS / WSL2
* Python 3.10+
* Docker y Docker Compose
* `just` (administrador de comandos)

### Paso 1: Configuración del Entorno
```bash
# Clonar y entrar al directorio
git clone <repo-url> && cd data-simulation

# Instalar dependencias
just install

# Iniciar contenedor PostgreSQL 18
just db-up
```

### Paso 2: Generación de Datos Sintéticos
```bash
# Simular 30 días de operaciones para los 3 casos
just generate-all 30

# O simular el año 2024 completo
just generate-all
```

### Paso 3: Carga en Base de Datos PostgreSQL
```bash
# Carga automática con fallback a Docker exec
just load-all
```

### Paso 4: Inspección de Modelos Analíticos
```bash
# Visualizar resultados de Estadística, Métodos Numéricos y Optimización
just inspect-all
```

### Paso 5: Exportación DataOps
```bash
# Generar paquete con sumas de verificación SHA-256
just export
```

---

## 4. Estructura del Repositorio

```text
├── antojitos.dbml                   # Esquema DBML Caso 1 (Antojitos Express)
├── cooperativa.dbml                 # Esquema DBML Caso 2 (Cooperativa El Volcán)
├── movigo.dbml                      # Esquema DBML Caso 3 (MoviGo)
├── compose.yml                      # PostgreSQL 18 Alpine con volumen montado
├── justfile                         # Automatización centralizada
├── pyproject.toml                   # Configuración del paquete y CLIs
├── scripts/                         # Pipeline DataOps & Generadores de Semillas
│   ├── ingesta.sh                   # Ingesta API Open-Meteo con reintentos y curl
│   ├── orquestador.sh               # Menú interactivo ANSI para estudiantes
│   ├── monitor.sh                   # Telemetría de recursos y Docker con traps
│   ├── exportar_resultados.sh       # Empaquetado tar.gz y manifiesto SHA-256
│   └── generate_all_seeds.py        # Generador de catálogos con Gemini API
├── src/
│   ├── antojitos_sim/               # Motor Caso 1 (Cocina Fantasma)
│   │   ├── analytics.py             # ANOVA, Gauss-Markov, Raíces, Simplex, Húngaro
│   │   ├── exporter.py              # DDL, Triggers, Auditoría, Vistas Materializadas
│   │   └── generator.py, weather.py, cli.py
│   ├── volcan_sim/                  # Motor Caso 2 (Café de Exportación)
│   │   ├── analytics.py             # ANOVA, Cinética secado, Vogel VAM, Mochila, CPM
│   │   ├── exporter.py              # DDL, SP Cierre, Triggers, Auditoría, Vistas
│   │   └── generator.py, weather.py, cli.py
│   └── movigo_sim/                  # Motor Caso 3 (Transporte Urbano MoviGo)
│       ├── analytics.py             # ANOVA, Gauss-Markov, Bisección, Húngaro, Dijkstra
│       ├── exporter.py              # DDL, Función liquidación, Triggers, Auditoría
│       └── generator.py, weather.py, cli.py
├── artifacts/                       # Salida de simulación (CSVs, SQL, JSON)
└── data/raw/                        # Series climáticas descargadas
```
