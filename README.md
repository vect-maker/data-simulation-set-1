# Motores de Simulación de Datos Sintéticos (Proyecto Integrador - Nicaragua)

Repositorio de generación y simulación de datos transaccionales realistas para el **Proyecto Integrador: De los Datos a la Decisión**, ambientado en el mercado de **Nicaragua** y cubriendo las 5 asignaturas de la columna vertebral analítica:
1. **Bases de Datos Analíticas:** Fundación OLTP normalizada con integridad referencial, staging y marts.
2. **Shell Scripting (DataOps):** Ingesta automatizada de variables *driver* externas vía APIs públicas (`ingesta.sh`).
3. **Estadística II:** Relaciones de demanda, verificación de supuestos lineales y pruebas de independencia Ji-Cuadrado ($p < 0.01$).
4. **Métodos Numéricos:** Ajuste de curvas (splines/polinomios), diferenciación (tasas de cambio/elasticidad), integración y raíces.
5. **Optimización:** Modelos de transporte, asignación (Húngaro), ruteo (TSP), optimización lineal (Simplex) y programación entera (Mochila).

---

## Casos Implementados

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ CASO 1: Antojitos Express (Cocina Fantasma / Delivery en Managua)           │
│  - Driver: Precipitación diaria en Managua (Open-Meteo)                     │
│  - Ji-Cuadrado: Categoría de platillo vs. Zona urbana de Managua            │
│  - Optimización: TSP multientrega, Húngaro couriers, Simplex capacidad     │
│  - CLI: antojitos-sim                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ CASO 2: Cooperativa El Volcán (Café de Exportación de Altura)               │
│  - Driver: Clima agropecuario Jinotega (Open-Meteo) y cotización futures    │
│  - Ji-Cuadrado: Variedad botánica vs. Región de origen (Dipilto/Jinotega...)│
│  - Regresión: Altitud de finca vs. Calidad de taza SCAA (80-92.5 pts)       │
│  - Optimización: Red Fincas -> Beneficios -> Puerto Corinto, Mochila Taza   │
│  - CLI: volcan-sim                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Caso 1: Antojitos Express (Cocina Fantasma - Managua)

