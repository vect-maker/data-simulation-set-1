"""Semantic enrichment module for MoviGo ride-hailing simulation."""

import logging
from typing import Any
import numpy as np

from movigo_sim.models import Viaje

logger = logging.getLogger(__name__)


class MoviGoSemanticEnricher:
    """Enriches simulated rides with contextual ride comments and cancellation notes."""

    def __init__(
        self,
        templates: dict[str, Any] | None = None,
        use_llm: bool = False,
        random_seed: int = 42,
    ):
        self.templates = templates or {}
        self.use_llm = use_llm
        self.random_seed = random_seed
        np.random.seed(random_seed)
        self.motivos_cancel = (
            self.templates.get("motivos_cancelacion")
            or [
                "Tarifa dinámica sobrepasa presupuesto",
                "Tiempo de llegada excesivo",
                "Vía anegada / cauce intransitable",
                "Conductor no avanza",
                "Falla mecánica / imprevisto del conductor",
            ]
        )

    def enrich_trips(self, viajes: list[Viaje]) -> list[Viaje]:
        """Ensure all canceled trips have descriptive Managua cancellation notes."""
        logger.info(f"Enriching {len(viajes)} rides with semantic cancellation reasons...")
        for viaje in viajes:
            if "cancelado" in viaje.estado_viaje and not viaje.motivo_cancelacion:
                viaje.motivo_cancelacion = str(np.random.choice(self.motivos_cancel))
        return viajes
