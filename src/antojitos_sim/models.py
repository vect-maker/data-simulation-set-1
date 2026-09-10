"""Pydantic models for Antojitos Express relational schema and simulation entities."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class Zona(BaseModel):
    """Delivery zone in Managua."""
    model_config = ConfigDict(from_attributes=True)

    id_zona: str = Field(pattern=r"^ZON-\d{2}$")
    nombre_zona: str
    latitud: float = Field(ge=12.00, le=12.30)
    longitud: float = Field(ge=-86.45, le=-86.10)
    distancia_km: float = Field(ge=0.5, le=25.0)
    tiempo_base_minutos: int = Field(ge=5, le=60)
    tarifa_envio_base: float = Field(ge=30.0, le=180.0)


class Repartidor(BaseModel):
    """Delivery driver."""
    model_config = ConfigDict(from_attributes=True)

    id_repartidor: str = Field(pattern=r"^REP-\d{3}$")
    nombre: str
    tipo_vehiculo: str = Field(pattern=r"^(moto|bicicleta|auto)$")
    calificacion_promedio: float = Field(ge=1.0, le=5.0)
    capacidad_maxima_ordenes: int = Field(ge=1, le=8)
    estado: str = Field(pattern=r"^(activo|inactivo|descanso)$")


class CategoriaPlatillo(BaseModel):
    """Dish category."""
    model_config = ConfigDict(from_attributes=True)

    id_categoria: str = Field(pattern=r"^CAT-(FRT|QSL|HAM|BEB|POS)$")
    nombre_categoria: str
    margen_contribucion_pct: float = Field(ge=0.10, le=0.85)


class Platillo(BaseModel):
    """Menu dish with kitchen constraints."""
    model_config = ConfigDict(from_attributes=True)

    id_platillo: str = Field(pattern=r"^PLT-\d{3}$")
    id_categoria: str = Field(pattern=r"^CAT-(FRT|QSL|HAM|BEB|POS)$")
    nombre_platillo: str
    precio_unitario: float = Field(ge=50.0, le=500.0)
    costo_ingredientes: float = Field(ge=15.0, le=250.0)
    tiempo_preparacion_minutos: float = Field(ge=1.0, le=45.0)
    requiere_horno: bool = False
    activo: bool = True


class Promocion(BaseModel):
    """Promotional campaign for Knapsack modeling."""
    model_config = ConfigDict(from_attributes=True)

    id_promocion: str = Field(pattern=r"^PRM-\d{3}$")
    nombre_campana: str
    costo_campana: float = Field(ge=1000.0, le=20000.0)
    retorno_esperado: float = Field(ge=2000.0, le=60000.0)
    descuento_pct: float = Field(ge=0.05, le=0.40)
    fecha_inicio: date
    fecha_fin: date


class ClimaDiario(BaseModel):
    """Daily weather series in Managua (Driver variable)."""
    model_config = ConfigDict(from_attributes=True)

    fecha: date
    precipitacion_mm: float = Field(ge=0.0)
    temperatura_c: float = Field(ge=15.0, le=42.0)
    condicion_cielo: str = Field(pattern=r"^(despejado|lluvia_ligera|tormenta|nublado)$")


class Orden(BaseModel):
    """Order transaction header."""
    model_config = ConfigDict(from_attributes=True)

    id_orden: str = Field(pattern=r"^ORD-2024-\d{6}$")
    id_zona: str
    id_repartidor: Optional[str] = None
    id_promocion: Optional[str] = None
    fecha_hora_creacion: datetime
    fecha_hora_entrega: Optional[datetime] = None
    metodo_pago: str = Field(pattern=r"^(efectivo|tarjeta|billetera_digital)$")
    estado_orden: str = Field(pattern=r"^(entregada|cancelada|en_camino|preparando)$")
    total_orden: float = Field(ge=0.0)
    costo_envio: float = Field(ge=0.0)
    propina: float = Field(ge=0.0, default=0.0)
    notas_entrega: Optional[str] = None
    comentario_cliente: Optional[str] = None
    motivo_cancelacion: Optional[str] = None


class DetalleOrden(BaseModel):
    """Order line item detail."""
    model_config = ConfigDict(from_attributes=True)

    id_detalle: int
    id_orden: str
    id_platillo: str
    cantidad: int = Field(ge=1)
    precio_unitario: float = Field(ge=0.0)
    subtotal: float = Field(ge=0.0)


# Models for Gemini Structured Outputs
class BatchIncidentFeedback(BaseModel):
    """Schema for Gemini batch generation of semantic order feedback."""
    motivo_cancelacion: Optional[str] = Field(None, description="Detailed Nicaraguan cancellation reason if order failed")
    comentario_cliente: Optional[str] = Field(None, description="Customer review or complaint reflecting delivery delay or food temperature")
    notas_entrega: Optional[str] = Field(None, description="Nicaraguan style delivery reference directions (e.g. del semáforo 2c al lago)")