* **Esquema:** [`antojitos.dbml`](file:///var/home/ocelot/Repositories/data-simulation/antojitos.dbml)
* **Ubicación:** Managua, Nicaragua (Cocina en Los Robles/Altamira).
* **Zonas:** 12 cuadrantes (Los Robles, Altamira, Villa Fontana, Las Colinas, Bello Horizonte, Bolonia, Linda Vista, Santo Domingo, Carretera Sur, Ciudad Jardín, Centroamérica, Rubenia).
* **Platillos:** Más de 35 platillos auténticos (Fritanga y asados, quesillos en hoja de chaguite, nacatamales, cacao con leche, cervezas Toña/Victoria).
* **Métricas 2024:** 56,888 órdenes, 123,241 ítems, C$ 22.3M en ventas brutas, $r = 0.9037$ con lluvia, $\chi^2 = 4,304.24$ ($p < 0.01$).

### Comandos de Ejecución
```bash
# Vía just (Recomendado)
just generate-antojitos
just inspect-antojitos
just mock-antojitos

# Vía CLI directa
antojitos-sim generate
antojitos-sim inspect
antojitos-sim mock-api --port 8000
```

---

## 2. Caso 2: Cooperativa El Volcán (Café de Exportación)

* **Esquema:** [`cooperativa.dbml`](file:///var/home/ocelot/Repositories/data-simulation/cooperativa.dbml)
* **Zonas Cafetaleras:** 30 fincas en Jinotega (Datanlí, Pantasma, El Cuá), Matagalpa (Selva Negra, Yasica Sur), Nueva Segovia (Dipilto, Mozonte) y Madriz (San Juan del Río Coco).
* **Altitudes:** 950 a 1650 msnm.
* **Variedades:** Geisha, Pacamara, Bourbon, Maragogipe, Caturra, Catuaí Rojo, Catuaí Amarillo.
* **Logística:** Fincas $\rightarrow$ Beneficios Húmedos regionales $\rightarrow$ Beneficio Seco Central Sébaco $\rightarrow$ Exportación vía **Puerto Corinto**.
* **Métricas 2024:**
  * **2,493 lotes de acopio** recolectados (3,141,263 kg de café cereza).
  * **7,479 etapas de procesamiento** (despulpado, fermentación, secado en patio, trillado).
  * **1,920 embarques internacionales** hacia Alemania, EE.UU., Japón, Bélgica, Taiwán e Italia.
  * **USD $5,918,051.28** en ingresos brutos de exportación.
  * **Correlación Altitud vs. SCAA:** $r = 0.7196$ (fuerte relación lineal).
  * **Ji-Cuadrado (Variedad vs. Región):** $\chi^2 = 712.01, p = 1.61 \times 10^{-139}$ ($p < 0.01$ **PASS**).
  * **Problema de la Mochila:** 12 micro-lotes para subasta internacional (Taza de la Excelencia) bajo restricción de quintales.

### Comandos de Ejecución
```bash
# Vía just (Recomendado)
just generate-volcan
just inspect-volcan
just mock-volcan

# Vía CLI directa
volcan-sim generate
volcan-sim inspect
volcan-sim mock-api --port 8001
```

---

## 3. Caso 3: MoviGo (Transporte por Aplicación - Managua)

* **Esquema:** [`movigo.dbml`](file:///var/home/ocelot/Repositories/data-simulation/movigo.dbml)
* **Zonas Urbanas:** 12 cuadrantes urbanos clasificados por estrato socioeconómico:
  * **Estrato Alto:** *Villa Fontana, Las Colinas, Santo Domingo*.
  * **Estrato Medio:** *Los Robles, Altamira, Bolonia, Bello Horizonte, Linda Vista*.
  * **Comercial / Universitarias:** *Metrocentro / Eje Corporativo UCA*.
  * **Popular:** *Ciudad Jardín, Mercado Oriental, Mercado Roberto Huembes*.
* **Driver Continuo:** Precipitación diaria y severidad de lluvia ($P_t$), congestionamiento vial y hora pico.
* **Ji-Cuadrado de Independencia:** Método de Pago (`efectivo`, `tarjeta`, `billetera_digital`) vs. Estrato Socioeconómico de Origen ($p < 0.01$).
* **Optimización & Métodos Numéricos:**
  * Algoritmo Húngaro para despacho y balanceo de conductores a zonas críticas.
  * Ruta más corta sobre grafos viales de Managua.
  * Elasticidad-precio de la demanda bajo multiplicador dinámico (1.0x a 2.8x).
  * Problema de la Mochila (Knapsack 0/1) para selección de bonos e incentivos a conductores bajo presupuesto mensual fijo.

### Comandos de Ejecución
```bash
# Vía just (Recomendado)
just generate-movigo
just inspect-movigo
just mock-movigo

# Vía CLI directa
movigo-sim generate
movigo-sim inspect
movigo-sim mock-api --port 8002
```

---

## 4. Orquestación con `just`

El repositorio incluye un [`justfile`](file:///var/home/ocelot/Repositories/data-simulation/justfile) para coordinar las tareas de desarrollo, simulación, inspección y carga en bases de datos:

| Comando | Descripción |
| :--- | :--- |
| `just` | Lista todos los comandos disponibles con su descripción |
| `just install` | Instala dependencias y los tres paquetes en modo editable (`pip install -e .`) |
| `just fetch-weather` / `just weather` | Descarga y actualiza desde la API Open-Meteo los datos climáticos para los 3 casos (reemplaza raw data) |
| `just fetch-weather-antojitos` | Descarga datos meteorológicos de Managua para Antojitos Express |
| `just fetch-weather-volcan` | Descarga datos agroclimáticos de Jinotega para Cooperativa El Volcán |
| `just fetch-weather-movigo` | Descarga datos de clima y tráfico de Managua para MoviGo |
| `just generate-all` | Genera las 3 simulaciones completas para el año 2024 (descarga clima si no existe) |
| `just generate-antojitos [days]` | Genera datos de Caso 1: Antojitos Express (ej. `just generate-antojitos 30`) |
| `just generate-volcan [days]` | Genera datos de Caso 2: Cooperativa El Volcán |
| `just generate-movigo [days]` | Genera datos de Caso 3: MoviGo |
| `just inspect-all` | Despliega los reportes estadísticos y métricas de los 3 casos |
| `just inspect-antojitos` | Despliega métricas de Antojitos Express |
| `just inspect-volcan` | Despliega métricas de Cooperativa El Volcán |
| `just inspect-movigo` | Despliega métricas de MoviGo |
| `just mock-antojitos [port]` | Inicia servidor mock de Open-Meteo para Antojitos (defecto: 8000) |
| `just mock-volcan [port]` | Inicia servidor mock de agro-clima para El Volcán (defecto: 8001) |
| `just mock-movigo [port]` | Inicia servidor mock de clima/tráfico para MoviGo (defecto: 8002) |
| `just db-up` / `just db-down` | Levanta o detiene el contenedor local de PostgreSQL 18 Alpine con Compose (`compose.yml`) |
| `just db-reset` | Detiene el contenedor, borra los volúmenes persistentes y lo inicia limpio |
| `just db-psql` | Abre una terminal interactiva `psql` dentro de la base de datos |
| `just load-all` | Carga los 3 casos en sus respectivos esquemas PostgreSQL |
| `just load-antojitos` | Carga Antojitos Express en el esquema `raw_staging` |
| `just load-volcan` | Carga El Volcán en el esquema `raw_staging_volcan` |
| `just load-movigo` | Carga MoviGo en el esquema `raw_staging_movigo` |
| `just test` | Ejecuta un ciclo de verificación rápida (3 días por caso), verifica y limpia |
| `just clean` | Elimina artefactos generados, cachés temporales y archivos `__pycache__` |
| `just clean-all` | Elimina artefactos generados, cachés temporales y la carpeta `data/raw/` de clima |

---

## 5. Estructura Estandarizada del Repositorio

```text
├── antojitos.dbml                   # Esquema DBML Caso 1 (Antojitos Express)
├── cooperativa.dbml                 # Esquema DBML Caso 2 (Cooperativa El Volcán)
├── movigo.dbml                      # Esquema DBML Caso 3 (MoviGo)
├── justfile                         # Orquestador de comandos Just
├── pyproject.toml                   # Configuración de paquete Python data-simulation
├── requirements.txt                 # Dependencias Python
├── compose.yml                      # PostgreSQL 18 Alpine local
├── .env.example                     # Variables de entorno
├── info.md                          # Definición del proyecto integrador
├── src/
│   ├── antojitos_sim/               # Motor Caso 1 (Antojitos Express)
│   │   ├── config.py, models.py, seeds/, weather.py
│   │   ├── generator.py, enrichment.py, exporter.py, pipeline.py, cli.py
│   ├── volcan_sim/                  # Motor Caso 2 (Cooperativa El Volcán)
│   │   ├── config.py, models.py, seeds/, weather.py
│   │   ├── generator.py, enrichment.py, exporter.py, pipeline.py, cli.py
│   └── movigo_sim/                  # Motor Caso 3 (MoviGo)
│       ├── config.py, models.py, seeds/, weather.py
│       ├── generator.py, enrichment.py, exporter.py, pipeline.py, cli.py
├── artifacts/                       # (Ignorado en git via .gitignore)
│   ├── antojitos/
│   │   ├── csv/                     # 8 CSVs normalizados
│   │   ├── sql/schema_and_data.sql  # DDL + COPY (schema raw_staging)
│   │   └── simulation_summary.json  # Métricas y pruebas Ji-Cuadrado
│   ├── volcan/
│   │   ├── csv/                     # 9 CSVs normalizados
│   │   ├── sql/schema_and_data.sql  # DDL + COPY (schema raw_staging_volcan)
│   │   └── simulation_summary.json  # Métricas y pruebas Ji-Cuadrado
│   └── movigo/
│       ├── csv/                     # 7 CSVs normalizados
│       ├── sql/schema_and_data.sql  # DDL + COPY (schema raw_staging_movigo)
│       └── simulation_summary.json  # Métricas y pruebas Ji-Cuadrado
└── data/
    └── raw/                         # (Ignorado en git via .gitignore, generado vía API)
        ├── antojitos/clima_managua_2024.json
        ├── volcan/clima_jinotega_2024.json
        └── movigo/clima_managua_movigo_2024.json
```

---

## 6. Carga Directa en PostgreSQL (dlt o psql)

### Levantar Base de Datos
```bash
just db-up
# o con Docker Compose: docker compose up -d
```

### Cargar todos los casos
```bash
just load-all
```

### O cargar individualmente con psql:
```bash
# Caso 1 (Antojitos Express -> raw_staging)
cd artifacts/antojitos/csv && psql -h localhost -U postgres -d integrador_db -f ../sql/schema_and_data.sql

# Caso 2 (Cooperativa El Volcán -> raw_staging_volcan)
cd artifacts/volcan/csv && psql -h localhost -U postgres -d integrador_db -f ../sql/schema_and_data.sql

# Caso 3 (MoviGo -> raw_staging_movigo)
cd artifacts/movigo/csv && psql -h localhost -U postgres -d integrador_db -f ../sql/schema_and_data.sql
```
