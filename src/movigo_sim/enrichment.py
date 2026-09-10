"""Semantic enrichment module for MoviGo ride-hailing simulation."""

import logging
from typing import List, Dict, Any, Tuple
import numpy as np

from movigo_sim.models import Viaje

logger = logging.getLogger(__name__)


class MoviGoSemanticEnricher:
    """Enriches simulated rides with contextual ride comments and cancellation notes."""

    def __init__(
        self,
        templates: Dict[str, Any] | None = None,
        use_llm: bool = False,
        random_seed: int = 42,
    ):
        self.templates = templates or {}
        self.use_llm = use_llm
        self.random_seed = random_seed
        np.random.seed(random_seed)
        self.motivos_cancel = (
            self.templates.get("motivos_cancelacion")
            or (self.templates.get("motivos_cancelacion_conductor", []) + self.templates.get("motivos_cancelacion_usuario", []))
            or ["Tranque en rotonda Centroamérica", "Lluvia torrencial inundó la vía", "Pasajero no apareció"]
        )

    def enrich_trips(self, viajes: List[Viaje]) -> List[Viaje]:
        """Ensure all canceled trips have descriptive Managua cancellation notes."""
        logger.info(f"Enriching {len(viajes)} rides with semantic cancellation reasons...")
        for viaje in viajes:
            if "cancelado" in viaje.estado_viaje and not viaje.motivo_cancelacion:
                viaje.motivo_cancelacion = str(np.random.choice(self.motivos_cancel))
        return viajes
