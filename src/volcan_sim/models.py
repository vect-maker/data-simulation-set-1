"""Pydantic models for Cooperativa El Volcán relational schema."""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Finca(BaseModel):
    """Coffee farm in the highlands of Nicaragua."""
    model_config = ConfigDict(from_attributes=True)

    id_finca: str = Field(pattern=r"^FNC-\d{3}$")
    nombre_finca: str
    id_productor: str = Field(pattern=r"^PRD-\d{3}$")
    nombre_productor: str
    region: str = Field(pattern=r"^(Jinotega|Matagalpa|Nueva Segovia - Dipilto|Madriz)$")
    municipio: str
    latitud: float = Field(ge=12.2, le=14.5)
    longitud: float = Field(ge=-87.5, le=-85.0)
    altitud_msnm: int = Field(ge=900, le=1800)
    area_manzanas: float = Field(ge=2.0, le=120.0)


class VariedadCafe(BaseModel):
    """Botanical coffee variety."""
    model_config = ConfigDict(from_attributes=True)

    id_variedad: str = Field(pattern=r"^VAR-\d{3}$")
    nombre_variedad: str
    especie: str = "Coffea Arabica"
    perfil_sensorial_base: str
    resistencia_roya: str = Field(pattern=r"^(alta|media|susceptible)$")
    rendimiento_promedio_qq_mz: float = Field(ge=8.0, le=45.0)


class Beneficio(BaseModel):
    """Coffee processing mill (wet or dry)."""
    model_config = ConfigDict(from_attributes=True)

    id_beneficio: str = Field(pattern=r"^BNF-\d{3}$")
    nombre_beneficio: str
    tipo_beneficio: str = Field(pattern=r"^(humedo|seco)$")
    municipio: str
    latitud: float = Field(ge=12.2, le=14.5)
    longitud: float = Field(ge=-87.5, le=-85.0)
    capacidad_quintales_dia: float = Field(ge=100.0, le=3000.0)
    costo_procesamiento_qq: float = Field(ge=15.0, le=95.0)


class CuadrillaCorte(BaseModel):
    """Harvesting team."""
    model_config = ConfigDict(from_attributes=True)

    id_cuadrilla: str = Field(pattern=r"^CUA-\d{3}$")
    nombre_cuadrilla: str
    capacidad_recolectores: int = Field(ge=5, le=40)
    rendimiento_latas_dia: float = Field(ge=20.0, le=350.0)
    costo_jornal_dia: float = Field(ge=150.0, le=350.0)
    estado: str = Field(pattern=r"^(activa|descanso|asignada)$")


class LoteAcopio(BaseModel):
    """Harvested coffee cherry lot."""
    model_config = ConfigDict(from_attributes=True)

    id_lote: str = Field(pattern=r"^LOT-2024-\d{5}$")
    id_finca: str
    id_variedad: str
    id_cuadrilla: Optional[str] = None
    fecha_corte: date
    peso_cereza_kg: float = Field(ge=50.0)
    humedad_porcentaje: float = Field(ge=40.0, le=68.0)
    puntaje_catacion_scaa: float = Field(ge=78.0, le=94.0)
    certificacion: str = Field(pattern=r"^(Convencional|Fairtrade|Orgánico|Rainforest Alliance|SHG)$")
    notas_catacion: Optional[str] = None
    costo_recoleccion_nio: float = Field(ge=0.0)
    estado_lote: str = Field(pattern=r"^(recolectado|en_beneficio_humedo|en_secado|listo_exportacion|descartado)$")


class ProcesamientoBeneficio(BaseModel):
    """Processing stage log in wet or dry mill."""
    model_config = ConfigDict(from_attributes=True)

    id_proceso: int
    id_lote: str
    id_beneficio: str
    etapa: str = Field(pattern=r"^(despulpado|fermentacion|secado_patio|trillado|clasificacion)$")
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    temperatura_fermentacion_c: Optional[float] = None
    merma_porcentaje: float = Field(ge=0.0, le=85.0)
    peso_salida_kg: float = Field(ge=0.0)
    observaciones_proceso: Optional[str] = None


class SubastaEspecial(BaseModel):
    """Specialty micro-lot for Cup of Excellence / Knapsack auction."""
    model_config = ConfigDict(from_attributes=True)

    id_subasta: str = Field(pattern=r"^SUB-\d{3}$")
    id_lote: Optional[str] = None
    nombre_lote_especial: str
    peso_quintales: float = Field(ge=5.0, le=50.0)
    costo_certificacion_usd: float = Field(ge=500.0, le=5000.0)
    retorno_esperado_usd: float = Field(ge=1500.0, le=25000.0)
    puntaje_taza: float = Field(ge=86.0, le=94.0)
    fecha_subasta: date
    estado_subasta: str = Field(pattern=r"^(programada|adjudicada|desierta)$")


class EmbarqueExportacion(BaseModel):
    """Export container shipment leaving via Puerto Corinto."""
    model_config = ConfigDict(from_attributes=True)

    id_embarque: str = Field(pattern=r"^EXP-2024-\d{4}$")
    id_lote: str
    numero_contenedor: str
    puerto_salida: str = "Puerto Corinto, Nicaragua"
    pais_destino: str = Field(pattern=r"^(Alemania|Estados Unidos|Japón|Bélgica|Taiwán|Italia)$")
    cliente_comprador: str
    fecha_embarque: date
    peso_oro_quintales: float = Field(ge=1.0)
    precio_quintal_usd: float = Field(ge=150.0, le=1200.0)
    flete_transporte_usd: float = Field(ge=10.0)
    total_usd: float = Field(ge=0.0)


class ClimaZonasCafetaleras(BaseModel):
    """Daily agro-meteorological series for Jinotega coffee region."""
    model_config = ConfigDict(from_attributes=True)

    fecha: date
    region: str = "Jinotega"
    precipitacion_mm: float = Field(ge=0.0)
    temperatura_media_c: float = Field(ge=10.0, le=35.0)
    temperatura_min_c: float = Field(ge=8.0, le=28.0)
    temperatura_max_c: float = Field(ge=15.0, le=38.0)
    humedad_relativa_pct: float = Field(ge=30.0, le=100.0)
    condicion_clima: str = Field(pattern=r"^(soleado|nublado|llovizna|temporal)$")
