"""Pydantic schemas and response models for all cases."""

from datetime import date, datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard REST pagination envelope."""
    items: List[T] = Field(..., description="List of items for the current page")
    count: int = Field(..., description="Number of items in the current page")
    total: int = Field(..., description="Total number of items matching filters")
    offset: int = Field(..., description="Current pagination offset")
    limit: int = Field(..., description="Current pagination limit")


# =========================================================
# Caso 1: Antojitos Express
# =========================================================

class ZonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_zona: str
    nombre_zona: str
    latitud: float
    longitud: float
    distancia_km: float
    tiempo_base_minutos: int
    tarifa_envio_base: float


class RepartidorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_repartidor: str
    nombre: str
    tipo_vehiculo: str
    calificacion_promedio: float
    capacidad_maxima_ordenes: int
    estado: str


class CategoriaPlatilloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_categoria: str
    nombre_categoria: str
    margen_contribucion_pct: float


class PlatilloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_platillo: str
    id_categoria: str
    nombre_platillo: str
    precio_unitario: float
    costo_ingredientes: float
    tiempo_preparacion_minutos: float
    requiere_horno: bool
    activo: bool


class PromocionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_promocion: str
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
    id_detalle: str
    id_orden: str
    id_platillo: str
    cantidad: int
    precio_unitario: float
    subtotal: float


class OrdenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_orden: str
    id_zona: str
    id_repartidor: Optional[str] = None
    id_promocion: Optional[str] = None
    fecha_hora_creacion: datetime
    fecha_hora_entrega: Optional[datetime] = None
    metodo_pago: str
    estado_orden: str
    total_orden: float
    costo_envio: float
    propina: float
    notas_entrega: Optional[str] = None
    comentario_cliente: Optional[str] = None
    motivo_cancelacion: Optional[str] = None


class OrdenDetailOut(OrdenOut):
    items: List[DetalleOrdenOut] = Field(default_factory=list, description="Associated order items")


# =========================================================
# Caso 2: Cooperativa El Volcán
# =========================================================

class FincaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_finca: str
    nombre_finca: str
    id_productor: str
    nombre_productor: str
    region: str
    municipio: str
    latitud: float
    longitud: float
    altitud_msnm: int
    area_manzanas: float


class VariedadCafeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_variedad: str
    nombre_variedad: str
    especie: str
    perfil_sensorial_base: str
    resistencia_roya: str
    rendimiento_promedio_qq_mz: float


class BeneficioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_beneficio: str
    nombre_beneficio: str
    tipo_beneficio: str
    municipio: str
    latitud: float
    longitud: float
    capacidad_quintales_dia: float
    costo_procesamiento_qq: float


class CuadrillaCorteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_cuadrilla: str
    nombre_cuadrilla: str
    capacidad_recolectores: int
    rendimiento_latas_dia: float
    costo_jornal_dia: float
    estado: str


class ClimaCafetaleroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fecha: date
    precipitacion_mm: float
    temperatura_media_c: float
    temperatura_min_c: float
    temperatura_max_c: float
    condicion_cielo: str


class LoteAcopioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_lote: str
    id_finca: str
    id_variedad: str
    fecha_corte: date
    peso_cereza_kg: float
    peso_bruto_quintales: float
    humedad_porcentaje: float
    puntaje_catacion_scaa: float
    precio_liquidado_qq_usd: float
    estado_lote: str
    notas_catacion: Optional[str] = None


class ProcesamientoBeneficioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_proceso: str
    id_lote: str
    id_beneficio: str
    tipo_etapa: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    peso_entrada_qq: float
    peso_salida_qq: Optional[float] = None
    merma_porcentaje: Optional[float] = None
    estado_proceso: str


class SubastaEspecialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_subasta: str
    nombre_evento: str
    peso_quintales: float
    puntaje_catacion_minimo: float
    costo_certificacion_usd: float
    retorno_esperado_usd: float
    fecha_evento: date


class EmbarqueExportacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_embarque: str
    id_lote: str
    numero_contenedor: str
    pais_destino: str
    puerto_destino: str
    fecha_embarque: date
    peso_oro_quintales: float
    precio_quintal_usd: float
    total_usd: float


# =========================================================
# Caso 3: MoviGo
# =========================================================

class ZonaUrbanaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_zona: str
    nombre_zona: str
    estrato_socioeconomico: str
    latitud: float
    longitud: float
    radio_cobertura_km: float
    tarifa_base_bajada_bandera: float


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_usuario: str
    nombre: str
    telefono: str
    metodo_pago_preferido: str
    calificacion_promedio: float
    fecha_registro: date


class ConductorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_conductor: str
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
    id_campana: str
    nombre_bono: str
    costo_presupuesto_nio: float
    incremento_horas_conexion: float
    tipo_incentivo: str
    fecha_inicio: date
    fecha_fin: date


class ClimaCuadranteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_registro: int
    fecha: date
    id_zona: str
    precipitacion_mm: float
    temperatura_c: float
    indice_congestion: float
    condicion_cielo: str


class ViajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_viaje: str
    id_usuario: str
    id_conductor: Optional[str] = None
    id_zona_origen: str
    id_zona_destino: str
    fecha_hora_solicitud: datetime
    fecha_hora_inicio: Optional[datetime] = None
    fecha_hora_fin: Optional[datetime] = None
    distancia_km: float
    duracion_minutos: float
    multiplicador_dinamico: float
    tarifa_final: float
    metodo_pago: str
    estado_viaje: str
    motivo_cancelacion: Optional[str] = None


class TelemetriaConductorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_telemetria: int
    id_conductor: str
    id_viaje: Optional[str] = None
    fecha_hora: datetime
    latitud: float
    longitud: float
    velocidad_kmh: float
    bateria_telefono_pct: int
