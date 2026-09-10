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
# Generar año 2024 completo (~57k órdenes)
antojitos-sim generate

# Inspeccionar reporte estadístico
antojitos-sim inspect

# Servidor Mock de clima para ingesta.sh (puerto 8000)
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
# Generar ciclo de cosecha 2024 completo
volcan-sim generate

# Inspeccionar reporte agro-estadístico
volcan-sim inspect

# Servidor Mock de clima cafetalero de Jinotega para ingesta.sh (puerto 8001)
volcan-sim mock-api --port 8001
```

---

## 3. Estructura del Repositorio

```text
├── antojitos.dbml                   # Esquema DBML Caso 1 (Antojitos Express)
├── cooperativa.dbml                 # Esquema DBML Caso 2 (Cooperativa El Volcán)
├── info.md                          # Definición del proyecto integrador
├── docker-compose.yml               # PostgreSQL 16 local
├── requirements.txt                 # Dependencias Python
├── pyproject.toml                   # Configuración del paquete CLI
├── .env.example                     # Variables de entorno
├── src/
│   ├── antojitos_sim/               # Paquete de simulación Caso 1
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── seeds/
│   │   ├── weather.py
│   │   ├── generator.py
│   │   ├── enrichment.py
│   │   ├── exporter.py
│   │   ├── pipeline.py
│   │   └── cli.py
│   └── volcan_sim/                  # Paquete de simulación Caso 2
│       ├── config.py
│       ├── models.py
│       ├── seeds/
│       ├── weather.py
│       ├── generator.py
│       ├── enrichment.py
│       ├── exporter.py
│       ├── pipeline.py
│       └── cli.py
├── artifacts/
│   ├── csv/                         # CSVs Caso 1 (Antojitos Express)
│   ├── sql/                         # SQL DDL & COPY Caso 1
│   ├── simulation_summary.json      # Métricas Caso 1
│   └── volcan/
│       ├── csv/                     # 9 CSVs Caso 2 (Cooperativa El Volcán)
│       ├── sql/                     # SQL DDL & COPY Caso 2
│       └── simulation_summary.json  # Métricas Caso 2
└── data/
    └── raw/
        ├── clima_managua_2024.json  # Clima histórico 2024 Managua
        └── volcan/
            └── clima_jinotega_2024.json # Agro-clima 2024 Jinotega
```

---

## 4. Carga Directa en PostgreSQL (dlt o psql)

### Levantar Base de Datos
```bash
docker compose up -d
```

### Cargar Caso 1 (Antojitos Express -> `raw_staging`)
```bash
antojitos-sim load
# o con psql:
cd artifacts/csv && psql -h localhost -U antojitos_user -d antojitos_db -f ../sql/schema_and_data.sql
```

### Cargar Caso 2 (Cooperativa El Volcán -> `raw_staging_volcan`)
```bash
volcan-sim load
# o con psql:
cd artifacts/volcan/csv && psql -h localhost -U antojitos_user -d antojitos_db -f ../sql/schema_and_data.sql
```
# cs-datos-simulations
