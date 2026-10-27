"""Pydantic schemas and response models for all cases.

Todos los esquemas están documentados en español y contextualizados para las asignaturas
del Proyecto Integrador (Bases de Datos Analíticas, Estadística II, Métodos Numéricos y Optimización).
"""

from datetime import date as dt_date, date, datetime
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Sobre uniforme de paginación REST para colecciones de datos.

    Proporciona metadatos estándar que permiten a los estudiantes iterar
    fácilmente a través de grandes volúmenes de datos usando parámetros offset y limit.
    """

    items: list[T] = Field(
        ...,
        description="Lista de registros recuperados para la página actual.",
    )
    count: int = Field(
        ...,
        description="Número de elementos contenidos en la página actual (len(items)).",
        examples=[50],
    )
    total: int = Field(
        ...,
        description="Cantidad total de registros en la base de datos que cumplen con los filtros aplicados.",
        examples=[1250],
    )
    offset: int = Field(
        ...,
        description="Desplazamiento o índice inicial aplicado en la consulta.",
        examples=[0],
    )
    limit: int = Field(
        ...,
        description="Límite máximo de registros solicitados por página (máximo 200).",
        examples=[50],
    )


# =========================================================
# Caso 1: Antojitos Express
# =========================================================


class ZonaOut(BaseModel):
    """Zona de cobertura urbana en Managua para entregas a domicilio."""

    model_config = ConfigDict(from_attributes=True)

    id_zona: int = Field(
        ...,
        description="Identificador único numérico de la zona urbana de Managua.",
        examples=[1],
    )
    nombre_zona: str = Field(
        ...,
        description="Nombre comercial o barrio de Managua (ej. Altamira, Bolonia, Los Robles, Bello Horizonte).",
        examples=["Altamira"],
    )
    latitud: float = Field(
        ...,
        description="Coordenada geográfica de latitud en grados decimales WGS84.",
        examples=[12.1245],
    )
    longitud: float = Field(
        ...,
        description="Coordenada geográfica de longitud en grados decimales WGS84.",
        examples=[-86.2654],
    )
    distancia_km: float = Field(
        ...,
        description="Distancia lineal o radial en kilómetros (km) desde la cocina central hasta la zona.",
        examples=[4.25],
    )
    tiempo_base_minutos: int = Field(
        ...,
        description="Tiempo estimado base de traslado en motocicleta en condiciones normales de tráfico (minutos).",
        examples=[18],
    )
    tarifa_envio_base: float = Field(
        ...,
        description="Costo base de envío cobrado a esta zona en Córdobas nicaragüenses (NIO).",
        examples=[45.0],
    )


class RepartidorOut(BaseModel):
    """Colaborador de la flota de reparto y logística de última milla."""

    model_config = ConfigDict(from_attributes=True)

    id_repartidor: int = Field(
        ...,
        description="Identificador único del repartidor en la flota.",
        examples=[10],
    )
    nombre: str = Field(
        ...,
        description="Nombre y apellido del repartidor.",
        examples=["Carlos Mendoza"],
    )
    tipo_vehiculo: str = Field(
        ...,
        description="Tipo de medio de transporte ('moto', 'bicicleta', 'auto'). Factor para ANOVA de tiempos.",
        examples=["moto"],
    )
    calificacion_promedio: float = Field(
        ...,
        description="Calificación promedio histórica otorgada por los clientes (escala 1.0 a 5.0).",
        examples=[4.85],
    )
    capacidad_maxima_ordenes: int = Field(
        ...,
        description="Número máximo de pedidos que puede transportar simultáneamente en su mochila térmica.",
        examples=[3],
    )
    estado: str = Field(
        ...,
        description="Estado operativo actual del repartidor ('activo', 'inactivo', 'descanso').",
        examples=["activo"],
    )


class CategoriaPlatilloOut(BaseModel):
    """Categoría del menú gastronómico y margen de contribución."""

    model_config = ConfigDict(from_attributes=True)

    id_categoria: int = Field(
        ...,
        description="Identificador único numérico de la categoría de comida.",
        examples=[1],
    )
    nombre_categoria: str = Field(
        ...,
        description="Nombre descriptivo de la categoría (ej. Tacos, Hamburguesas, Bebidas, Postres).",
        examples=["Tacos y Antojitos"],
    )
    margen_contribucion_pct: float = Field(
        ...,
        description="Margen de contribución bruto porcentual esperado de la categoría (0.00 a 1.00).",
        examples=[0.45],
    )


class PlatilloOut(BaseModel):
    """Platillo del catálogo digital, costos de elaboración y precios."""

    model_config = ConfigDict(from_attributes=True)

    id_platillo: int = Field(
        ...,
        description="Identificador único del platillo en el menú.",
        examples=[101],
    )
    id_categoria: int = Field(
        ...,
        description="Clave foránea que referencia a la categoría en categorias_platillo.",
        examples=[1],
    )
    nombre_platillo: str = Field(
        ...,
        description="Nombre comercial del platillo en la carta.",
        examples=["Quesadilla Suprema Mixta"],
    )
    precio_unitario: float = Field(
        ...,
        description="Precio de venta al público en Córdobas (NIO). Variable clave para análisis de elasticidad.",
        examples=[180.0],
    )
    costo_ingredientes: float = Field(
        ...,
        description="Costo directo de insumos e ingredientes por porción en Córdobas (NIO).",
        examples=[75.5],
    )
    tiempo_preparacion_minutos: float = Field(
        ...,
        description="Tiempo estándar de preparación en cocina (minutos).",
        examples=[12.5],
    )
    requiere_horno: bool = Field(
        ...,
        description="Indica si la preparación ocupa el horno industrial (cuello de botella operativo).",
        examples=[False],
    )
    activo: bool = Field(
        ...,
        description="Disponibilidad actual del platillo en el menú (True = disponible).",
        examples=[True],
    )


class PromocionOut(BaseModel):
    """Campaña de marketing, presupuesto y descuentos aplicados."""

    model_config = ConfigDict(from_attributes=True)

    id_promocion: int = Field(
        ...,
        description="Identificador único de la campaña promocional.",
        examples=[5],
    )
    nombre_campana: str = Field(
        ...,
        description="Nombre de la campaña publicitaria (ej. 'Martes de Tacos 2x1', 'Super Combo Fin de Semana').",
        examples=["Martes de Tacos 2x1"],
    )
    costo_campana: float = Field(
        ...,
        description="Presupuesto o costo de marketing asignado en Córdobas (NIO). Peso en el problema de la Mochila.",
        examples=[2500.0],
    )
    retorno_esperado: float = Field(
        ...,
        description="Ingreso incremental proyectado en Córdobas (NIO). Valor a maximizar en Optimización.",
        examples=[8200.0],
    )
    descuento_pct: float = Field(
        ...,
        description="Porcentaje de descuento aplicado sobre el precio del menú (0.00 a 1.00).",
        examples=[0.20],
    )
    fecha_inicio: date = Field(
        ...,
        description="Fecha de inicio de vigencia de la promoción (YYYY-MM-DD).",
        examples=["2024-03-01"],
    )
    fecha_fin: date = Field(
        ...,
        description="Fecha de culminación de la promoción (YYYY-MM-DD).",
        examples=["2024-03-31"],
    )


class ClimaDiarioOut(BaseModel):
    """Registro meteorológico diario en Managua (variable exógena de demanda)."""

    model_config = ConfigDict(from_attributes=True)

    fecha: date = Field(
        ...,
        description="Fecha del registro meteorológico en Managua (YYYY-MM-DD). Enlace temporal con órdenes.",
        examples=["2024-06-15"],
    )
    precipitacion_mm: float = Field(
        ...,
        description="Milímetros de lluvia acumulada en el día (mm). Variable predictora clave de demanda de delivery.",
        examples=[18.4],
    )
    temperatura_c: float = Field(
        ...,
        description="Temperatura ambiente media diaria en grados Celsius (°C).",
        examples=[29.8],
    )
    condicion_cielo: str = Field(
        ...,
        description="Condición atmosférica general ('despejado', 'lluvia_ligera', 'tormenta', 'nublado').",
        examples=["tormenta"],
    )


class DetalleOrdenOut(BaseModel):
    """Línea de detalle individual de platillo en una orden de compra."""

    model_config = ConfigDict(from_attributes=True)

    id_detalle: int = Field(
        ...,
        description="Identificador único numérico de la línea de detalle.",
        examples=[5001],
    )
    id_orden: int = Field(
        ...,
        description="Clave foránea que referencia a la orden principal en ordenes.",
        examples=[1250],
    )
    id_platillo: int = Field(
        ...,
        description="Clave foránea que referencia al platillo en platillos.",
        examples=[101],
    )
    cantidad: int = Field(
        ...,
        description="Cantidad de porciones o unidades solicitadas del platillo.",
        examples=[2],
    )
    precio_unitario: float = Field(
        ...,
        description="Precio unitario cobrado en Córdobas (NIO) al momento del pedido.",
        examples=[180.0],
    )
    subtotal: float = Field(
        ...,
        description="Importe subtotal calculado (cantidad * precio_unitario) en Córdobas (NIO).",
        examples=[360.0],
    )


class OrdenOut(BaseModel):
    """Histórico transaccional de pedidos y entregas a domicilio."""

    model_config = ConfigDict(from_attributes=True)

    id_orden: int = Field(
        ...,
        description="Identificador único transaccional de la orden de compra.",
        examples=[1250],
    )
    id_zona: int = Field(
        ...,
        description="Clave foránea de la zona urbana de Managua donde se realiza la entrega.",
        examples=[3],
    )
    id_repartidor: int | None = Field(
        default=None,
        description="Clave foránea del repartidor asignado (None si aún no ha sido despachada).",
        examples=[10],
    )
    id_promocion: int | None = Field(
        default=None,
        description="Clave foránea de la promoción aplicada a la orden (None si no aplicó campaña).",
        examples=[5],
    )
    fecha_hora_creacion: datetime = Field(
        ...,
        description="Marca de tiempo en que el cliente realizó el pedido (ISO 8601).",
        examples=["2024-06-15T19:30:00"],
    )
    fecha_hora_entrega: datetime | None = Field(
        default=None,
        description="Marca de tiempo en que el repartidor entregó el pedido al cliente.",
        examples=["2024-06-15T20:12:00"],
    )
    metodo_pago: str = Field(
        ...,
        description="Modalidad de pago empleada ('efectivo', 'tarjeta', 'billetera_digital').",
        examples=["billetera_digital"],
    )
    estado_orden: str = Field(
        ...,
        description="Estado del ciclo de vida de la orden ('entregada', 'cancelada', 'en_camino', 'preparando').",
        examples=["entregada"],
    )
    total_orden: float = Field(
        ...,
        description="Monto total cobrado por los alimentos en Córdobas nicaragüenses (NIO).",
        examples=[420.0],
    )
    costo_envio: float = Field(
        ...,
        description="Tarifa cobrada por el servicio de entrega a domicilio en Córdobas (NIO).",
        examples=[50.0],
    )
    propina: float = Field(
        default=0.0,
        description="Monto voluntario de propina dejado por el cliente al repartidor en Córdobas (NIO).",
        examples=[30.0],
    )
    notas_entrega: str | None = Field(
        default=None,
        description="Instrucciones especiales de entrega proporcionadas por el cliente.",
        examples=["Tocar el timbre de la casa verde"],
    )
    comentario_cliente: str | None = Field(
        default=None,
        description="Opinión o retroalimentación del comensal sobre el servicio.",
        examples=["Comida caliente y entrega rápida"],
    )
    motivo_cancelacion: str | None = Field(
        default=None,
        description="Motivo registrado en caso de cancelación del pedido.",
        examples=[None],
    )


class OrdenDetailOut(OrdenOut):
    """Orden de compra completa con la lista anidada de platillos e ítems solicitados."""

    items: list[DetalleOrdenOut] = Field(
        default_factory=list,
        description="Lista anidada con las líneas de detalle de platillos asociados a esta orden.",
    )


# =========================================================
# Caso 2: Cooperativa El Volcán
# =========================================================


class FincaOut(BaseModel):
    """Finca cafetalera asociada a la cooperativa en el norte de Nicaragua."""

    model_config = ConfigDict(from_attributes=True)

    id_finca: int = Field(
        ...,
        description="Identificador único numérico de la finca cafetalera.",
        examples=[1],
    )
    nombre_finca: str = Field(
        ...,
        description="Nombre comercial de la propiedad agrícola.",
        examples=["Finca La Cumbre"],
    )
    id_productor: int = Field(
        ...,
        description="Identificador del productor miembro asociado a la cooperativa.",
        examples=[101],
    )
    nombre_productor: str = Field(
        ...,
        description="Nombre completo del caficultor propietario.",
        examples=["Mateo Gutiérrez"],
    )
    region: str = Field(
        ...,
        description="Región cafetalera ('Jinotega', 'Matagalpa', 'Nueva Segovia - Dipilto', 'Madriz').",
        examples=["Jinotega"],
    )
    municipio: str = Field(
        ...,
        description="Municipio específico de localización de la finca.",
        examples=["San Rafael del Norte"],
    )
    latitud: float = Field(
        ...,
        description="Coordenada geográfica de latitud en grados decimales WGS84.",
        examples=[13.2124],
    )
    longitud: float = Field(
        ...,
        description="Coordenada geográfica de longitud en grados decimales WGS84.",
        examples=[-86.1105],
    )
    altitud_msnm: int = Field(
        ...,
        description="Altitud media sobre el nivel del mar (1000 a 1650 msnm). Factor determinante en la calidad del grano.",
        examples=[1350],
    )
    area_manzanas: float = Field(
        ...,
        description="Área cultivada en manzanas nicaragüenses (1 mz ≈ 0.704 hectáreas).",
        examples=[25.5],
    )


class VariedadCafeOut(BaseModel):
    """Variedad botánica de café arábica cultivada en las parcelas."""

    model_config = ConfigDict(from_attributes=True)

    id_variedad: int = Field(
        ...,
        description="Identificador único de la variedad botánica.",
        examples=[1],
    )
    nombre_variedad: str = Field(
        ...,
        description="Nombre botánico comercial ('Geisha', 'Pacamara', 'Bourbon', 'Caturra', 'Maragogipe', 'Catuaí').",
        examples=["Geisha"],
    )
    especie: str = Field(
        default="Coffea Arabica",
        description="Especie biológica del cultivo (predominantemente 'Coffea Arabica').",
        examples=["Coffea Arabica"],
    )
    perfil_sensorial_base: str = Field(
        ...,
        description="Notas organolépticas base y perfil de cata característico.",
        examples=["Jazmín, bergamota, acidez brillante y notas a durazno"],
    )
    resistencia_roya: str = Field(
        ...,
        description="Nivel de susceptibilidad al hongo de la roya Hemileia vastatrix ('alta', 'media', 'susceptible').",
        examples=["susceptible"],
    )
    rendimiento_promedio_qq_mz: float = Field(
        ...,
        description="Rendimiento agronómico promedio en quintales oro por manzana (qq/mz).",
        examples=[22.5],
    )


class BeneficioOut(BaseModel):
    """Planta agroindustrial de beneficio húmedo o seco para café."""

    model_config = ConfigDict(from_attributes=True)

    id_beneficio: int = Field(
        ...,
        description="Identificador único del beneficio agroindustrial.",
        examples=[1],
    )
    nombre_beneficio: str = Field(
        ...,
        description="Nombre o razón social de la planta de procesamiento.",
        examples=["Beneficio Central El Molino"],
    )
    tipo_beneficio: str = Field(
        ...,
        description="Tipo de procesamiento ('humedo' para despulpado/lavado, 'seco' para trillado/clasificación).",
        examples=["humedo"],
    )
    municipio: str = Field(
        ...,
        description="Municipio donde opera la instalación agroindustrial.",
        examples=["Jinotega"],
    )
    latitud: float = Field(
        ...,
        description="Coordenada geográfica de latitud de la planta.",
        examples=[13.0889],
    )
    longitud: float = Field(
        ...,
        description="Coordenada geográfica de longitud de la planta.",
        examples=[-85.9981],
    )
    capacidad_quintales_dia: float = Field(
        ...,
        description="Capacidad operativa máxima de recepción y proceso en quintales por día (qq/día).",
        examples=[500.0],
    )
    costo_procesamiento_qq: float = Field(
        ...,
        description="Costo unitario de beneficio por quintal procesado en Córdobas (NIO/qq).",
        examples=[120.0],
    )


class CuadrillaCorteOut(BaseModel):
    """Cuadrilla de recolectores para la cosecha manual de café cereza."""

    model_config = ConfigDict(from_attributes=True)

    id_cuadrilla: int = Field(
        ...,
        description="Identificador único numérico de la cuadrilla de recolectores.",
        examples=[4],
    )
    nombre_cuadrilla: str = Field(
        ...,
        description="Nombre o distintivo de la cuadrilla.",
        examples=["Cuadrilla Los Pinos"],
    )
    capacidad_recolectores: int = Field(
        ...,
        description="Cantidad total de cortadores que integran la cuadrilla.",
        examples=[18],
    )
    rendimiento_latas_dia: float = Field(
        ...,
        description="Rendimiento promedio diario de recolección en latas de café cereza.",
        examples=[145.0],
    )
    costo_jornal_dia: float = Field(
        ...,
        description="Costo de compensación diario por cortador en Córdobas (NIO/día).",
        examples=[220.0],
    )
    estado: str = Field(
        ...,
        description="Disponibilidad operativa de la cuadrilla ('activa', 'descanso', 'asignada').",
        examples=["activa"],
    )


class ClimaCafetaleroOut(BaseModel):
    """Variables agroclimáticas de montaña en regiones cafetaleras de Jinotega."""

    model_config = ConfigDict(from_attributes=True)

    fecha: date = Field(
        ...,
        description="Fecha de la observación meteorológica (YYYY-MM-DD).",
        examples=["2024-11-10"],
    )
    region: str = Field(
        ...,
        description="Zona montañosa monitoreada ('Jinotega', 'Matagalpa', etc.).",
        examples=["Jinotega"],
    )
    precipitacion_mm: float = Field(
        ...,
        description="Precipitación acumulada diaria en milímetros (mm).",
        examples=[12.5],
    )
    temperatura_media_c: float = Field(
        ...,
        description="Temperatura ambiente promedio diaria en grados Celsius (°C).",
        examples=[19.2],
    )
    temperatura_min_c: float = Field(
        ...,
        description="Temperatura mínima en horas nocturnas o madrugada (°C).",
        examples=[14.8],
    )
    temperatura_max_c: float = Field(
        ...,
        description="Temperatura máxima en horas del mediodía (°C).",
        examples=[24.5],
    )
    humedad_relativa_pct: float = Field(
        ...,
        description="Humedad relativa promedio del aire expresada en porcentaje (%).",
        examples=[84.5],
    )
    condicion_clima: str = Field(
        ...,
        description="Estado del tiempo predominante ('soleado', 'nublado', 'llovizna', 'temporal').",
        examples=["llovizna"],
    )


class LoteAcopioOut(BaseModel):
    """Lote de café cereza cosechado, recepcionado y evaluado sensorialmente."""

    model_config = ConfigDict(from_attributes=True)

    id_lote: int = Field(
        ...,
        description="Identificador único del lote de café recibido en acopio.",
        examples=[1001],
    )
    id_finca: int = Field(
        ...,
        description="Clave foránea de la finca productora donde se realizó el corte.",
        examples=[1],
    )
    id_variedad: int = Field(
        ...,
        description="Clave foránea de la variedad botánica cultivada.",
        examples=[1],
    )
    id_cuadrilla: int | None = Field(
        default=None,
        description="Clave foránea de la cuadrilla de recolección asignada.",
        examples=[4],
    )
    fecha_corte: date = Field(
        ...,
        description="Fecha en que se cosechó el café en la finca (YYYY-MM-DD).",
        examples=["2024-11-15"],
    )
    peso_cereza_kg: float = Field(
        ...,
        description="Peso bruto de café cereza fresca recibido en kilogramos (kg).",
        examples=[1850.0],
    )
    humedad_porcentaje: float = Field(
        ...,
        description="Porcentaje de humedad del grano medido al momento de recepción (%).",
        examples=[58.5],
    )
    puntaje_catacion_scaa: float = Field(
        ...,
        description="Calificación sensorial en protocolo SCAA (Specialty Coffee Association, escala 80.0 a 100.0).",
        examples=[87.5],
    )
    certificacion: str = Field(
        ...,
        description="Sello socioambiental o de calidad ('Convencional', 'Fairtrade', 'Orgánico', 'Rainforest Alliance', 'SHG').",
        examples=["Fairtrade"],
    )
    notas_catacion: str | None = Field(
        default=None,
        description="Descripción de descriptores sensoriales (aroma, acidez, cuerpo, dulzor).",
        examples=["Fragancia floral con notas de miel y jazmín"],
    )
    costo_recoleccion_nio: float = Field(
        ...,
        description="Costo total de corte y transporte al punto de acopio en Córdobas (NIO).",
        examples=[4200.0],
    )
    estado_lote: str = Field(
        ...,
        description="Fase operativa del lote ('recolectado', 'en_beneficio_humedo', 'en_secado', 'listo_exportacion', 'descartado').",
        examples=["en_beneficio_humedo"],
    )


class ProcesamientoBeneficioOut(BaseModel):
    """Etapa de transformación industrial en beneficio y control de mermas."""

    model_config = ConfigDict(from_attributes=True)

    id_proceso: int = Field(
        ...,
        description="Identificador único del registro de procesamiento.",
        examples=[201],
    )
    id_lote: int = Field(
        ...,
        description="Clave foránea del lote de café intervenido.",
        examples=[1001],
    )
    id_beneficio: int = Field(
        ...,
        description="Clave foránea del beneficio donde se realiza la transformación.",
        examples=[1],
    )
    etapa: str = Field(
        ...,
        description="Fase técnica del proceso ('despulpado', 'fermentacion', 'secado_patio', 'trillado', 'clasificacion').",
        examples=["fermentacion"],
    )
    fecha_inicio: datetime = Field(
        ...,
        description="Fecha y hora de inicio de la etapa (ISO 8601).",
        examples=["2024-11-16T08:00:00"],
    )
    fecha_fin: datetime | None = Field(
        default=None,
        description="Fecha y hora de finalización de la etapa.",
        examples=["2024-11-17T14:30:00"],
    )
    temperatura_fermentacion_c: float | None = Field(
        default=None,
        description="Temperatura controlada en tanques de fermentación (°C).",
        examples=[21.5],
    )
    merma_porcentaje: float = Field(
        ...,
        description="Pérdida porcentual de peso por deshidratación o cascabillo (0.00 a 1.00).",
        examples=[0.18],
    )
    peso_salida_kg: float = Field(
        ...,
        description="Peso neto resultante de la etapa en kilogramos (kg).",
        examples=[1517.0],
    )
    observaciones_proceso: str | None = Field(
        default=None,
        description="Anotaciones técnicas del maestro beneficiador.",
        examples=["Fermentación aeróbica de 30 horas con lavado limpio"],
    )


class SubastaEspecialOut(BaseModel):
    """Microlote de café de especialidad ofertado en subastas internacionales."""

    model_config = ConfigDict(from_attributes=True)

    id_subasta: int = Field(
        ...,
        description="Identificador único del microlote en subasta.",
        examples=[12],
    )
    id_lote: int | None = Field(
        default=None,
        description="Clave foránea del lote de café seleccionado.",
        examples=[1001],
    )
    nombre_lote_especial: str = Field(
        ...,
        description="Nombre comercial de fantasía para la subasta (ej. 'Geisha Diamante').",
        examples=["Geisha Diamante - Taza de la Excelencia"],
    )
    peso_quintales: float = Field(
        ...,
        description="Peso disponible del microlote en quintales oro (qq). Peso en el problema de la Mochila.",
        examples=[15.0],
    )
    costo_certificacion_usd: float = Field(
        ...,
        description="Costo de inscripción, auditoría y catación en Dólares (USD).",
        examples=[850.0],
    )
    retorno_esperado_usd: float = Field(
        ...,
        description="Ingreso esperado por venta en subasta en Dólares (USD). Valor a maximizar en Optimización.",
        examples=[6800.0],
    )
    puntaje_taza: float = Field(
        ...,
        description="Puntaje de catación final otorgado por el panel internacional.",
        examples=[90.5],
    )
    fecha_subasta: date = Field(
        ...,
        description="Fecha programada o celebrada de la subasta (YYYY-MM-DD).",
        examples=["2024-12-05"],
    )
    estado_subasta: str = Field(
        ...,
        description="Resultado de la puja ('programada', 'adjudicada', 'desierta').",
        examples=["adjudicada"],
    )


class EmbarqueExportacionOut(BaseModel):
    """Despacho marítimo de café oro con destino a mercados internacionales."""

    model_config = ConfigDict(from_attributes=True)

    id_embarque: int = Field(
        ...,
        description="Identificador único numérico del embarque de exportación.",
        examples=[88],
    )
    id_lote: int = Field(
        ...,
        description="Clave foránea del lote de café exportado.",
        examples=[1001],
    )
    numero_contenedor: str = Field(
        ...,
        description="Código alfanumérico internacional del contenedor marítimo.",
        examples=["MSKU9082341"],
    )
    puerto_salida: str = Field(
        default="Puerto Corinto, Nicaragua",
        description="Puerto marítimo de zarpe (ej. 'Puerto Corinto, Nicaragua').",
        examples=["Puerto Corinto, Nicaragua"],
    )
    pais_destino: str = Field(
        ...,
        description="País comprador ('Alemania', 'Estados Unidos', 'Japón', 'Bélgica', 'Taiwán', 'Italia').",
        examples=["Alemania"],
    )
    cliente_comprador: str = Field(
        ...,
        description="Nombre de la empresa tostadora o importadora extranjera.",
        examples=["Hamburg Specialty Roasters GmbH"],
    )
    fecha_embarque: date = Field(
        ...,
        description="Fecha de despacho o zarpe aduanero (YYYY-MM-DD).",
        examples=["2024-12-20"],
    )
    peso_oro_quintales: float = Field(
        ...,
        description="Volumen exportado en quintales de café oro (qq).",
        examples=[275.0],
    )
    precio_quintal_usd: float = Field(
        ...,
        description="Precio acordado por quintal según contrato en Dólares (USD/qq).",
        examples=[245.0],
    )
    flete_transporte_usd: float = Field(
        ...,
        description="Costo de transporte terrestre y flete marítimo en Dólares (USD).",
        examples=[1800.0],
    )
    total_usd: float = Field(
        ...,
        description="Facturación total bruta de la exportación en Dólares (USD).",
        examples=[67375.0],
    )


# =========================================================
# Caso 3: MoviGo
# =========================================================


class QuadrantOut(BaseModel):
    """Cuadrante cuadrado fino (~0.88 km x 0.88 km) dentro de una zona urbana de Managua."""

    model_config = ConfigDict(from_attributes=True)

    quadrant_id: int = Field(
        ...,
        description="Identificador único numérico del cuadrante cuadrado en la grilla de Managua (1 a 92).",
        examples=[53],
    )
    zone_id: int = Field(
        ...,
        description="Clave foránea de la zona urbana padre a la que pertenece el cuadrante (1 a 12).",
        examples=[11],
    )
    district: str = Field(
        default="Distrito I",
        description="Distrito municipal oficial de Managua al que pertenece el cuadrante (Distrito I a VII).",
        examples=["Distrito IV"],
    )
    quadrant_code: str = Field(
        ...,
        description="Código corto estandarizado del cuadrante y su zona urbana.",
        examples=["Q53-Z11"],
    )
    quadrant_name: str = Field(
        ...,
        description="Nombre descriptivo de la zona, cuadrante y coordenadas de fila/columna en la grilla.",
        examples=["Mercado Oriental - Cuadrante Q53 (F7C9)"],
    )
    grid_row: int = Field(
        ...,
        description="Índice de fila de sur a norte en la grilla espacial de Managua.",
        examples=[6],
    )
    grid_col: int = Field(
        ...,
        description="Índice de columna de oeste a este en la grilla espacial de Managua.",
        examples=[8],
    )
    lat_min: float = Field(
        ...,
        description="Límite sur de latitud del cuadrante cuadrado (WGS84).",
        examples=[12.134],
    )
    lat_max: float = Field(
        ...,
        description="Límite norte de latitud del cuadrante cuadrado (WGS84).",
        examples=[12.142],
    )
    lon_min: float = Field(
        ...,
        description="Límite oeste de longitud del cuadrante cuadrado (WGS84).",
        examples=[-86.252],
    )
    lon_max: float = Field(
        ...,
        description="Límite este de longitud del cuadrante cuadrado (WGS84).",
        examples=[-86.244],
    )
    mean_altitude_masl: int = Field(
        ...,
        description="Altitud media sobre el nivel del mar en metros (msnm). Determina el drenaje sur-norte.",
        examples=[58],
    )
    flood_risk: str = Field(
        ...,
        description="Nivel de vulnerabilidad a anegamientos por cauces ('bajo', 'medio', 'alto', 'critico').",
        examples=["critico"],
    )
    main_drainage_channels: str = Field(
        ...,
        description="Principales cauces pluviales, pasos a desnivel y arterias dentro o contiguas al cuadrante.",
        examples=["Cauce Oriental / Gancho de Camino"],
    )


class UrbanZoneOut(BaseModel):
    """Zona urbana comercial y de tarifación en Managua (agrupa múltiples cuadrantes cuadrados)."""

    model_config = ConfigDict(from_attributes=True)

    zone_id: int = Field(
        ...,
        description="Identificador único numérico de la zona urbana de Managua (1 a 12).",
        examples=[1],
    )
    zone_name: str = Field(
        ...,
        description="Nombre comercial o referencia urbana (ej. Metrocentro, Villa Fontana, Mercado Oriental).",
        examples=["Villa Fontana"],
    )
    district: str = Field(
        default="Distrito I",
        description="Distrito municipal oficial de Managua (Distrito I a VII).",
        examples=["Distrito I"],
    )
    socioeconomic_stratum: str = Field(
        ...,
        description="Estrato económico de la zona urbana ('alto', 'medio', 'popular', 'comercial').",
        examples=["comercial"],
    )
    latitude: float = Field(
        ...,
        description="Latitud geográfica del centroide de la zona en grados decimales WGS84.",
        examples=[12.1275],
    )
    longitude: float = Field(
        ...,
        description="Longitud geográfica del centroide de la zona en grados decimales WGS84.",
        examples=[-86.2658],
    )
    coverage_radius_km: float = Field(
        ...,
        description="Radio operativo de cobertura en kilómetros (km).",
        examples=[2.5],
    )
    base_flag_drop_fare: float = Field(
        ...,
        description="Tarifa base fija de bajada de bandera al iniciar el viaje en Córdobas (NIO).",
        examples=[35.0],
    )


class UserOut(BaseModel):
    """Pasajero registrado en la aplicación de transporte."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(
        ...,
        description="Identificador único numérico del pasajero en la plataforma.",
        examples=[501],
    )
    name: str = Field(
        ...,
        description="Nombre completo del usuario pasajero.",
        examples=["Sofía Morales"],
    )
    phone: str = Field(
        ...,
        description="Número de teléfono móvil de contacto (+505).",
        examples=["+505 8899-1122"],
    )
    preferred_payment_method: str = Field(
        ...,
        description="Modalidad de pago configurada ('efectivo', 'tarjeta', 'billetera_digital').",
        examples=["tarjeta"],
    )
    average_rating: float = Field(
        ...,
        description="Calificación promedio histórica como pasajero (escala 1.0 a 5.0).",
        examples=[4.92],
    )
    registration_date: date = Field(
        ...,
        description="Fecha de creación de la cuenta en la plataforma (YYYY-MM-DD).",
        examples=["2023-08-14"],
    )


