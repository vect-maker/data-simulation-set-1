"""Pydantic schemas and response models for all cases."""

from datetime import date, datetime
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard REST pagination envelope."""
    items: list[T] = Field(..., description="List of items for the current page")
    count: int = Field(..., description="Number of items in the current page")
    total: int = Field(..., description="Total number of items matching filters")
    offset: int = Field(..., description="Current pagination offset")
    limit: int = Field(..., description="Current pagination limit")


# =========================================================
# Caso 1: Antojitos Express
# =========================================================

class ZonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_zona: int
    nombre_zona: str
    latitud: float
    longitud: float
    distancia_km: float
    tiempo_base_minutos: int
    tarifa_envio_base: float


class RepartidorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_repartidor: int
    nombre: str
    tipo_vehiculo: str
    calificacion_promedio: float
    capacidad_maxima_ordenes: int
    estado: str


class CategoriaPlatilloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_categoria: int
    nombre_categoria: str
    margen_contribucion_pct: float


class PlatilloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_platillo: int
    id_categoria: int
    nombre_platillo: str
    precio_unitario: float
    costo_ingredientes: float
    tiempo_preparacion_minutos: float
    requiere_horno: bool
    activo: bool


class PromocionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_promocion: int
    nombre_campana: str
    costo_campana: float
    retorno_esperado: float
    descuento_pct: float
    fecha_inicio: date
    fecha_fin: date


class ClimaDiarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha: date
    precipitacion_mm: float
    temperatura_c: float
    condicion_cielo: str


class DetalleOrdenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_detalle: int
    id_orden: int
    id_platillo: int
    cantidad: int
    precio_unitario: float
    subtotal: float


class OrdenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_orden: int
    id_zona: int
    id_repartidor: int | None = None
    id_promocion: int | None = None
    fecha_hora_creacion: datetime
    fecha_hora_entrega: datetime | None = None
    metodo_pago: str
    estado_orden: str
    total_orden: float
    costo_envio: float
    propina: float
    notas_entrega: str | None = None
    comentario_cliente: str | None = None
    motivo_cancelacion: str | None = None


class OrdenDetailOut(OrdenOut):
    items: list[DetalleOrdenOut] = Field(default_factory=list, description="Associated order items")


# =========================================================
# Caso 2: Cooperativa El Volcán
# =========================================================

class FincaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_finca: int
    nombre_finca: str
    id_productor: int
    nombre_productor: str
    region: str
    municipio: str
    latitud: float
    longitud: float
    altitud_msnm: int
    area_manzanas: float


class VariedadCafeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_variedad: int
    nombre_variedad: str
    especie: str
    perfil_sensorial_base: str
    resistencia_roya: str
    rendimiento_promedio_qq_mz: float


class BeneficioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_beneficio: int
    nombre_beneficio: str
    tipo_beneficio: str
    municipio: str
    latitud: float
    longitud: float
    capacidad_quintales_dia: float
    costo_procesamiento_qq: float


class CuadrillaCorteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_cuadrilla: int
    nombre_cuadrilla: str
    capacidad_recolectores: int
    rendimiento_latas_dia: float
    costo_jornal_dia: float
    estado: str


class ClimaCafetaleroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha: date
    region: str
    precipitacion_mm: float
    temperatura_media_c: float
    temperatura_min_c: float
    temperatura_max_c: float
    humedad_relativa_pct: float
    condicion_clima: str


class LoteAcopioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_lote: int
    id_finca: int
    id_variedad: int
    id_cuadrilla: int | None = None
    fecha_corte: date
    peso_cereza_kg: float
    humedad_porcentaje: float
    puntaje_catacion_scaa: float
    certificacion: str
    notas_catacion: str | None = None
    costo_recoleccion_nio: float
    estado_lote: str


class ProcesamientoBeneficioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_proceso: int
    id_lote: int
    id_beneficio: int
    etapa: str
    fecha_inicio: datetime
    fecha_fin: datetime | None = None
    temperatura_fermentacion_c: float | None = None
    merma_porcentaje: float
    peso_salida_kg: float
    observaciones_proceso: str | None = None


class SubastaEspecialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_subasta: int
    id_lote: int | None = None
    nombre_lote_especial: str
    peso_quintales: float
    costo_certificacion_usd: float
    retorno_esperado_usd: float
    puntaje_taza: float
    fecha_subasta: date
    estado_subasta: str


class EmbarqueExportacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_embarque: int
    id_lote: int
    numero_contenedor: str
    puerto_salida: str
    pais_destino: str
    cliente_comprador: str
    fecha_embarque: date
    peso_oro_quintales: float
    precio_quintal_usd: float
    flete_transporte_usd: float
    total_usd: float


# =========================================================
# Caso 3: MoviGo
# =========================================================

class ZonaUrbanaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_zona: int
    nombre_zona: str
    estrato_socioeconomico: str
    latitud: float
    longitud: float
    radio_cobertura_km: float
    tarifa_base_bajada_bandera: float


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_usuario: int
    nombre: str
    telefono: str
    metodo_pago_preferido: str
    calificacion_promedio: float
    fecha_registro: date


class ConductorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_conductor: int
    nombre: str
    tipo_servicio: str
    modelo_vehiculo: str
    anio_vehiculo: int
    placa: str
    calificacion_promedio: float
    tasa_aceptacion_pct: float
    estado: str


class CampanaIncentivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_campana: int
    nombre_bono: str
    costo_presupuesto_nio: float
    incremento_horas_conexion: float
    tipo_incentivo: str
    fecha_inicio: date
    fecha_fin: date
    estado: str


class ClimaCuadranteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha: date
    precipitacion_mm: float
    temperatura_c: float
    indice_congestion: float
    condicion_cielo: str


class ViajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_viaje: int
    id_usuario: int
    id_conductor: int | None = None
    id_zona_origen: int
    id_zona_destino: int
    fecha_hora_solicitud: datetime
    fecha_hora_inicio: datetime | None = None
    fecha_hora_fin: datetime | None = None
    distancia_km: float
    duracion_minutos: float
    tarifa_base: float
    multiplicador_dinamico: float
    tarifa_final: float
    metodo_pago: str
    estado_viaje: str
    calificacion_usuario: float | None = None
    calificacion_conductor: float | None = None
    propina: float
    motivo_cancelacion: str | None = None


class TelemetriaConductorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_telemetria: int
    id_conductor: int
    id_zona: int
    fecha_hora: datetime
    latitud: float
    longitud: float
    velocidad_kmh: float
    estado_disponibilidad: str
