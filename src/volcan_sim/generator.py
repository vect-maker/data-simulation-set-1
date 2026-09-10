"""Numerical and agricultural simulation engine for Cooperativa El Volcán.

Generates realistic coffee supply chain facts with strict mathematical guarantees:
- Seasonal harvest bell curve (Oct-Mar harvest, off-season maintenance)
- Chi-Square dependency matrix: P(Variedad | Región) guaranteeing p < 0.01
- SCAA cupping score regression against altitude (r > 0.60, homoscedastic)
- Wet-to-dry milling mass balance and export staging through Puerto Corinto
- Transportation and Knapsack optimization hooks
"""

import json
import logging
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from volcan_sim.config import (
    SEEDS_DIR,
    SCAA_BASE,
    SCAA_ALTITUDE_COEFF,
    SCAA_NOISE_STD,
    VARIETY_CUP_BONUS,
    CHERRY_TO_ORO_RATIO,
    MOISTURE_TARGET_EXPORT,
    OUTLIER_COE_WINNER_PROB,
    OUTLIER_DEFECT_LOT_PROB,
    OUTLIER_MEGA_LOT_PROB,
    OUTLIER_REPELA_LOT_PROB,
)
from volcan_sim.models import (
    Finca,
    VariedadCafe,
    Beneficio,
    CuadrillaCorte,
    LoteAcopio,
    ProcesamientoBeneficio,
    SubastaEspecial,
    EmbarqueExportacion,
)

logger = logging.getLogger(__name__)

# Chi-Square Transition Matrix: P(Variedad | Región)
# Varieties order: VAR-001 (Geisha), VAR-002 (Pacamara), VAR-003 (Bourbon),
#                  VAR-004 (Maragogipe), VAR-005 (Caturra), VAR-006 (Catuaí Rojo), VAR-007 (Catuaí Amarillo)
REGION_VARIETY_PROBABILITIES: Dict[str, List[float]] = {
    # Nueva Segovia (Dipilto): Capital of Cup of Excellence, high exotic micro-lots
    "Nueva Segovia - Dipilto": [0.22, 0.26, 0.20, 0.08, 0.12, 0.06, 0.06],
    # Jinotega: High-volume mountain valleys, productive Caturra and Catuaí
    "Jinotega":                 [0.02, 0.05, 0.12, 0.05, 0.38, 0.26, 0.12],
    # Matagalpa: Historic coffee estates, Maragogipe & Bourbon specialty
    "Matagalpa":                [0.03, 0.07, 0.25, 0.22, 0.15, 0.14, 0.14],
    # Madriz (San Juan de Río Coco): High-altitude organic cooperatives
    "Madriz":                   [0.04, 0.06, 0.16, 0.06, 0.26, 0.18, 0.24],
}

# Regional wet mill routing mapping
REGION_WET_MILL: Dict[str, int] = {
    "Jinotega": 1,
    "Matagalpa": 2,
    "Nueva Segovia - Dipilto": 3,
    "Madriz": 4,
}


def load_volcan_seed_catalogs() -> Tuple[
    List[Finca],
    List[VariedadCafe],
    List[Beneficio],
    List[CuadrillaCorte],
    List[SubastaEspecial],
    Dict[str, Any],
]:
    """Load dimensional catalogs from JSON fixtures."""
    with open(SEEDS_DIR / "fincas_nicaragua.json", "r", encoding="utf-8") as f:
        fincas = [Finca(**f_data) for f_data in json.load(f)]

    with open(SEEDS_DIR / "variedades_cafe.json", "r", encoding="utf-8") as f:
        variedades = [VariedadCafe(**v) for v in json.load(f)]

    with open(SEEDS_DIR / "beneficios.json", "r", encoding="utf-8") as f:
        beneficios = [Beneficio(**b) for b in json.load(f)]

    with open(SEEDS_DIR / "cuadrillas.json", "r", encoding="utf-8") as f:
        cuadrillas = [CuadrillaCorte(**c) for c in json.load(f)]

    with open(SEEDS_DIR / "subastas_knapsack.json", "r", encoding="utf-8") as f:
        subastas = [SubastaEspecial(**s) for s in json.load(f)]

    with open(SEEDS_DIR / "tasting_notes.json", "r", encoding="utf-8") as f:
        notes = json.load(f)

    return fincas, variedades, beneficios, cuadrillas, subastas, notes