class DriverOut(BaseModel):
    """Socio conductor registrado en la flota."""

    model_config = ConfigDict(from_attributes=True)

    driver_id: int = Field(
        ...,
        description="Identificador único del socio conductor en la flota.",
        examples=[205],
    )
    name: str = Field(
        ...,
        description="Nombre y apellido del conductor.",
        examples=["Ernesto Chamorro"],
    )
    average_rating: float = Field(
        ...,
        description="Calificación promedio histórica recibida de pasajeros (escala 1.0 a 5.0).",
        examples=[4.88],
    )
    acceptance_rate_pct: float = Field(
        ...,
        description="Tasa histórica de aceptación de solicitudes de viaje en porcentaje (50.0 a 100.0).",
        examples=[94.0],
    )
    status: str = Field(
        ...,
        description="Disponibilidad operativa actual ('activo', 'inactivo', 'en_viaje', 'desconectado').",
        examples=["activo"],
    )


class VehicleOut(BaseModel):
    """Unidad vehicular asignada al socio conductor en la flota MoviGo."""

    model_config = ConfigDict(from_attributes=True)

    vehicle_id: int = Field(
        ...,
        description="Identificador único numérico de la unidad vehicular.",
        examples=[1],
    )
    driver_id: int = Field(
        ...,
        description="Clave foránea del socio conductor que opera la unidad.",
        examples=[1],
    )
    service_type: str = Field(
        ...,
        description="Categoría del servicio prestado ('movigo_estandar', 'movigo_comfort', 'movigo_moto').",
        examples=["movigo_estandar"],
    )
    vehicle_model: str = Field(
        ...,
        description="Marca y modelo del automóvil o moto.",
        examples=["Toyota Yaris"],
    )
    vehicle_year: int = Field(
        ...,
        description="Año de fabricación del vehículo automotor.",
        examples=[2021],
    )
    license_plate: str = Field(
        ...,
        description="Matrícula vehicular de Managua (ej. 'M-123456').",
        examples=["M-123456"],
    )
    fuel_type: str = Field(
        default="gasolina_regular",
        description="Tipo de combustible utilizado por la unidad vehicular.",
        examples=["gasolina_regular"],
    )
    fuel_efficiency_km_l: float = Field(
        default=13.5,
        description="Rendimiento promedio de combustible en kilómetros por litro.",
        examples=[13.5],
    )
    initial_odometer_km: float = Field(
        default=35000.0,
        description="Kilometraje acumulado del odómetro al inicio del periodo operativo.",
        examples=[35000.0],
    )


