"""MoviGo simulation generator facade (3NF OLTP schema).

Exposes the modular Agent-Based Simulation (ABS) engine components:
- DriverAgent & RiderAgent (`movigo_sim.engine.entities`)
- WorldEnvironment (`movigo_sim.engine.world`)
- MoviGoPlatform (`movigo_sim.engine.platform`)
- SimulationRecorder (`movigo_sim.engine.recorder`)
- MoviGoSimulationEngine (`movigo_sim.engine.simulator`)
"""

from movigo_sim.engine.simulator import (
    MoviGoSimulationEngine,
    load_movigo_quadrants,
    load_movigo_vehicles,
    load_movigo_seed_catalogs,
    load_managua_street_network,
)
from movigo_sim.engine.world import (
    WorldEnvironment,
    haversine_km,
    get_gravity_regime_name,
    ZONE_GRAVITY_REGIMES,
)
from movigo_sim.engine.platform import (
    MoviGoPlatform,
    HOURLY_TRIP_WEIGHTS,
    PAYMENT_METHODS,
    STRATUM_PAYMENT_PROBABILITIES,
    STRATUM_SURGE_BETA,
)
from movigo_sim.engine.entities import DriverAgent, RiderAgent, RiderPersona
from movigo_sim.engine.recorder import SimulationRecorder

__all__ = [
    "MoviGoSimulationEngine",
    "WorldEnvironment",
    "MoviGoPlatform",
    "SimulationRecorder",
    "DriverAgent",
    "RiderAgent",
    "RiderPersona",
    "haversine_km",
    "get_gravity_regime_name",
    "ZONE_GRAVITY_REGIMES",
    "HOURLY_TRIP_WEIGHTS",
    "PAYMENT_METHODS",
    "STRATUM_PAYMENT_PROBABILITIES",
    "STRATUM_SURGE_BETA",
    "load_movigo_quadrants",
    "load_movigo_vehicles",
    "load_movigo_seed_catalogs",
    "load_managua_street_network",
]
