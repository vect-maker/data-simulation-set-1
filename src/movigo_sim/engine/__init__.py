"""MoviGo Agent-Based Simulation (ABS) Engine.

Components:
- entities: DriverAgent, RiderAgent
- world: WorldEnvironment (OSM graph, CSR matrices, traffic & flood physics)
- platform: MoviGoPlatform (dispatch matcher, surge pricing, payment clearing)
- recorder: SimulationRecorder (3NF OLTP relational event sink)
- simulator: MoviGoSimulationEngine (chronological coordinator)
"""

from movigo_sim.engine.entities import DriverAgent, RiderAgent, RiderPersona
from movigo_sim.engine.world import WorldEnvironment, haversine_km, get_gravity_regime_name
from movigo_sim.engine.platform import MoviGoPlatform
from movigo_sim.engine.recorder import SimulationRecorder
from movigo_sim.engine.simulator import (
    MoviGoSimulationEngine,
    load_movigo_quadrants,
    load_movigo_vehicles,
    load_movigo_seed_catalogs,
    load_managua_street_network,
)

__all__ = [
    "DriverAgent",
    "RiderAgent",
    "WorldEnvironment",
    "MoviGoPlatform",
    "SimulationRecorder",
    "MoviGoSimulationEngine",
    "haversine_km",
    "get_gravity_regime_name",
    "load_movigo_quadrants",
    "load_movigo_vehicles",
    "load_movigo_seed_catalogs",
    "load_managua_street_network",
]
