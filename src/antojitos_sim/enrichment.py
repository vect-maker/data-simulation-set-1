"""Semantic enrichment module for Antojitos Express.

Applies authentic Nicaraguan delivery instructions, cancellation reasons,
and customer feedback conditioned on operational states (rain severity, delay, failure).
Supports offline deterministic templates as well as optional live Gemini LLM enrichment.
"""

import logging
import os
from typing import List, Dict, Any, Optional
import numpy as np

from antojitos_sim.config import GEMINI_API_KEY, GEMINI_MODEL
from antojitos_sim.models import Orden

logger = logging.getLogger(__name__)


class SemanticEnricher:
    """Enriches simulated orders with realistic qualitative customer and delivery notes."""

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

        self.notas_pool: List[str] = templates.get("notas_entrega", [])
        self.motivos_pool: List[str] = templates.get("motivos_cancelacion", [])
        self.comentarios_retraso: List[str] = templates.get("comentarios_retraso", [])
        self.comentarios_exito: List[str] = templates.get("comentarios_exitosos", [])

        self.gemini_client = None
        if self.use_llm:
            api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
            if api_key:
                try:
                    from google import genai
                    self.gemini_client = genai.Client(api_key=api_key)
                    logger.info("Initialized Gemini client for live semantic enrichment.")
                except Exception as e:
                    logger.warning(f"Could not initialize Gemini client: {e}. Falling back to templates.")
            else:
                logger.warning("No GEMINI_API_KEY provided. Falling back to offline templates.")

    def enrich_orders(self, orders: List[Orden]) -> List[Orden]:
        """Iterate through orders and enrich qualitative fields based on simulated state."""
        logger.info(f"Enriching {len(orders)} orders with semantic notes and edge cases...")

        cancellations_count = 0
        complaints_count = 0
        positive_reviews_count = 0
        notes_count = 0

        for order in orders:
            # 1. Delivery directions (notas_entrega): ~32% of all orders
            if np.random.rand() < 0.32:
                order.notas_entrega = str(np.random.choice(self.notas_pool))
                notes_count += 1

            # 2. Cancellations (motivo_cancelacion)
            if order.estado_orden == "cancelada":
                order.motivo_cancelacion = str(np.random.choice(self.motivos_pool))
                cancellations_count += 1
                # 40% of cancelled orders also include an angry customer comment
                if np.random.rand() < 0.40:
                    order.comentario_cliente = str(np.random.choice(self.comentarios_retraso))
                    complaints_count += 1
                continue

            # 3. Delivered orders feedback
            if order.estado_orden == "entregada" and order.fecha_hora_entrega and order.fecha_hora_creacion:
                duration = (order.fecha_hora_entrega - order.fecha_hora_creacion).total_seconds() / 60.0

                # Delayed orders (> 50 min duration)
                if duration > 50.0:
                    if np.random.rand() < 0.35:
                        order.comentario_cliente = str(np.random.choice(self.comentarios_retraso))
                        complaints_count += 1
                else:
                    # Normal / fast delivery: 8% leave a happy review
                    if np.random.rand() < 0.08:
                        order.comentario_cliente = str(np.random.choice(self.comentarios_exito))
                        positive_reviews_count += 1

        logger.info(
            f"Semantic enrichment complete: {notes_count} delivery notes, "
            f"{cancellations_count} cancellation reasons, "
            f"{complaints_count} delay complaints, {positive_reviews_count} positive reviews."
        )
        return orders
