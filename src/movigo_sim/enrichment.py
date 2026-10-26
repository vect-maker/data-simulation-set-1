"""Semantic enrichment module for MoviGo ride-hailing simulation (3NF OLTP schema)."""

import logging
from typing import Any
import numpy as np

from movigo_sim.config import SIMULATION_SEED
from movigo_sim.models import TripCancellation

logger = logging.getLogger(__name__)


class MoviGoSemanticEnricher:
    """Enriches simulated cancellation records with contextual Managua cancellation notes."""

    def __init__(
        self,
        templates: dict[str, Any] | None = None,
        use_llm: bool = False,
        random_seed: int = SIMULATION_SEED,
    ):
        self.templates = templates or {}
        self.use_llm = use_llm
        self.random_seed = random_seed
        self.rng = np.random.default_rng(self.random_seed)
        self.cancellation_reasons = self.templates.get("cancellation_reasons") or [
            "Tarifa dinámica sobrepasa presupuesto",
            "Tiempo de llegada excesivo",
            "Vía anegada / cauce intransitable",
            "Conductor no avanza",
            "Falla mecánica / imprevisto del conductor",
        ]

    def enrich_cancellations(self, cancellations: list[TripCancellation]) -> list[TripCancellation]:
        """Ensure all cancellation logs have descriptive Managua cancellation notes."""
        self.rng = np.random.default_rng(self.random_seed)
        logger.info(f"Enriching {len(cancellations)} cancellation logs with semantic cancellation reasons...")
        for canc in cancellations:
            if not canc.cancellation_reason:
                idx = int(self.rng.integers(0, len(self.cancellation_reasons)))
                canc.cancellation_reason = str(self.cancellation_reasons[idx])
        return cancellations