class VehicleMaintenanceOut(BaseModel):
    """Registro de mantenimiento preventivo o correctivo de unidades de la flota MoviGo."""

    model_config = ConfigDict(from_attributes=True)

    maintenance_id: int = Field(
        ...,
        description="Identificador único del registro de mantenimiento.",
        examples=[1],
    )
    vehicle_id: int = Field(
        ...,
        description="Clave foránea de la unidad vehicular atendida en taller.",
        examples=[12],
    )
    service_date: date = Field(
        ...,
        description="Fecha en que se ejecutó el servicio de mantenimiento.",
        examples=["2024-03-15"],
    )
    maintenance_type: str = Field(
        ...,
        description="Tipo de intervención técnica ('preventivo' por kilometraje o 'correctivo' por avería).",
        examples=["preventivo"],
    )
    odometer_km: float = Field(
        ...,
        description="Lectura del odómetro en kilómetros al momento de ingresar al taller.",
        examples=[40250.5],
    )
    description: str = Field(
        ...,
        description="Descripción detallada de los trabajos técnicos ejecutados.",
        examples=["Cambio de aceite, filtro y revisión de frenos 5,000 km"],
    )
    cost_nio: float = Field(
        ...,
        description="Costo total de mano de obra y repuestos en Córdobas (NIO).",
        examples=[3450.0],
    )
    downtime_hours: float = Field(
        ...,
        description="Horas de inactividad de la unidad vehicular en taller.",
        examples=[4.5],
    )
    workshop_name: str = Field(
        ...,
        description="Nombre del taller mecánico autorizado en Managua.",
        examples=["Taller Central MoviGo Bolonia"],
    )


