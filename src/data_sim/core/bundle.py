"""Student Bundle Generator.

Creates self-contained, distributable project packages for student groups:
- Complete standalone SQL schemas with generated data
- Clean CSV files for data science pipelines (dbt, pandas, polars)
- DBML relational schema diagrams
- Starter SQL queries demonstrating triggers, functions, and materialized views
- Student assignment guide tailored to the 5 analytical subjects
"""

import shutil
import tarfile
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

STUDENT_BUNDLES_DIR = Path("data/exports/student_bundles")

CASE_METADATA = {
    "antojitos": {
        "folder": "caso_1_antojitos_express",
        "title": "Caso 1: Antojitos Express (Cocina Fantasma y Delivery en Managua)",
        "artifact_dir": Path("artifacts/antojitos"),
        "dbml": Path("antojitos.dbml"),
        "queries": Path("queries/01_antojitos_express.sql"),
        "guide": Path("docs/casos/01_antojitos_express.md"),
        "schema_name": "raw_staging",
    },
    "volcan": {
        "folder": "caso_2_cooperativa_volcan",
        "title": "Caso 2: Cooperativa El Volcán (Café de Exportación de Jinotega)",
        "artifact_dir": Path("artifacts/volcan"),
        "dbml": Path("cooperativa.dbml"),
        "queries": Path("queries/02_cooperativa_volcan.sql"),
        "guide": Path("docs/casos/02_cooperativa_volcan.md"),
        "schema_name": "raw_staging_volcan",
    },
    "movigo": {
        "folder": "caso_3_movigo",
        "title": "Caso 3: MoviGo (Transporte Urbano por Aplicación en Managua)",
        "artifact_dir": Path("artifacts/movigo"),
        "dbml": Path("movigo.dbml"),
        "queries": Path("queries/03_movigo.sql"),
        "guide": Path("docs/casos/03_movigo.md"),
        "schema_name": "raw_staging_movigo",
    },
}


def create_student_bundle(case_key: str, make_archive: bool = True) -> Path:
    """Package all artifacts and student documentation for a specific study case."""
    if case_key not in CASE_METADATA:
        raise ValueError(f"Unknown case '{case_key}'. Available: {list(CASE_METADATA.keys())}")

    meta = CASE_METADATA[case_key]
    bundle_dir = STUDENT_BUNDLES_DIR / meta["folder"]
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy CSV directory
    csv_src = meta["artifact_dir"] / "csv"
    csv_dest = bundle_dir / "csv"
    if csv_src.exists():
        if csv_dest.exists():
            shutil.rmtree(csv_dest)
        shutil.copytree(csv_src, csv_dest)
        logger.info(f"Copied CSV files to {csv_dest}")

    # 2. Copy SQL dump
    sql_src = meta["artifact_dir"] / "sql" / "schema_and_data.sql"
    sql_dest = bundle_dir / "schema_and_data.sql"
    if sql_src.exists():
        shutil.copy(sql_src, sql_dest)
        logger.info(f"Copied SQL schema to {sql_dest}")

    # 3. Copy DBML diagram
    if meta["dbml"].exists():
        shutil.copy(meta["dbml"], bundle_dir / meta["dbml"].name)

    # 4. Copy starter queries
    if meta["queries"].exists():
        shutil.copy(meta["queries"], bundle_dir / "starter_queries.sql")

    # 5. Copy case guide as README.md
    if meta["guide"].exists():
        shutil.copy(meta["guide"], bundle_dir / "README.md")
    else:
        # Fallback brief README
        with open(bundle_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(f"# {meta['title']}\n\nPaquete de datos y esquemas para el Proyecto Integrador.\n")

    logger.info(f"Student bundle created at {bundle_dir}")

    # 6. Optionally create .tar.gz
    if make_archive:
        archive_path = STUDENT_BUNDLES_DIR / f"{meta['folder']}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(bundle_dir, arcname=meta["folder"])
        logger.info(f"Created compressed bundle archive at {archive_path}")
        return archive_path

    return bundle_dir


def create_all_student_bundles(make_archive: bool = True) -> Dict[str, Path]:
    """Create bundles for all 3 semester project cases."""
    results = {}
    for case_key in CASE_METADATA:
        results[case_key] = create_student_bundle(case_key, make_archive=make_archive)
    return results
