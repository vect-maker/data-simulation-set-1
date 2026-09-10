"""Semantic enrichment module for Cooperativa El Volcán.

Enriches coffee lots with authentic SCAA sensory cupping notes,
processing observations, and quality edge cases.
Supports offline template banking as well as optional live Gemini LLM enrichment.
"""

import logging
import os
from typing import List, Dict, Any, Tuple
import numpy as np

from volcan_sim.config import POSTGRES_SCHEMA
from volcan_sim.models import LoteAcopio, ProcesamientoBeneficio

logger = logging.getLogger(__name__)


class VolcanSemanticEnricher:
    """Enriches simulated coffee lots with professional SCAA cupping descriptions."""

    def __init__(
        self,
        templates: Dict[str, Any],
        use_llm: bool = False,
        random_seed: int = 42,
    ):
        self.templates = templates
        self.use_llm = use_llm
        self.random_seed = random_seed
        np.random.seed(random_seed)

        self.notas_altas: List[str] = templates.get("notas_catacion_altas", [])
        self.notas_medias: List[str] = templates.get("notas_catacion_medias", [])
        self.defectos: List[str] = templates.get("defectos_proceso", [])

    def enrich_lots_and_processes(
        self,
        lotes: List[LoteAcopio],
        procesos: List[ProcesamientoBeneficio],
    ) -> Tuple[List[LoteAcopio], List[ProcesamientoBeneficio]]:
        """Populate sensory cupping descriptions and milling logs."""
        logger.info(f"Enriching {len(lotes)} coffee lots with SCAA cupping notes...")

        for lote in lotes:
            # SCAA >= 87.0: Exotic and complex notes
            if lote.puntaje_catacion_scaa >= 87.0:
                lote.notas_catacion = str(np.random.choice(self.notas_altas))
            else:
                lote.notas_catacion = str(np.random.choice(self.notas_medias))

        # Enrich any discarded or edge-case processing batches
        discarded_lote_ids = {l.id_lote for l in lotes if l.estado_lote == "descartado"}
        for proc in procesos:
            if proc.id_lote in discarded_lote_ids:
                proc.observaciones_proceso = str(np.random.choice(self.defectos))

        logger.info("Enrichment complete.")
        return lotes, procesos