class IncentiveCampaignOut(BaseModel):
    """Programa de bonos y estímulos para horas de conexión de conductores."""

    model_config = ConfigDict(from_attributes=True)

    campaign_id: int = Field(
        ...,
        description="Identificador único del programa de incentivos.",
        examples=[8],
    )
    target_zone_id: int = Field(
        ...,
        description="Clave foránea de la zona urbana de Managua donde se focaliza la campaña.",
        examples=[2],
    )
    bonus_name: str = Field(
        ...,
        description="Nombre del bono o reto operativo (ej. 'Bono Aguacero Nocturno').",
        examples=["Bono Aguacero Nocturno"],
    )
    budget_cost_nio: float = Field(
        ...,
        description="Presupuesto asignado al bono en Córdobas (NIO). Peso en el problema de la Mochila.",
        examples=[12000.0],
    )
    online_hours_increase: float = Field(
        ...,
        description="Aumento estimado en horas de conexión activa. Retorno a maximizar en Optimización.",
        examples=[180.0],
    )
    incentive_type: str = Field(
        ...,
        description="Mecánica del incentivo ('meta_viajes', 'hora_pico_lluvia', 'zona_alta_demanda').",
        examples=["hora_pico_lluvia"],
    )
    start_date: date = Field(
        ...,
        description="Fecha de inicio de la vigencia (YYYY-MM-DD).",
        examples=["2024-05-01"],
    )
    end_date: date = Field(
        ...,
        description="Fecha de cierre de la vigencia (YYYY-MM-DD).",
        examples=["2024-05-31"],
    )
    status: str = Field(
        ...,
        description="Estado del programa ('activa', 'finalizada').",
        examples=["activa"],
    )


