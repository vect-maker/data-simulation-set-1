# Guía del Proyecto: Caso 2 - Cooperativa El Volcán (Jinotega, Nicaragua)

## 1. Contexto del Negocio

La **Cooperativa de Servicios Agropecuarios El Volcán R.L.** agrupa a decenas de pequeños y medianos caficultores en las zonas montañosas del norte de Nicaragua: **Jinotega**, **Matagalpa**, **Nueva Segovia (Dipilto)** y **Madriz**. Produce y procesa cafés especiales de estricta altura (SHG - *Strictly High Grown*) destinados a mercados de exportación en Europa, Norteamérica y Asia.

La cadena de valor agroindustrial abarca:
1. **Recolección en finca:** Labores de corte selectivo de cerezas maduras a diferentes altitudes (1,000 a 1,650 msnm).
2. **Acopio y Beneficio Húmedo:** Despulpado, fermentación y lavado del grano.
3. **Secado y Beneficio Seco:** Deshidratación en patios solares y camas africanas hasta alcanzar la humedad objetivo óptima (11.5%), seguido de trillado y clasificación.
4. **Catación y Subasta:** Evaluación del puntaje SCAA (80 a 90+ puntos) para ventas convencionales o lotes exclusivos de subasta internacional (*Cup of Excellence*).
5. **Logística de Exportación:** Fletes terrestres desde plantas de beneficio hacia **Puerto Corinto (Chinandega)** para embarque marítimo.

---

## 2. Diccionario de Datos Relacional (`raw_staging_volcan`)

| Tabla | Clave Primaria | Claves Foráneas | Descripción |
| :--- | :--- | :--- | :--- |
| `fincas` | `id_finca` | - | Fincas socias con altitud (msnm), municipio, productor y área en manzanas. |
| `variedades_cafe` | `id_variedad` | - | Variedades botánicas (Caturra, Bourbon, Geisha, Pacamara, Maragogipe, Catuaí). |
| `beneficios` | `id_beneficio` | - | Plantas de beneficio húmedo y seco con capacidad y costos operativos. |
| `cuadrillas_corte` | `id_cuadrilla` | - | Cuadrillas de recolectores temporales con rendimiento en latas/día y costo jornal. |
| `clima_zonas_cafetaleras` | `fecha` | - | Datos agroclimáticos diarios de Jinotega (lluvia, temperatura media, min y max). |
| `lotes_acopio` | `id_lote` | `id_finca`, `id_variedad` | Lotes recolectados con peso bruto, humedad inicial y puntaje de catación SCAA. |
| `procesamiento_beneficio` | `id_proceso` | `id_lote`, `id_beneficio` | Etapas industriales de despulpado, secado y trillado con control de mermas. |
| `subastas_especiales` | `id_subasta` | - | Convocatorias de subastas con cupo de volumen y retorno esperado (Mochila). |
| `embarques_exportacion` | `id_embarque` | - | Contratos de exportación marítima vía Puerto Corinto con precio FOB en USD. |
| `auditoria_lotes` | `id_auditoria` | - | Bitácora de cambios de estado del grano poblada por trigger. |

---

## 3. Objetos Avanzados de Base de Datos

* **Trigger de Auditoría (`trg_auditar_lotes`):** Registra cualquier cambio en el estado del lote (`acopiado`, `en_beneficio`, `listo_embarque`, `exportado`).
* **Procedimiento Almacenado (`sp_cerrar_etapa_beneficio`):** Ejecuta la liquidación de rendimientos, actualización de merma porcentual y peso de salida en una transacción ACID con control de excepciones.
* **Vista Materializada (`mv_resumen_exportacion_pais`):** Muestra el consolidado de sacos de 69 kg, valor FOB total en dólares y precio promedio por libra por país de destino.

---

## 4. Retos y Entregables por Asignatura

### A. Bases de Datos Relacionales & Analíticas
1. Modelar el *Star Schema* en **dbt** (`fact_acopio_cafe`, `fact_exportaciones`, `dim_finca`, `dim_variedad`, `dim_tiempo`).
2. Probar la atomicidad de `sp_cerrar_etapa_beneficio` validando que rechace mermas negativas o procesos inexistentes.
3. Crear tableros en **Metabase** sobre rendimientos de quintales por manzana y distribución de puntajes SCAA.

### B. Shell Scripting (DataOps)
1. Automatizar la descarga del clima de Jinotega desde Open-Meteo vía Bash script y parsear con `awk` y `sed`.
2. Crear un monitor de integridad que genere alertas si los pesos de salida superan los pesos de entrada en el beneficio.

### C. Estadística II
1. **Regresión Lineal Simple:** Modelar la relación entre la altitud de la finca ($msnm$) y el puntaje de catación ($SCAA$).
2. **Diagnóstico Gauss-Markov:** Evaluar normalidad (Shapiro-Wilk), homocedasticidad (Breusch-Pagan) e independencia (Durbin-Watson).
3. **Pruebas de Hipótesis:**
   - $t$-Student: Comparar el precio liquidado entre lotes cultivados a más de 1,300 msnm vs. menores a 1,300 msnm.
   - $z$-proporciones: Probar si la proporción de lotes especiales (SCAA $\ge 85$) es significativamente mayor en Jinotega vs. Matagalpa.
   - ANOVA de un factor: Comparar rendimientos por quintal entre variedades botánicas (Geisha vs. Caturra vs. Bourbon).
4. **Prueba Ji-Cuadrado ($\chi^2$):** Probar la asociación entre la variedad de café y la región de cultivo ($p < 0.01$).

### D. Métodos Numéricos
1. **Cinética de Deshidratación:** Ajustar la curva exponencial de pérdida de humedad $M(t) = M_0 \cdot e^{-kt}$ mediante linealización logarítmica por mínimos cuadrados.
2. **Búsqueda de Raíces:** Resolver numéricamente mediante **Newton-Raphson** el tiempo exacto $t^*$ requerido para que el lote alcance el 11.5% de humedad de exportación.
3. **Integración Numérica:** Calcular la masa total de cerezas cosechadas durante el período pico mediante la Regla de Simpson 1/3.

### E. Optimización
1. **Modelo de Transporte (Vogel VAM / Simplex):** Determinar la asignación óptima de carga desde fincas hacia beneficios y desde beneficios hacia Puerto Corinto, minimizando los fletes totales en dólares.
2. **Problema de la Mochila (Knapsack 0/1):** Seleccionar la combinación óptima de microlotes de alta puntuación para la subasta internacional bajo una restricción de volumen máximo de contenedor (275 quintales).
3. **Gestión de Proyectos (CPM / PERT):** Identificar la ruta crítica y las holguras temporales sobre las 12 actividades del ciclo de beneficio y exportación de café.

---

## 5. Consultas SQL de Inicio Rápido
Consulte el archivo `queries/02_cooperativa_volcan.sql` para ejemplos funcionales sobre PostgreSQL.
