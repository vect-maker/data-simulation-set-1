"""Pydantic models for MoviGo ride-hailing relational schema."""

from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class Cuadrante(BaseModel):
    """Fine-grained geographical square quadrant (~0.88 km x 0.88 km) inside an urban zone."""
    model_config = ConfigDict(from_attributes=True)

    id_cuadrante: int = Field(ge=1)
    id_zona: int = Field(ge=1)
    codigo_cuadrante: str
    nombre_cuadrante: str
    fila_grid: int = Field(ge=0)
    columna_grid: int = Field(ge=0)
    lat_min: float = Field(ge=12.00, le=12.30)
    lat_max: float = Field(ge=12.00, le=12.30)
    lon_min: float = Field(ge=-86.45, le=-86.10)
    lon_max: float = Field(ge=-86.45, le=-86.10)
    altitud_media_msnm: int = Field(ge=30, le=950)
    riesgo_inundacion: str = Field(pattern=r"^(bajo|medio|alto|critico)$")
    cauces_principales: str


class ZonaUrbana(BaseModel):
    """Urban pricing and mobility zone in Managua (groups multiple square cuadrantes)."""
    model_config = ConfigDict(from_attributes=True)

    id_zona: int = Field(ge=1)
    nombre_zona: str
    estrato_socioeconomico: str = Field(pattern=r"^(alto|medio|popular|comercial)$")
    latitud: float = Field(ge=12.00, le=12.30)
    longitud: float = Field(ge=-86.45, le=-86.10)
    radio_cobertura_km: float = Field(ge=0.5, le=10.0)
    tarifa_base_bajada_bandera: float = Field(ge=30.0, le=90.0)


class Usuario(BaseModel):
    """App passenger user."""
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int = Field(ge=1)
    nombre: str
    telefono: str
    metodo_pago_preferido: str = Field(pattern=r"^(efectivo|tarjeta|billetera_digital)$")
    calificacion_promedio: float = Field(ge=1.0, le=5.0)
    fecha_registro: date


class Conductor(BaseModel):
    """Ride-hailing driver."""
    model_config = ConfigDict(from_attributes=True)

    id_conductor: int = Field(ge=1)
    nombre: str
    tipo_servicio: str = Field(pattern=r"^(movigo_estandar|movigo_comfort|movigo_moto)$")
    modelo_vehiculo: str
    anio_vehiculo: int = Field(ge=2010, le=2024)
    placa: str
    calificacion_promedio: float = Field(ge=1.0, le=5.0)
    tasa_aceptacion_pct: float = Field(ge=50.0, le=100.0)
    estado: str = Field(pattern=r"^(activo|inactivo|en_viaje|desconectado)$")


class Viaje(BaseModel):
    """Ride transaction header."""
    model_config = ConfigDict(from_attributes=True)

    id_viaje: int = Field(ge=1)
    id_usuario: int = Field(ge=1)
    id_conductor: int | None = None
    id_zona_origen: int = Field(ge=1)
    id_zona_destino: int = Field(ge=1)
    id_cuadrante_origen: int = Field(ge=1)
    id_cuadrante_destino: int = Field(ge=1)
    latitud_origen: float = Field(ge=12.00, le=12.30)
    longitud_origen: float = Field(ge=-86.45, le=-86.10)
    latitud_destino: float = Field(ge=12.00, le=12.30)
    longitud_destino: float = Field(ge=-86.45, le=-86.10)
    fecha_hora_solicitud: datetime
    fecha_hora_inicio: datetime | None = None
    fecha_hora_fin: datetime | None = None
    tiempo_espera_minutos: float = Field(ge=0.0)
    distancia_km: float = Field(ge=0.5)
    duracion_minutos: float = Field(ge=2.0)
    tarifa_bajada_bandera: float = Field(ge=0.0)
    cargo_distancia: float = Field(ge=0.0)
    cargo_tiempo: float = Field(ge=0.0)
    tarifa_base: float = Field(ge=0.0)
    multiplicador_dinamico: float = Field(ge=1.0, le=3.5)
    tarifa_final: float = Field(ge=0.0)
    solicitudes_activas_origen: int = Field(ge=1)
    conductores_disponibles_origen: int = Field(ge=1)
    metodo_pago: str = Field(pattern=r"^(efectivo|tarjeta|billetera_digital)$")
    estado_viaje: str = Field(pattern=r"^(completado|cancelado_usuario|cancelado_conductor|no_asignado)$")
    calificacion_usuario: float | None = Field(None, ge=1.0, le=5.0)
    calificacion_conductor: float | None = Field(None, ge=1.0, le=5.0)
    propina: float = Field(ge=0.0, default=0.0)
    motivo_cancelacion: str | None = None


class TelemetriaConductor(BaseModel):
    """Driver GPS tracking ping."""
    model_config = ConfigDict(from_attributes=True)

    id_telemetria: int = Field(ge=1)
    id_conductor: int = Field(ge=1)
    id_viaje: int | None = None
    id_zona: int = Field(ge=1)
    id_cuadrante: int = Field(ge=1)
    fecha_hora: datetime
    latitud: float = Field(ge=12.00, le=12.30)
    longitud: float = Field(ge=-86.45, le=-86.10)
    velocidad_kmh: float = Field(ge=0.0, le=120.0)
    estado_disponibilidad: str = Field(pattern=r"^(disponible|ocupado|en_camino_recogida)$")


class CampanaIncentivo(BaseModel):
    """Driver bonus incentive campaign for Knapsack modeling."""
    model_config = ConfigDict(from_attributes=True)

    id_campana: int = Field(ge=1)
    nombre_bono: str
    costo_presupuesto_nio: float = Field(ge=2000.0, le=50000.0)
    incremento_horas_conexion: float = Field(ge=50.0, le=1200.0)
    tipo_incentivo: str = Field(pattern=r"^(meta_viajes|hora_pico_lluvia|zona_alta_demanda)$")
    fecha_inicio: date
    fecha_fin: date
    estado: str = Field(pattern=r"^(activa|finalizada)$")


class ClimaCuadrantes(BaseModel):
    """Hourly urban weather, cauce runoff, and traffic congestion per quadrant."""
    model_config = ConfigDict(from_attributes=True)

    id_clima: int = Field(ge=1)
    id_cuadrante: int = Field(ge=1)
    fecha_hora: datetime
    fecha: date
    hora: int = Field(ge=0, le=23)
    precipitacion_mm: float = Field(ge=0.0)
    escorrentia_cauce_mm: float = Field(ge=0.0)
    temperatura_c: float = Field(ge=15.0, le=43.0)
    indice_congestion: float = Field(ge=1.00, le=4.00)
    vias_anegadas: bool = False
    condicion_cielo: str = Field(pattern=r"^(despejado|lluvia_ligera|tormenta|nublado)$")