class QuadrantWeatherOut(BaseModel):
    """Condición climática horaria, escorrentía de cauces e índice de congestión vehicular por cuadrante en Managua."""

    model_config = ConfigDict(from_attributes=True)

    weather_id: int = Field(
        ...,
        description="Identificador único del registro horario de clima por cuadrante.",
        examples=[1024],
    )
    quadrant_id: int = Field(
        ...,
        description="Clave foránea del cuadrante cuadrado geográfico monitoreado (1 a 92).",
        examples=[53],
    )
    recorded_at: datetime = Field(
        ...,
        description="Marca de tiempo horaria del registro meteorológico y vial (ISO 8601).",
        examples=["2024-05-18T17:00:00"],
    )
    date: dt_date = Field(
        ...,
        description="Fecha calendario de la observación (YYYY-MM-DD).",
        examples=["2024-05-18"],
    )
    hour: int = Field(
        ...,
        description="Hora del día en formato 24 horas (0 a 23).",
        examples=[17],
    )
    precipitation_mm: float = Field(
        ...,
        description="Milímetros de lluvia caída directamente sobre el cuadrante en esa hora (mm).",
        examples=[8.4],
    )
    channel_runoff_mm: float = Field(
        ...,
        description="Lámina de agua efectiva y escorrentía pluvial acumulada en cauces desde cuadrantes altos del sur (mm).",
        examples=[12.6],
    )
    temperature_c: float = Field(
        ...,
        description="Temperatura ambiente horaria en el cuadrante en grados Celsius (°C).",
        examples=[27.8],
    )
    congestion_index: float = Field(
        ...,
        description="Índice horario de saturación vial en el cuadrante (1.00 flujo libre a 3.95 colapso por inundación).",
        examples=[2.85],
    )
    flooded_roads: bool = Field(
        ...,
        description="Indica si la escorrentía superó el umbral de drenaje del cuadrante anegando calles y pasos a desnivel.",
        examples=[True],
    )
    sky_condition: str = Field(
        ...,
        description="Condición atmosférica horaria ('despejado', 'nublado', 'lluvia_ligera', 'tormenta').",
        examples=["tormenta"],
    )


