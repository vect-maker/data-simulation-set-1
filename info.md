# PROPUESTA DE PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN

Un producto de ciencia de datos de punta a punta que integra cinco asignaturas sobre un mismo almacén analítico: de la fundación descriptiva a la decisión prescriptiva.

- **Asignaturas integradas:** Bases de Datos Analíticas, Estadística II, Métodos Numéricos, Optimización, Shell Scripting.

- **Modalidad:** Un caso aplicado por grupo.

---

| Asignatura                        | Peldaño analítico | Pregunta que responde |
| --------------------------------- | ----------------- | --------------------- |
| **Bases de Datos Analíticas**<br> | Descriptivo       |

| ¿Qué pasó? — La fundación de dato limpio y confiable.

|
| **Estadística II**<br> | Diagnóstico / Inferencial

| ¿La señal es real y qué la explica?

|
| **Métodos Numéricos**<br> | Predictivo

| ¿Qué forma exacta tiene y cuánto se espera?

|
| **Optimización**<br> | Prescriptivo

| ¿Qué debemos hacer con esos números?

|
| **Shell Scripting**<br> | Operación (DataOps)

| ¿Cómo hacemos que todo esto corra solo y sea reproducible?

|

---

## 1. El Concepto Integrador

Las asignaturas forman una columna vertebral continua donde la salida de cada módulo es la entrada indispensable del siguiente:

1. **Bases de Datos Analíticas:** Fundación mediante _star schema_, PostgreSQL, dbt y Metabase.

2. **Shell Scripting (DataOps):** Ingesta continua de variables _driver_ vía APIs públicas, orquestación y monitoreo.

3. **Estadística II:** Validación empírica de hipótesis y relaciones de demanda.

4. **Métodos Numéricos:** Ajuste de curvas, diferenciación (elasticidad), integración (volumen) y raíces (equilibrio).

5. **Optimización:** Modelado prescriptivo (programación lineal, transporte, asignación, redes y entera).

6. **Decisión:** Dashboards analíticos y reportes ejecutivos reproducibles.

---

## 2. Arquitectura del Producto

- **Fuente OLTP:** PostgreSQL (esquema raw) con carga vía `dlt`.

- **Transformación:** dbt (staging $\rightarrow$ marts) construyendo el _star schema_ por rebanadas verticales.

- **Orquestación / DataOps:** Dagster + Shell scripts (`bash`) + cron.

- **Consumo / BI:** Metabase para tableros descriptivos y entrega de decisiones.

- **Capa Analítica:** Python consumiendo directamente las tablas _marts_ validadas.

> **Principio de diseño:** Ningún grupo empieza limpiando datos manualmente. La calidad del dato queda garantizada por el modelo dimensional y los tests de dbt.

---

## 3. Módulos y Entregables por Asignatura

**Bases de Datos Analíticas (Fundación)**

- Tablas de hechos y dimensiones validadas (`fact_*`, `dim_*`).

- Dashboards descriptivos de línea base.

**Estadística II (Diagnóstico e Inferencia)**

- Muestreo sobre la población finita del almacén y verificación del Teorema del Límite Central.

- Intervalos de confianza y $\ge 3$ pruebas de hipótesis (medias, proporciones, varianzas).

- Tablas de contingencia y prueba Ji-Cuadrado de independencia.

- Regresión lineal con validación completa de supuestos (normalidad de residuos, homocedasticidad).

- **Handoff:** Relación de demanda validada (variable _driver_ externa confirmada).

**Métodos Numéricos (Cuantificación y Pronóstico)**

- Regresión polinomial / Trazador cúbico (splines) vs. Interpolación de Lagrange/Newton.

- Diferenciación numérica (diferencias finitas) para cálculo de elasticidad y tasas de cambio.

- Integración numérica (Trapecio, Simpson, Gauss) para estimar demanda total acumulada.

- Ecuaciones no lineales (Newton-Raphson, Bisección) para punto de equilibrio y precio óptimo.

- **Handoff:** Coeficientes numéricos, curvas de demanda y funciones de costo/ingreso.

**Optimización (Prescripción y Decisión)**

- Programación Lineal (Simplex, Dualidad, Análisis de Sensibilidad y Precios Sombra).

- Modelos de Transporte (Vogel, Costo Mínimo) y Asignación (Algoritmo Húngaro).

- Modelos de Redes (Ruta Crítica / CPM, Árbol de Expansión, Camino más Corto).

- Programación Entera (Problema de la Mochila, Agente Viajero / TSP).

- **Handoff:** Plan de operaciones óptimo (cantidades, rutas, asignaciones y presupuesto).

**Shell Scripting (Capa Operativa DataOps)**

- `ingesta.sh`: Consumo de APIs públicas, parseo con `awk`/`sed`/`jq` y disparo del pipeline.

- `orquestador.sh`: Menú interactivo con ejecución secuencial y control de salida (`PASS`/`WARN`/`ERROR`).

- `monitor.sh`: Supervisión de CPU, memoria y salud de procesos/contenedores mediante `trap`.

- `exportar_resultados.sh`: Extracción versionada de datos vía `psql` para consumo analítico.

---

## 4. Casos Asignados

### Caso 1: Antojitos Express (Cocina Fantasma / Delivery)

- **Fuente OLTP:** Órdenes, ítems por pedido, zonas de cobertura/entrega, catálogo y repartidores.

- **Driver continuo:** Nivel de precipitación diaria (la lluvia eleva la demanda de delivery) o índice de congestión de tráfico.