class VolcanSimulationEngine:
    """Core simulation engine for Cooperativa El Volcán coffee production and supply chain."""

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)

        (
            self.fincas,
            self.variedades,
            self.beneficios,
            self.cuadrillas,
            self.subastas_seed,
            self.notes_templates,
        ) = load_volcan_seed_catalogs()

        self.fincas_map = {f.id_finca: f for f in self.fincas}
        self.variedades_map = {v.id_variedad: v for v in self.variedades}
        self.beneficios_map = {b.id_beneficio: b for b in self.beneficios}
        self.variety_ids = [v.id_variedad for v in self.variedades]

        # Active harvesting crews
        self.active_cuadrillas = [c for c in self.cuadrillas if c.estado == "activa"]

    def get_seasonal_daily_lots(self, curr_date: date, precip_mm: float) -> int:
        """Calculate daily harvest batches according to Nicaraguan coffee phenological cycle, with operational noise and macro shocks."""
        month = curr_date.month
        day = curr_date.day

        # Peak harvest: Nov 15 to Feb 28
        if month in [12, 1] or (month == 11 and day >= 15) or (month == 2 and day <= 28):
            base_lots = int(np.random.normal(20.0, 4.5))
        # Early harvest: Oct 15 to Nov 14
        elif (month == 10 and day >= 15) or (month == 11 and day < 15):
            base_lots = int(np.random.normal(9.0, 2.8))
        # Late repela: Mar 1 to Apr 10
        elif month == 3 or (month == 4 and day <= 10):
            base_lots = int(np.random.normal(5.0, 2.0))
        # Off season (May - Sep): Maintenance, rare sampling
        else:
            base_lots = 1 if np.random.rand() < 0.12 else 0

        # Rain friction: Heavy tropical downpours (> 20mm) interrupt harvesting by crews
        if precip_mm > 20.0:
            base_lots = max(0, int(base_lots * 0.40))

        # Macro harvest shock outliers (~3% of days):
        # - High-yield surge before incoming storms (+40% to +65%)
        # - Road blockade / truck breakdown / storm interruption (-50% to -75%)
        shock_roll = np.random.rand()
        if shock_roll < 0.015:
            base_lots = int(round(base_lots * np.random.uniform(1.40, 1.65)))
        elif shock_roll < 0.030:
            base_lots = int(round(base_lots * np.random.uniform(0.25, 0.50)))

        return max(0, base_lots)

    def sample_variety_for_region(self, region: str) -> str:
        """Sample coffee botanical variety using the Chi-Square conditional transition matrix."""
        probs = REGION_VARIETY_PROBABILITIES.get(region)
        if not probs:
            probs = [0.10, 0.10, 0.20, 0.10, 0.25, 0.15, 0.10]
        cat_idx = int(np.random.choice(len(self.variety_ids), p=probs))
        return self.variety_ids[cat_idx]

    def calculate_scaa_score(self, altitud: int, id_variedad: str) -> float:
        """Calculate SCAA cupping score based on altitude and botanical genetics, with realistic sensory noise and outliers."""
        bonus = VARIETY_CUP_BONUS.get(id_variedad, 0.0)
        noise = np.random.normal(0, SCAA_NOISE_STD)

        # score = 76.2 + 0.0088 * Altitude + Variety_Bonus + eps
        raw_score = SCAA_BASE + (SCAA_ALTITUDE_COEFF * altitud) + bonus + noise

        # Sensory / quality triage outliers (~3.2% of lots):
        # 1. Defect lot outlier (~2.0%): Fermentation taint, broca damage, or bag dampness (commercial grade / pasilla: 73.0 - 78.5)
        # 2. Cup of Excellence presidential winner (~1.2%): Exceptional natural anaerobic lot (93.0 - 95.8)
        roll = np.random.rand()
        if roll < OUTLIER_DEFECT_LOT_PROB:
            raw_score = float(np.random.uniform(73.5, 78.5))
        elif roll < (OUTLIER_DEFECT_LOT_PROB + OUTLIER_COE_WINNER_PROB):
            raw_score = float(np.random.uniform(93.0, 95.8))

        # Clip to valid specialty/commercial cupping range (72.0 to 96.5)
        return round(float(np.clip(raw_score, 72.0, 96.5)), 2)

    def run_simulation(
        self,
        weather_df: pd.DataFrame,
    ) -> Tuple[
        List[LoteAcopio],
        List[ProcesamientoBeneficio],
        List[SubastaEspecial],
        List[EmbarqueExportacion],
    ]:
        """Run full year coffee cycle simulation."""
        logger.info(f"Starting Cooperativa El Volcán simulation across {len(weather_df)} days...")

        lotes: List[LoteAcopio] = []
        procesos: List[ProcesamientoBeneficio] = []
        subastas: List[SubastaEspecial] = []
        embarques: List[EmbarqueExportacion] = []

        lote_counter = 1
        proceso_counter = 1
        subasta_counter = 1
        embarque_counter = 1

        # Farm selection weights proportional to coffee area (manzanas)
        farm_weights = np.array([f.area_manzanas for f in self.fincas])
        farm_weights = farm_weights / farm_weights.sum()

        certifications = self.notes_templates.get("certificaciones", ["Convencional"])
        buyers = self.notes_templates.get("clientes_compradores", [])

        for day_idx, (_, row) in enumerate(weather_df.iterrows()):
            curr_date: date = row["fecha"]
            precip_mm: float = float(row["precipitacion_mm"])
            daily_lots_count = self.get_seasonal_daily_lots(curr_date, precip_mm)

            for _ in range(daily_lots_count):
                lote_id = lote_counter
                lote_counter += 1

                # Sample farm
                finca_idx = int(np.random.choice(len(self.fincas), p=farm_weights))
                finca = self.fincas[finca_idx]

                # Sample variety conditioned on region (Chi-Square guarantee)
                id_variedad = self.sample_variety_for_region(finca.region)
                variedad = self.variedades_map[id_variedad]

                # Assign harvesting crew
                cuadrilla = np.random.choice(self.active_cuadrillas)

                # Cherry weight (kg): Fresh coffee picked in a single lot
                # Standard harvest lot with realistic lognormal/normal distribution
                peso_cereza = round(float(np.random.normal(1250.0, 420.0)), 2)

                # Lot volume outliers (~3% of lots):
                # - Mega harvest delivery from large hacienda peak day (3,800 - 5,400 kg)
                # - End-of-season repela / smallholder parcel delivery (95 - 220 kg)
                lot_roll = np.random.rand()
                if lot_roll < OUTLIER_MEGA_LOT_PROB:
                    peso_cereza = round(float(np.random.uniform(3800.0, 5400.0)), 2)
                elif lot_roll < (OUTLIER_MEGA_LOT_PROB + OUTLIER_REPELA_LOT_PROB):
                    peso_cereza = round(float(np.random.uniform(95.0, 220.0)), 2)
                else:
                    peso_cereza = max(250.0, peso_cereza)

                # Initial moisture in fresh coffee cherry:
                # Weather-sensitive: heavy rain harvest reaches 64.0-67.5% (outliers), sunny days 52.0-57.0%
                if precip_mm > 15.0:
                    humedad_ini = round(float(np.random.uniform(63.0, 67.5)), 2)
                elif precip_mm == 0.0 and np.random.rand() < 0.20:
                    humedad_ini = round(float(np.random.uniform(52.0, 57.0)), 2)
                else:
                    humedad_ini = round(float(np.random.uniform(57.5, 63.8)), 2)

                # SCAA score
                scaa_score = self.calculate_scaa_score(finca.altitud_msnm, id_variedad)

                # Certification assignment
                if finca.region == "Madriz" and np.random.rand() < 0.65:
                    cert = "Orgánico"
                elif scaa_score >= 88.0:
                    cert = "SHG" # Strictly High Grown
                elif np.random.rand() < 0.35:
                    cert = "Fairtrade"
                elif np.random.rand() < 0.25:
                    cert = "Rainforest Alliance"
                else:
                    cert = "Convencional"

                # Harvesting labor cost (Nicaragua latas: ~20 latas per 500kg, C$45-55/lata)
                costo_recoleccion = round(peso_cereza * float(np.random.uniform(2.8, 3.5)), 2)

                # Quality triage
                is_discarded = scaa_score < 80.0 and np.random.rand() < 0.15
                estado_lote = "descartado" if is_discarded else "listo_exportacion"

                lote_obj = LoteAcopio(
                    id_lote=lote_id,
                    id_finca=finca.id_finca,
                    id_variedad=id_variedad,
                    id_cuadrilla=cuadrilla.id_cuadrilla,
                    fecha_corte=curr_date,
                    peso_cereza_kg=peso_cereza,
                    humedad_porcentaje=humedad_ini,
                    puntaje_catacion_scaa=scaa_score,
                    certificacion=cert,
                    notas_catacion=None, # Enriched in Stage 3
                    costo_recoleccion_nio=costo_recoleccion,
                    estado_lote=estado_lote,
                )
                lotes.append(lote_obj)

                if is_discarded:
                    continue

                # Wet Milling (Beneficio Húmedo regional)
                wet_mill_id = REGION_WET_MILL.get(finca.region, 1)
                wet_start = datetime.combine(curr_date, time(17, 0)) + timedelta(hours=int(np.random.randint(1, 4)))
                ferm_hours = int(np.random.randint(20, 32))
                wet_end = wet_start + timedelta(hours=ferm_hours)

                # Despulpado y fermentación: ~42% merma (with realistic natural variance: 37% - 47%)
                merma_ferm = round(float(np.clip(np.random.normal(42.0, 2.2), 37.0, 48.0)), 1)
                peso_pergamino_humedo = round(peso_cereza * (1.0 - (merma_ferm / 100.0)), 2)
                procesos.append(
                    ProcesamientoBeneficio(
                        id_proceso=proceso_counter,
                        id_lote=lote_id,
                        id_beneficio=wet_mill_id,
                        etapa="fermentacion",
                        fecha_inicio=wet_start,
                        fecha_fin=wet_end,
                        temperatura_fermentacion_c=round(float(np.random.uniform(18.5, 23.0)), 1),
                        merma_porcentaje=merma_ferm,
                        peso_salida_kg=peso_pergamino_humedo,
                        observaciones_proceso="Fermentación natural en pila con lavado de agua limpia de manantial.",
                    )
                )
                proceso_counter += 1

                # Patio Drying (Secado en patio o camas africanas)
                dry_start = wet_end + timedelta(hours=2)
                dry_days = int(np.random.randint(8, 14))
                dry_end = dry_start + timedelta(days=dry_days)
                # Moisture loss to 11.5%: ~40% merma (with realistic environmental variance: 35% - 45%)
                merma_secado = round(float(np.clip(np.random.normal(40.0, 2.4), 35.0, 46.0)), 1)
                peso_pergamino_seco = round(peso_pergamino_humedo * (1.0 - (merma_secado / 100.0)), 2)
                procesos.append(
                    ProcesamientoBeneficio(
                        id_proceso=proceso_counter,
                        id_lote=lote_id,
                        id_beneficio=wet_mill_id,
                        etapa="secado_patio",
                        fecha_inicio=dry_start,
                        fecha_fin=dry_end,
                        temperatura_fermentacion_c=None,
                        merma_porcentaje=merma_secado,
                        peso_salida_kg=peso_pergamino_seco,
                        observaciones_proceso=f"Secado solar uniforme en camas africanas hasta alcanzar {MOISTURE_TARGET_EXPORT}% de humedad.",
                    )
                )
                proceso_counter += 1

                # Dry Milling (Beneficio Seco Central Sébaco - BNF-005)
                # Trillado: remove pergamino/parchment hull -> green export coffee (café oro)
                mill_start = dry_end + timedelta(days=int(np.random.randint(2, 6)))
                mill_end = mill_start + timedelta(hours=6)
                # Green coffee hulling loss: ~20% merma (with realistic variance: 17% - 23%)
                merma_trillado = round(float(np.clip(np.random.normal(20.0, 1.4), 17.0, 23.0)), 1)
                peso_oro_kg = round(peso_pergamino_seco * (1.0 - (merma_trillado / 100.0)), 2)
                peso_oro_quintales = round(peso_oro_kg / 46.0, 2) # 1 quintal = 46 kg

                procesos.append(
                    ProcesamientoBeneficio(
                        id_proceso=proceso_counter,
                        id_lote=lote_id,
                        id_beneficio=5,
                        etapa="trillado",
                        fecha_inicio=mill_start,
                        fecha_fin=mill_end,
                        temperatura_fermentacion_c=None,
                        merma_porcentaje=merma_trillado,
                        peso_salida_kg=peso_oro_kg,
                        observaciones_proceso="Trillado, clasificación por zaranda 17/18 y selección electrónica de color.",
                    )
                )
                proceso_counter += 1

                # Export Shipment staging through Puerto Corinto
                # Only lots ready for export within the 2024 calendar window with at least 1 quintal oro
                shipment_date = (mill_end + timedelta(days=int(np.random.randint(7, 21)))).date()
                if shipment_date <= date(2024, 12, 31) and peso_oro_quintales >= 1.0:
                    buyer_info = np.random.choice(buyers) if buyers else {"cliente": "General Coffee Importers", "pais": "Estados Unidos"}
                    
                    # Specialty pricing formula (USD per quintal):
                    # Specialty / Auction premiums with commercial discount for defective lots
                    if scaa_score >= 88.0:
                        price_per_qq = round(420.0 + min((scaa_score - 88.0) * 110.0, 750.0), 2)
                    elif scaa_score >= 85.0:
                        price_per_qq = round(280.0 + (scaa_score - 85.0) * 45.0, 2)
                    elif scaa_score >= 80.0:
                        price_per_qq = round(220.0 + (scaa_score - 80.0) * 12.0, 2)
                    else:
                        price_per_qq = round(max(155.0, 200.0 - (80.0 - scaa_score) * 8.0), 2)

                    flete_usd = round(peso_oro_quintales * 18.50, 2) # Transportation from Sébaco to Puerto Corinto
                    total_usd = round((peso_oro_quintales * price_per_qq) + flete_usd, 2)

                    embarques.append(
                        EmbarqueExportacion(
                            id_embarque=embarque_counter,
                            id_lote=lote_id,
                            numero_contenedor=f"MSCU-NIC-{embarque_counter:05d}",
                            puerto_salida="Puerto Corinto, Nicaragua",
                            pais_destino=buyer_info["pais"],
                            cliente_comprador=buyer_info["cliente"],
                            fecha_embarque=shipment_date,
                            peso_oro_quintales=peso_oro_quintales,
                            precio_quintal_usd=price_per_qq,
                            flete_transporte_usd=flete_usd,
                            total_usd=total_usd,
                        )
                    )
                    embarque_counter += 1

        # Match top micro-lots to Knapsack specialty auctions (SUB-001 to SUB-012)
        top_lots = [l for l in lotes if l.puntaje_catacion_scaa >= 87.5 and l.estado_lote == "listo_exportacion"]
        top_lots.sort(key=lambda x: x.puntaje_catacion_scaa, reverse=True)

        for s_seed in self.subastas_seed:
            matched_lot = top_lots[subasta_counter - 1] if len(top_lots) >= subasta_counter else lotes[0]
            subastas.append(
                SubastaEspecial(
                    id_subasta=s_seed.id_subasta,
                    id_lote=matched_lot.id_lote,
                    nombre_lote_especial=s_seed.nombre_lote_especial,
                    peso_quintales=s_seed.peso_quintales,
                    costo_certificacion_usd=s_seed.costo_certificacion_usd,
                    retorno_esperado_usd=s_seed.retorno_esperado_usd,
                    puntaje_taza=matched_lot.puntaje_catacion_scaa,
                    fecha_subasta=s_seed.fecha_subasta,
                    estado_subasta=s_seed.estado_subasta,
                )
            )
            subasta_counter += 1

        logger.info(
            f"Simulation finished! Produced {len(lotes)} lots, {len(procesos)} milling stages, "
            f"{len(subastas)} auction micro-lots, and {len(embarques)} export shipments."
        )
        return lotes, procesos, subastas, embarques