class WeatherAggregatedOut(BaseModel):
    """Métrica climática e hidrológica agregada temporalmente (día, semana, mes) para cuadrante o ciudad consolidada."""

    model_config = ConfigDict(from_attributes=True)

    period_start: dt_date | datetime = Field(
        ...,
        description="Inicio del período de agregación temporal (YYYY-MM-DD o ISO 8601).",
        examples=["2024-05-18"],
    )
    period_end: dt_date | datetime | None = Field(
        None,
        description="Fin del período de agregación temporal (YYYY-MM-DD o ISO 8601).",
        examples=["2024-05-24"],
    )
    quadrant_id: int | None = Field(
        None,
        description="Identificador del cuadrante analizado (1 a 92), o null si es promedio consolidado de Managua.",
        examples=[53],
    )
    granularity: str = Field(
        ...,
        description="Nivel de granularidad aplicado ('day', 'week', 'month').",
        examples=["day"],
    )
    avg_temperature_c: float = Field(
        ...,
        description="Temperatura promedio en el período (°C).",
        examples=[27.5],
    )
    min_temperature_c: float | None = Field(
        None,
        description="Temperatura mínima registrada en el período (°C).",
        examples=[22.1],
    )
    max_temperature_c: float | None = Field(
        None,
        description="Temperatura máxima registrada en el período (°C).",
        examples=[34.2],
    )
    total_precipitation_mm: float = Field(
        ...,
        description="Precipitación acumulada total en el período (mm).",
        examples=[45.8],
    )
    max_precipitation_mm: float | None = Field(
        None,
        description="Precipitación horaria máxima en el período (mm).",
        examples=[18.5],
    )
    avg_channel_runoff_mm: float = Field(
        ...,
        description="Escorrentía promedio de cauces en el período (mm).",
        examples=[5.2],
    )
    max_channel_runoff_mm: float | None = Field(
        None,
        description="Escorrentía pico máxima registrada en el período (mm).",
        examples=[18.4],
    )
    avg_congestion_index: float = Field(
        ...,
        description="Índice promedio de congestión vial (1.00 a 3.95).",
        examples=[1.85],
    )
    flooded_hours_count: int = Field(
        0,
        description="Cantidad total de horas con cauces o vías inundadas durante el período.",
        examples=[3],
    )
    records_count: int = Field(
        ...,
        description="Total de observaciones horarias consolidadas en este intervalo.",
        examples=[24],
    )
    dominant_sky_condition: str | None = Field(
        None,
        description="Condición atmosférica más frecuente en el período (moda estadística).",
        examples=["lluvia_ligera"],
    )


