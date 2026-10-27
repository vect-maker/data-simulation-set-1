"""Pydantic models for MoviGo 3NF transactional OLTP relational schema (standardized English identifiers)."""

from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class Quadrant(BaseModel):
    """Fine-grained geographical square quadrant (~0.88 km x 0.88 km) inside an urban zone."""
    model_config = ConfigDict(from_attributes=True)

    quadrant_id: int = Field(ge=1)
    zone_id: int = Field(ge=1)
    district: str = Field(default="Distrito I", pattern=r"^Distrito (I|II|III|IV|V|VI|VII)$")
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


class DrainageChannel(BaseModel):
    """Managua natural drainage canal / cauce hydrological infrastructure."""
    model_config = ConfigDict(from_attributes=True)

    channel_id: int = Field(ge=1)
    channel_name: str
    zone_id: int = Field(ge=1)
    latitude: float = Field(ge=12.00, le=12.30)
    longitude: float = Field(ge=-86.45, le=-86.10)
    critical_radius_km: float = Field(ge=0.2, le=3.0)
    vulnerability_level: str = Field(pattern=r"^(bajo|medio|alto|critico)$")
    flow_direction: str


class UrbanZone(BaseModel):
    """Urban pricing and mobility zone in Managua (groups multiple square quadrants)."""
    model_config = ConfigDict(from_attributes=True)

    zone_id: int = Field(ge=1)
    zone_name: str
    district: str = Field(default="Distrito I", pattern=r"^Distrito (I|II|III|IV|V|VI|VII)$")
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
    """Ride-hailing driver profile and operational state."""
    model_config = ConfigDict(from_attributes=True)

    driver_id: int = Field(ge=1)
    name: str
    average_rating: float = Field(ge=1.0, le=5.0)
    acceptance_rate_pct: float = Field(ge=50.0, le=100.0)
    status: str = Field(pattern=r"^(activo|inactivo|en_viaje|desconectado)$")


class Vehicle(BaseModel):
    """Vehicle registered and operated by a driver."""
    model_config = ConfigDict(from_attributes=True)

    vehicle_id: int = Field(ge=1)
    driver_id: int = Field(ge=1)
    service_type: str = Field(pattern=r"^(movigo_estandar|movigo_comfort|movigo_moto)$")
    vehicle_model: str
    vehicle_year: int = Field(ge=2010, le=2024)
    license_plate: str
    fuel_type: str = Field(default="gasolina_regular", pattern=r"^(gasolina_regular|gasolina_super|diesel)$")
    fuel_efficiency_km_l: float = Field(ge=5.0, le=45.0, default=13.5)
    initial_odometer_km: float = Field(ge=0.0, default=35000.0)


class VehicleMaintenance(BaseModel):
    """Vehicle maintenance and repair service record in 3NF."""
    model_config = ConfigDict(from_attributes=True)

    maintenance_id: int = Field(ge=1)
    vehicle_id: int = Field(ge=1)
    service_date: date
    maintenance_type: str = Field(pattern=r"^(preventivo|correctivo)$")
    odometer_km: float = Field(ge=0.0)
    description: str
    cost_nio: float = Field(ge=500.0, le=35000.0)
    downtime_hours: float = Field(ge=1.0, le=48.0)
    workshop_name: str


class Trip(BaseModel):
    """Lean 3NF ride transaction header (core lifecycle and spatial trajectory)."""
    model_config = ConfigDict(from_attributes=True)

    trip_id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    driver_id: int | None = None
    origin_quadrant_id: int = Field(ge=1)
    destination_quadrant_id: int = Field(ge=1)
    origin_latitude: float = Field(ge=12.00, le=12.30)
    origin_longitude: float = Field(ge=-86.45, le=-86.10)
    destination_latitude: float = Field(ge=12.00, le=12.30)
    destination_longitude: float = Field(ge=-86.45, le=-86.10)
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    distance_km: float = Field(ge=0.5)
    duration_minutes: float = Field(ge=2.0)
    trip_status: str = Field(pattern=r"^(completado|cancelado_usuario|cancelado_conductor|no_asignado)$")


class TripPayment(BaseModel):
    """Billing and payment authorization transaction for a trip."""
    model_config = ConfigDict(from_attributes=True)

    payment_id: int = Field(ge=1)
    trip_id: int = Field(ge=1)
    payment_method: str = Field(pattern=r"^(efectivo|tarjeta|billetera_digital)$")
    base_fare: float = Field(ge=0.0)
    surge_multiplier: float = Field(ge=1.0, le=3.5)
    tip_amount: float = Field(ge=0.0, default=0.0)
    final_fare: float = Field(ge=0.0)
    payment_status: str = Field(pattern=r"^(pagado|anulado)$")


class TripRating(BaseModel):
    """Post-trip bilateral ratings for a completed trip."""
    model_config = ConfigDict(from_attributes=True)

    rating_id: int = Field(ge=1)
    trip_id: int = Field(ge=1)
    user_rating: float = Field(ge=1.0, le=5.0)
    driver_rating: float = Field(ge=1.0, le=5.0)


class TripCancellation(BaseModel):
    """Cancellation log and dispatch market snapshot for a cancelled trip."""
    model_config = ConfigDict(from_attributes=True)

    cancellation_id: int = Field(ge=1)
    trip_id: int = Field(ge=1)
    cancelled_by: str = Field(pattern=r"^(usuario|conductor)$")
    cancellation_reason: str
    wait_time_minutes: float = Field(ge=0.0)
    origin_active_requests: int = Field(ge=1)
    origin_available_drivers: int = Field(ge=1)


class DriverTelemetry(BaseModel):
    """Driver GPS tracking ping in 3NF (zone resolved via quadrant_id -> quadrants.zone_id)."""
    model_config = ConfigDict(from_attributes=True)

    telemetry_id: int = Field(ge=1)
    driver_id: int = Field(ge=1)
    trip_id: int | None = None
    quadrant_id: int = Field(ge=1)
    recorded_at: datetime
    latitude: float = Field(ge=12.00, le=12.30)
    longitude: float = Field(ge=-86.45, le=-86.10)
    speed_kmh: float = Field(ge=0.0, le=120.0)
    availability_status: str = Field(pattern=r"^(disponible|ocupado|en_camino_recogida|descanso)$")


class IncentiveCampaign(BaseModel):
    """Driver bonus incentive campaign for Knapsack modeling and zone supply boosts."""
    model_config = ConfigDict(from_attributes=True)

    campaign_id: int = Field(ge=1)
    target_zone_id: int = Field(ge=1)
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
