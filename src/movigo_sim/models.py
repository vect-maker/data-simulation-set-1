"""Pydantic models for MoviGo ride-hailing relational schema (standardized English identifiers)."""

from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class Quadrant(BaseModel):
    """Fine-grained geographical square quadrant (~0.88 km x 0.88 km) inside an urban zone."""
    model_config = ConfigDict(from_attributes=True)

    quadrant_id: int = Field(ge=1)
    zone_id: int = Field(ge=1)
    quadrant_code: str
    quadrant_name: str
    grid_row: int = Field(ge=0)
    grid_col: int = Field(ge=0)
    lat_min: float = Field(ge=12.00, le=12.30)
    lat_max: float = Field(ge=12.00, le=12.30)
    lon_min: float = Field(ge=-86.45, le=-86.10)
    lon_max: float = Field(ge=-86.45, le=-86.10)
    mean_altitude_masl: int = Field(ge=30, le=950)
    flood_risk: str = Field(pattern=r"^(bajo|medio|alto|critico)$")
    main_drainage_channels: str


class UrbanZone(BaseModel):
    """Urban pricing and mobility zone in Managua (groups multiple square quadrants)."""
    model_config = ConfigDict(from_attributes=True)

    zone_id: int = Field(ge=1)
    zone_name: str
    socioeconomic_stratum: str = Field(pattern=r"^(alto|medio|popular|comercial)$")
    latitude: float = Field(ge=12.00, le=12.30)
    longitude: float = Field(ge=-86.45, le=-86.10)
    coverage_radius_km: float = Field(ge=0.5, le=10.0)
    base_flag_drop_fare: float = Field(ge=30.0, le=90.0)


class User(BaseModel):
    """App passenger user."""
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(ge=1)
    name: str
    phone: str
    preferred_payment_method: str = Field(pattern=r"^(efectivo|tarjeta|billetera_digital)$")
    average_rating: float = Field(ge=1.0, le=5.0)
    registration_date: date


class Driver(BaseModel):
    """Ride-hailing driver."""
    model_config = ConfigDict(from_attributes=True)

    driver_id: int = Field(ge=1)
    name: str
    service_type: str = Field(pattern=r"^(movigo_estandar|movigo_comfort|movigo_moto)$")
    vehicle_model: str
    vehicle_year: int = Field(ge=2010, le=2024)
    license_plate: str
    average_rating: float = Field(ge=1.0, le=5.0)
    acceptance_rate_pct: float = Field(ge=50.0, le=100.0)
    status: str = Field(pattern=r"^(activo|inactivo|en_viaje|desconectado)$")


class Trip(BaseModel):
    """Ride transaction header."""
    model_config = ConfigDict(from_attributes=True)

    trip_id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    driver_id: int | None = None
    origin_zone_id: int = Field(ge=1)
    destination_zone_id: int = Field(ge=1)
    origin_quadrant_id: int = Field(ge=1)
    destination_quadrant_id: int = Field(ge=1)
    origin_latitude: float = Field(ge=12.00, le=12.30)
    origin_longitude: float = Field(ge=-86.45, le=-86.10)
    destination_latitude: float = Field(ge=12.00, le=12.30)
    destination_longitude: float = Field(ge=-86.45, le=-86.10)
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    wait_time_minutes: float = Field(ge=0.0)
    distance_km: float = Field(ge=0.5)
    duration_minutes: float = Field(ge=2.0)
    flag_drop_fare: float = Field(ge=0.0)
    distance_charge: float = Field(ge=0.0)
    time_charge: float = Field(ge=0.0)
    base_fare: float = Field(ge=0.0)
    surge_multiplier: float = Field(ge=1.0, le=3.5)
    final_fare: float = Field(ge=0.0)
    origin_active_requests: int = Field(ge=1)
    origin_available_drivers: int = Field(ge=1)
    payment_method: str = Field(pattern=r"^(efectivo|tarjeta|billetera_digital)$")
    trip_status: str = Field(pattern=r"^(completado|cancelado_usuario|cancelado_conductor|no_asignado)$")
    user_rating: float | None = Field(None, ge=1.0, le=5.0)
    driver_rating: float | None = Field(None, ge=1.0, le=5.0)
    tip_amount: float = Field(ge=0.0, default=0.0)
    cancellation_reason: str | None = None


class DriverTelemetry(BaseModel):
    """Driver GPS tracking ping."""
    model_config = ConfigDict(from_attributes=True)

    telemetry_id: int = Field(ge=1)
    driver_id: int = Field(ge=1)
    trip_id: int | None = None
    zone_id: int = Field(ge=1)
    quadrant_id: int = Field(ge=1)
    recorded_at: datetime
    latitude: float = Field(ge=12.00, le=12.30)
    longitude: float = Field(ge=-86.45, le=-86.10)
    speed_kmh: float = Field(ge=0.0, le=120.0)
    availability_status: str = Field(pattern=r"^(disponible|ocupado|en_camino_recogida)$")


class IncentiveCampaign(BaseModel):
    """Driver bonus incentive campaign for Knapsack modeling."""
    model_config = ConfigDict(from_attributes=True)

    campaign_id: int = Field(ge=1)
    bonus_name: str
    budget_cost_nio: float = Field(ge=2000.0, le=50000.0)
    online_hours_increase: float = Field(ge=50.0, le=1200.0)
    incentive_type: str = Field(pattern=r"^(meta_viajes|hora_pico_lluvia|zona_alta_demanda)$")
    start_date: date
    end_date: date
    status: str = Field(pattern=r"^(activa|finalizada)$")


class QuadrantWeather(BaseModel):
    """Hourly urban weather, cauce runoff, and traffic congestion per quadrant."""
    model_config = ConfigDict(from_attributes=True)

    weather_id: int = Field(ge=1)
    quadrant_id: int = Field(ge=1)
    recorded_at: datetime
    date: date
    hour: int = Field(ge=0, le=23)
    precipitation_mm: float = Field(ge=0.0)
    channel_runoff_mm: float = Field(ge=0.0)
    temperature_c: float = Field(ge=15.0, le=43.0)
    congestion_index: float = Field(ge=1.00, le=4.00)
    flooded_roads: bool = False
    sky_condition: str = Field(pattern=r"^(despejado|lluvia_ligera|tormenta|nublado)$")