class TripOut(BaseModel):
    """Cabecera transaccional esbelta (3NF) de un viaje solicitado en la plataforma MoviGo."""

    model_config = ConfigDict(from_attributes=True)

    trip_id: int = Field(
        ...,
        description="Identificador único transaccional del viaje.",
        examples=[10042],
    )
    user_id: int = Field(
        ...,
        description="Clave foránea del pasajero que solicitó el traslado.",
        examples=[501],
    )
    driver_id: int | None = Field(
        default=None,
        description="Clave foránea del socio conductor que atendió el viaje.",
        examples=[205],
    )
    origin_quadrant_id: int = Field(
        ...,
        description="Clave foránea del cuadrante cuadrado exacto de origen en la grilla de Managua (1 a 92).",
        examples=[15],
    )
    destination_quadrant_id: int = Field(
        ...,
        description="Clave foránea del cuadrante cuadrado exacto de destino en la grilla de Managua (1 a 92).",
        examples=[41],
    )
    origin_latitude: float = Field(
        ...,
        description="Latitud exacta en la vía pública del punto de recogida (WGS84).",
        examples=[12.11542],
    )
    origin_longitude: float = Field(
        ...,
        description="Longitud exacta en la vía pública del punto de recogida (WGS84).",
        examples=[-86.25481],
    )
    destination_latitude: float = Field(
        ...,
        description="Latitud exacta en la vía pública del punto de destino (WGS84).",
        examples=[12.12834],
    )
    destination_longitude: float = Field(
        ...,
        description="Longitud exacta en la vía pública del punto de destino (WGS84).",
        examples=[-86.26512],
    )
    requested_at: datetime = Field(
        ...,
        description="Marca de tiempo en que el pasajero pidió el viaje (ISO 8601).",
        examples=["2024-05-18T17:45:00"],
    )
    started_at: datetime | None = Field(
        default=None,
        description="Marca de tiempo en que el conductor abordó al pasajero.",
        examples=["2024-05-18T17:52:00"],
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Marca de tiempo de finalización del viaje en destino.",
        examples=["2024-05-18T18:22:00"],
    )
    distance_km: float = Field(
        ...,
        description="Distancia real del trayecto en kilómetros (km).",
        examples=[6.8],
    )
    duration_minutes: float = Field(
        ...,
        description="Tiempo total transcurrido del viaje en minutos.",
        examples=[30.0],
    )
    trip_status: str = Field(
        ...,
        description="Estado final del servicio ('completado', 'cancelado_usuario', 'cancelado_conductor', 'no_asignado').",
        examples=["completado"],
    )


