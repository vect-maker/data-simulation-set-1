# Guía Maestro: Proyecto Integrador "De los Datos a la Decisión"

Este documento orienta a **docentes** y **estudiantes** sobre la arquitectura, propósito pedagógico y uso práctico de la suite de simulación de bases de datos para el proyecto semestral integrador.

---

## 1. Misión Pedagógica

El objetivo principal de este proyecto es dotar a los estudiantes de la carrera de **Ingeniería en Ciencia de Datos** de un entorno empresarial realista, contextualizado en **Nicaragua**, que sirve como laboratorio único para la columna vertebral de seis asignaturas:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Bases de Datos Relacionales (3NF, Claves, Triggers, SP, Auditoría)       │
│                                ↓                                            │
│ 2. Bases de Datos Analíticas (Staging, Star Schema con dbt, Vistas Mat.)   │
│                                ↓                                            │
│ 3. Shell Scripting / DataOps (APIs, curl, jq, pipelines, monitores, cron)   │
│                                ↓                                            │
│ 4. Estadística II (Regresión OLS, Supuestos Gauss-Markov, Hipótesis, χ²)   │
│                                ↓                                            │
│ 5. Métodos Numéricos (Raíces, Diferencias Finitas, Integración Simpson)     │
│                                ↓                                            │
│ 6. Optimización Prescriptiva (Simplex, Húngaro, Mochila, Dijkstra, Vogel)  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Los 3 Casos de Estudio Disponibles

Cada equipo de estudiantes asume un caso de negocio completo:

1. **Caso 1: Antojitos Express (Cocina Fantasma y Delivery en Managua)**
   - *Sector:* Restauración, gastronomía tradicional y moderna, última milla urbana.
   - *Driver:* Lluvia diaria en Managua (Open-Meteo).
   - *Doc:* [`docs/casos/01_antojitos_express.md`](file:///var/home/ocelot/Repositories/data-simulation/docs/casos/01_antojitos_express.md)
   - *Queries:* [`queries/01_antojitos_express.sql`](file:///var/home/ocelot/Repositories/data-simulation/queries/01_antojitos_express.sql)

2. **Caso 2: Cooperativa El Volcán (Café Especial de Exportación en Jinotega)**
   - *Sector:* Agroindustria, acopio en fincas, beneficiado húmedo/seco, exportación marítima.
   - *Driver:* Agroclima en Jinotega y cotización internacional.
   - *Doc:* [`docs/casos/02_cooperativa_volcan.md`](file:///var/home/ocelot/Repositories/data-simulation/docs/casos/02_cooperativa_volcan.md)
   - *Queries:* [`queries/02_cooperativa_volcan.sql`](file:///var/home/ocelot/Repositories/data-simulation/queries/02_cooperativa_volcan.sql)

3. **Caso 3: MoviGo (Transporte Urbano por Aplicación en Managua)**
   - *Sector:* Movilidad urbana compartida, tarificación dinámica, telemetría vehicular.
   - *Driver:* Lluvia torrencial y congestión vial en corredores de Managua.
   - *Doc:* [`docs/casos/03_movigo.md`](file:///var/home/ocelot/Repositories/data-simulation/docs/casos/03_movigo.md)
   - *Queries:* [`queries/03_movigo.sql`](file:///var/home/ocelot/Repositories/data-simulation/queries/03_movigo.sql)

---

## 3. Flujo de Trabajo para el Docente

### A. Generar los Datos de Simulación
El docente puede generar simulaciones de 30 días, 90 días o el año 2024 completo:

```bash
# Simular 30 días para todos los casos
just generate-all 30

# O utilizar la CLI unificada
data-sim generate --case all --days 30
```

### B. Inspeccionar las Soluciones Numéricas y Analíticas (Clave de Corrección)
Para disponer de los resultados de referencia esperados en cada materia:

```bash
just inspect-all
```

### C. Levantar PostgreSQL y Cargar las Bases de Datos
```bash
# Iniciar contenedor Podman de PostgreSQL 18
just db-up

# Cargar automáticamente los 3 esquemas relacionales
just load-all
```

### D. Empaquetar y Distribuir a los Estudiantes
El comando de empaquetado genera bundles autónomos en `data/exports/student_bundles/`:

```bash
just bundle-all
```

Cada carpeta (`caso_1_antojitos_express/`, `caso_2_cooperativa_volcan/`, `caso_3_movigo/`) contiene:
- `README.md`: La guía detallada del caso para el estudiante.
- `schema_and_data.sql`: Script SQL autocontenido para recrear la base de datos en cualquier PostgreSQL o pgAdmin.
- `csv/`: Archivos CSV normalizados para cargarlos con dbt, pandas o polars.
- Diagrama relacional `.dbml`.
- `starter_queries.sql`: Consultas SQL demostrativas.
- Un archivo comprimido `.tar.gz` listo para subir a la plataforma virtual (Moodle/Google Classroom).

---

## 4. Flujo de Trabajo para los Estudiantes

1. **Explorar el Esquema Relacional:**
   - Abrir el archivo `.dbml` en [dbdiagram.io](https://dbdiagram.io) para visualizar las tablas y llaves foráneas.
   - Ejecutar el script `starter_queries.sql` en su cliente SQL (DBeaver, pgAdmin, DataGrip, o `psql`).

2. **Verificar los Objetos de Negocio en la Base de Datos:**
   - Comprobar que los triggers de auditoría funcionen al actualizar registros.
   - Validar que los triggers de negocio impidan insertar datos incoherentes.
   - Ejecutar las funciones PL/pgSQL y refrescar las vistas materializadas.

3. **Construir la Capa Analítica:**
   - En **Bases de Datos Analíticas**: Usar dbt para modelar hechos y dimensiones (*Star Schema*).
   - En **Estadística II**: Extraer tablas hacia Python para ajustar regresiones y validar supuestos de Gauss-Markov.
   - En **Métodos Numéricos**: Implementar algoritmos de raíces, diferenciación e integración sobre las series generadas.
   - En **Optimización**: Modelar y resolver los problemas de Simplex, Húngaro y Mochila.