- **Enriquecimiento API:** Datos meteorológicos históricos/pronóstico (Open-Meteo) o APIs de tipo de cambio para insumos importados.

- **Ji-Cuadrado:** Categoría de platillo vs. Zona geográfica de entrega.

- **Optimización:**
- Asignación de repartidores a zonas críticas (Algoritmo Húngaro).

- Optimización de rutas de despacho multientrega (Problema del Agente Viajero / TSP).

- Mezcla óptima de preparación de platillos en cocina bajo capacidad de hornos/estaciones (Programación Lineal).

- Selección de campañas y combos bajo presupuesto publicitario limitado (Problema de la Mochila).

### Caso 2: Cooperativa El Volcán (Café de Exportación)

- **Fuente OLTP:** Registro de acopio por productor, lotes recolectados, pesaje de beneficio húmedo/seco y embarques de exportación.

- **Driver continuo:** Precipitación acumulada/temperatura en zonas de cultivo, o cotización internacional del café en bolsa (ICE Futures).

- **Enriquecimiento API:** API climática agropecuaria o API financiera de precios de _commodities_ / tipo de cambio.

- **Ji-Cuadrado:** Variedad de café (Arábica, Catuaí, Bourbon) vs. Región de origen, o Calidad de taza (puntaje SCAA) vs. Rango de altura de finca.

- **Optimización:**
- Red de distribución y fletes desde fincas $\rightarrow$ plantas de beneficio $\rightarrow$ puerto de exportación (Modelo de Transporte / Costo Mínimo).

- Selección de lotes especiales de alta gama para maximizar retorno en subastas bajo restricciones de volumen (Problema de la Mochila).

- Asignación de cuadrillas de corte y recolección a parcelas según maduración (Problema de Asignación).

- Programación del ciclo de cosecha, secado y procesamiento (Ruta Crítica / CPM).

### Caso 3: MoviGo (Transporte por Aplicación)

- **Fuente OLTP:** Registro de viajes solicitados, telemetría de conductores, zonas urbanas, tarifas cobradas y tiempos de espera.

- **Driver continuo:** Severidad de lluvia y hora pico del día (variables determinantes de la demanda y el multiplicador dinámico).

- **Enriquecimiento API:** Clima en tiempo real por cuadrante urbano.

- **Ji-Cuadrado:** Método de pago seleccionado (Efectivo, Tarjeta, Billetera digital) vs. Zona socioeconómica/origen.

- **Optimización:**
- Asignación y balanceo de flotilla de conductores hacia zonas de alta demanda (Algoritmo Húngaro / Despacho).

- Ruteo eficiente y evasión de congestión (Ruta más Corta sobre grafos viales).

- Calibración prescriptiva del multiplicador de tarifa dinámica derivado de la elasticidad-precio calculada numéricamente.

- Asignación de bonos e incentivos a conductores bajo presupuesto mensual fijo (Problema de la Mochila).

---

## 5. Contratos de Datos entre Módulos

| Módulo origen          | Artefacto entregado                            | Formato / Protocolo | Consumidor |
| ---------------------- | ---------------------------------------------- | ------------------- | ---------- |
| **Bases de Datos**<br> | Esquema dimensional limpio (`fact_*`, `dim_*`) |

| Tablas _marts_ en PostgreSQL

| Todos los módulos

|
| **Shell Scripting**<br> | Variable _driver_ externa procesada

| Tabla staging/raw en Postgres

| Estadística II

|
| **Estadística II**<br> | Relación validada (coeficientes, $r$, $p$-valores)

| CSV / Tabla versionada

| Métodos Numéricos

|
| **Métodos Numéricos**<br> | Curvas ajustadas, elasticidades y pronósticos

| Parámetros estructurados

| Optimización

|
| **Optimización**<br> | Asignaciones óptimas y plan de operaciones

| Tabla mart de resultados

| Metabase / Reporte

|

---

## 6. Fases de Ejecución

- **Fase 1 (Bases de Datos + Shell):** Despliegue de entorno, construcción del _star schema_ y pipeline de ingesta automatizada del driver vía API.

- **Fase 2 (Estadística II):** Muestreo analítico, verificación de supuestos, pruebas de hipótesis, Ji-cuadrado y regresión confirmada.

- **Fase 3 (Métodos Numéricos):** Ajuste de funciones continuas, cálculo de elasticidades, estimación de volumen bajo la curva y raíces.

- **Fase 4 (Optimización):** Formulación y solución de modelos lineales, enteros y de redes; análisis de sensibilidad.

- **Fase 5 (Shell + Integración):** Enlace de punta a punta mediante `orquestador.sh` y despliegue del reporte final de decisión en Metabase.

---

## 7. Rúbrica de Evaluación

- **Bases de Datos Analíticas (15%):** Modelado dimensional correcto, transformaciones en dbt, pruebas de esquema y vistas base.

- **Estadística II (18%):** Pruebas de hipótesis formales ($\ge 3$), Ji-Cuadrado de independencia y regresión con supuestos validados.

- **Métodos Numéricos (18%):** Ajuste comparativo de curvas, diferenciación, integración numérica y cálculo de raíces con análisis de convergencia.

- **Optimización (18%):** Formulación de $\ge 2$ modelos de optimización resueltos e interpretación operativa de precios sombra/sensibilidad.

- **Shell Scripting (15%):** Ingesta limpia vía API, menú de orquestación, script de monitoreo y exportación estructurada.

- **Integración End-to-End (16%):** Trazabilidad completa desde el dato crudo hasta la recomendación prescriptiva en el tablero.