class TripPaymentOut(BaseModel):
    """Transacción de cobro y liquidación tarifaria asociada a un viaje."""

    model_config = ConfigDict(from_attributes=True)

    payment_id: int = Field(
        ...,
        description="Identificador único numérico de la transacción de pago.",
        examples=[10042],
    )
    trip_id: int = Field(
        ...,
        description="Clave foránea del viaje facturado.",
        examples=[10042],
    )
    payment_method: str = Field(
        ...,
        description="Modalidad de pago ('efectivo', 'tarjeta', 'billetera_digital').",
        examples=["tarjeta"],
    )
    base_fare: float = Field(
        ...,
        description="Tarifa base regular antes de aplicar recargos dinámicos en Córdobas (NIO).",
        examples=[327.4],
    )
    surge_multiplier: float = Field(
        ...,
        description="Factor multiplicador por alta demanda o lluvia (surge pricing, 1.00x a 3.20x).",
        examples=[1.35],
    )
    tip_amount: float = Field(
        default=0.0,
        description="Monto voluntario de gratificación dejado al conductor en Córdobas (NIO).",
        examples=[20.0],
    )
    final_fare: float = Field(
        ...,
        description="Monto final facturado al pasajero (base_fare * surge_multiplier) en Córdobas (NIO).",
        examples=[441.99],
    )
    payment_status: str = Field(
        ...,
        description="Estado de la transacción de pago ('pagado', 'anulado').",
        examples=["pagado"],
    )


class TripRatingOut(BaseModel):
    """Calificación bilateral post-viaje para viajes completados."""

    model_config = ConfigDict(from_attributes=True)

    rating_id: int = Field(
        ...,
        description="Identificador único numérico del registro de calificación.",
        examples=[8500],
    )
    trip_id: int = Field(
        ...,
        description="Clave foránea del viaje completado.",
        examples=[10042],
    )
    user_rating: float = Field(
        ...,
        description="Puntuación otorgada por el conductor al pasajero (1.0 a 5.0).",
        examples=[5.0],
    )
    driver_rating: float = Field(
        ...,
        description="Puntuación otorgada por el pasajero al conductor (1.0 a 5.0).",
        examples=[4.9],
    )


class TripCancellationOut(BaseModel):
    """Bitácora de cancelación y estado de oferta/demanda al momento de cancelar el viaje."""

    model_config = ConfigDict(from_attributes=True)

    cancellation_id: int = Field(
        ...,
        description="Identificador único numérico del evento de cancelación.",
        examples=[1204],
    )
    trip_id: int = Field(
        ...,
        description="Clave foránea del viaje cancelado.",
        examples=[10055],
    )
    cancelled_by: str = Field(
        ...,
        description="Actor que originó la cancelación ('usuario', 'conductor').",
        examples=["usuario"],
    )
    cancellation_reason: str = Field(
        ...,
        description="Motivo registrado de la cancelación.",
        examples=["Tarifa dinámica sobrepasa presupuesto"],
    )
    wait_time_minutes: float = Field(
        ...,
        description="Tiempo de espera transcurrido desde la solicitud hasta la cancelación en minutos.",
        examples=[9.5],
    )
    origin_active_requests: int = Field(
        ...,
        description="Demanda activa instantánea (Dt) de viajes en la zona de origen.",
        examples=[42],
    )
    origin_available_drivers: int = Field(
        ...,
        description="Oferta instantánea (St) de conductores disponibles en la zona de origen.",
        examples=[18],
    )


class DriverTelemetryOut(BaseModel):
    """Ping de telemetría GPS vehicular y velocidad en tiempo real (esquema 3NF)."""

    model_config = ConfigDict(from_attributes=True)

    telemetry_id: int = Field(
        ...,
        description="Identificador único del registro de telemetría GPS.",
        examples=[99001],
    )
    driver_id: int = Field(
        ...,
        description="Clave foránea del conductor monitoreado.",
        examples=[205],
    )
    trip_id: int | None = Field(
        default=None,
        description="Clave foránea del viaje activo asociado al ping GPS (None cuando el conductor está disponible).",
        examples=[10042],
    )
    quadrant_id: int = Field(
        ...,
        description="Clave foránea del cuadrante cuadrado exacto donde se captó la señal GPS (1 a 92).",
        examples=[15],
    )
    recorded_at: datetime = Field(
        ...,
        description="Marca de tiempo precisa de emisión del ping GPS (ISO 8601).",
        examples=["2024-05-18T18:00:15"],
    )
    latitude: float = Field(
        ...,
        description="Coordenada de latitud en grados decimales WGS84 sobre la red vial.",
        examples=[12.1288],
    )
    longitude: float = Field(
        ...,
        description="Coordenada de longitud en grados decimales WGS84 sobre la red vial.",
        examples=[-86.2642],
    )
    speed_kmh: float = Field(
        ...,
        description="Velocidad instantánea registrada por el GPS en kilómetros por hora (km/h).",
        examples=[34.5],
    )
    availability_status: str = Field(
        ...,
        description="Estado del conductor en ese instante ('disponible', 'ocupado', 'en_camino_recogida', 'descanso').",
        examples=["ocupado"],
    )


class SimulationStatusOut(BaseModel):
    """Estado en tiempo real del reloj de simulación y progreso de generación."""

    model_config = ConfigDict(from_attributes=True)

    case_name: str = Field(..., description="Nombre del caso de estudio de movilidad.")
    current_status: str = Field(..., description="Estado del worker ('ready', 'catching_up', 'hourly_wait').")
    earliest_datetime: datetime | None = Field(None, description="Límite inferior histórico generado (inclusive).")
    latest_datetime: datetime | None = Field(None, description="Última hora virtual simulada y lista para consultas.")
    target_datetime: datetime | None = Field(None, description="Hora de destino actual a alcanzar (datetime.now).")
    hours_remaining_catch_up: int = Field(0, description="Horas faltantes para nivelarse con el tiempo presente.")
    total_hours_simulated: int = Field(0, description="Total acumulado de horas simuladas generadas.")
    total_trips_simulated: int = Field(0, description="Total acumulado de viajes generados en el sistema.")
    is_leader: bool = Field(False, description="Indica si esta instancia posee el bloqueo líder de generación.")

