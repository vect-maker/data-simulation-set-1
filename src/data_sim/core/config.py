"""Global shared configuration for the Data Simulation suite."""

import os
from dotenv import load_dotenv

load_dotenv()

# Hierarchical global simulation seed:
# 1. GLOBAL_SIMULATION_SEED
# 2. SIMULATION_SEED
# 3. Fallback default 42
GLOBAL_SIMULATION_SEED: int = int(
    os.getenv("GLOBAL_SIMULATION_SEED", os.getenv("SIMULATION_SEED", "42"))
)
