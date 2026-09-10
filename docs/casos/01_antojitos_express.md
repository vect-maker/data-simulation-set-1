# Guía del Proyecto: Caso 1 - Antojitos Express (Managua, Nicaragua)

## 1. Contexto del Negocio

**Antojitos Express** es una red de cocinas fantasma (*ghost kitchens*) y servicio de delivery ubicada en el área metropolitana de **Managua, Nicaragua**. Opera una oferta gastronómica que combina comida típica nicaragüense (fritangas, quesillos de Nagarote/La Paz Centro, asados) con opciones contemporáneas (hamburguesas artesanales, bebidas y postres tradicionales como tres leches y buñuelos).

El negocio enfrenta alta volatilidad operativa debido a:
- **Clima tropical extremo:** Durante la época lluviosa (mayo a noviembre), las fuertes precipitaciones en Managua aumentan drásticamente la demanda de pedidos a domicilio, al tiempo que reducen la velocidad y seguridad de los repartidores en motocicleta.
- **Cuellos de botella en cocina:** Capacidad finita de hornos, freidoras y horas-hombre de cocineros en horas pico (almuerzo 12:00–14:00 y cena 19:00–21:30).
- **Asignación logística:** Emparejamiento óptimo entre zonas de alta demanda (Los Robles, Villa Fontana, Altamira, Bello Horizonte) y repartidores según tipo de vehículo (moto, bicicleta, auto).

---

## 2. Diccionario de Datos Relacional (`raw_staging`)

El esquema relacional normalizado en 3NF se encuentra en el esquema PostgreSQL `raw_staging`:

| Tabla | Clave Primaria | Claves Foráneas | Descripción |
| :--- | :--- | :--- | :--- |
| `zonas` | `id_zona` | - | 12 zonas de Managua con coordenadas GPS, distancia base y tarifa de envío. |
| `repartidores` | `id_repartidor` | - | Flota de repartidores activos, tipo de vehículo y calificación. |
| `categorias_platillo`| `id_categoria` | - | Categorías del menú (Fritanga, Quesillos, Hamburguesas, Bebidas, Postres). |
| `platillos` | `id_platillo` | `id_categoria` | Catálogo de platillos con costo de insumos, precio y tiempo de cocción. |
| `promociones` | `id_promocion` | - | Campañas de mercadeo con costo y retorno esperado para optimización. |
| `clima_diario` | `fecha` | - | Serie de tiempo meteorológica de Managua (lluvia en mm, temperatura, cielo). |
| `ordenes` | `id_orden` | `id_zona`, `id_repartidor`, `id_promocion` | Encabezado transaccional de órdenes con estado, método de pago y totales. |
| `detalle_ordenes` | `id_detalle` | `id_orden`, `id_platillo` | Líneas de detalle con cantidad, precio unitario y subtotal. |
| `auditoria_ordenes` | `id_auditoria` | - | Tabla de trazabilidad poblada automáticamente por disparador (`AFTER UPDATE`). |

---

## 3. Objetos Avanzados de Base de Datos

* **Trigger de Auditoría (`trg_auditar_ordenes`):** Registra cada transición de estado en la orden con usuario (`CURRENT_USER`) y marca de tiempo.
* **Trigger de Negocio (`trg_validar_cronologia_orden`):** Impide inconsistencias de negocio donde `fecha_hora_entrega < fecha_hora_creacion`.
* **Función PL/pgSQL (`fn_calcular_total_orden`):** Calcula el total consolidando detalle, envío y propinas.
* **Vista Materializada (`mv_resumen_diario_ventas`):** Agregación diaria por zona con índice único para reporting de alto rendimiento.

---

## 4. Retos y Entregables por Asignatura

### A. Bases de Datos Relacionales & Analíticas
1. Inspeccionar el modelo entidad-relación y verificar el cumplimiento de la Tercera Forma Normal (3NF).
2. Construir un pipeline en **dbt** para transformar los datos crudos de `raw_staging` hacia un modelo dimensional *Star Schema* (`fact_ordenes`, `dim_tiempo`, `dim_zona`, `dim_platillo`, `dim_repartidor`).
3. Probar los triggers y la función almacenada mediante transacciones controladas.
4. Diseñar un dashboard analítico en **Metabase** mostrando ticket promedio, platillos más vendidos y cumplimiento de entrega.

### B. Shell Scripting (DataOps)
1. Consumir la API meteorológica de Managua utilizando `curl` con reintentos exponenciales y extracción mediante `jq`.
2. Crear un script que valide la integridad de los archivos CSV antes de cargarlos a PostgreSQL.
3. Automatizar el refresco periódico de `mv_resumen_diario_ventas` mediante una tarea `cron`.

### C. Estadística II
1. **Regresión Lineal Simple:** Ajustar el modelo $Pedidos = \beta_0 + \beta_1 \cdot Lluvia\_mm + \epsilon$.
2. **Tabla ANOVA:** Descomponer las sumas de cuadrados (Regresión, Residual, Total) y calcular el estadístico $F$ y $R^2$.
3. **Validación de Supuestos Gauss-Markov:**
   - Normalidad de residuos (Test de Shapiro-Wilk).
   - Homocedasticidad (Test de Breusch-Pagan).
   - Independencia de residuos (Estadístico de Durbin-Watson).
4. **Pruebas de Hipótesis Formales:**
   - $t$-Student: ¿Es el ticket promedio en días lluviosos significativamente mayor que en días secos?
   - $z$-proporciones: ¿Se eleva la tasa de cancelación durante aguaceros fuertes?
   - ANOVA de un factor: ¿Difieren los tiempos de entrega según el tipo de vehículo (moto, bici, auto)?
5. **Prueba Ji-Cuadrado ($\chi^2$):** Demostrar la dependencia entre la categoría de platillo pedida y la zona urbana de Managua ($p < 0.01$).

### D. Métodos Numéricos
1. **Búsqueda de Raíces:** Hallar el punto de equilibrio operativo de la cocina fantasma $\pi(q) = R(q) - C(q) = 0$ aplicando Bisección y Newton-Raphson, comparando iteraciones y velocidad de convergencia.
2. **Diferenciación Numérica:** Calcular la elasticidad-precio de la demanda mediante diferencias finitas centradas de orden $\mathcal{O}(h^2)$ sobre la curva de precios de platillos populares.
3. **Integración Numérica:** Estimar el volumen continuo de demanda horaria acumulada integrando el flujo de pedidos con la Regla de Simpson 1/3 y regla Trapezoidal.

### E. Optimización
1. **Programación Lineal (Simplex):** Formular la mezcla óptima de preparación diaria de platillos que maximice el margen bruto sujeto a la capacidad horaria de hornos, freidoras y cocineros. Interpretar los **precios sombra** de cada restricción.
2. **Algoritmo Húngaro (Asignación Biyectiva):** Asignar repartidores a pedidos pendientes minimizando el tiempo total de espera de los clientes.
3. **Problema de la Mochila (Knapsack 0/1):** Seleccionar la cartera óptima de promociones bajo un presupuesto publicitario mensual de C$ 50,000 NIO para maximizar las ventas incrementales.

---

## 5. Consultas SQL de Inicio Rápido
Consulte el archivo `queries/01_antojitos_express.sql` para ejecutar ejemplos funcionales sobre PostgreSQL.
