set dotenv-load := true
set shell := ["bash", "-uc"]

VENV_BIN := if path_exists(".venv/bin") == "true" { ".venv/bin/" } else { "" }
PYTHON := VENV_BIN + "python"
PIP := VENV_BIN + "pip"
ANTOJITOS := VENV_BIN + "antojitos-sim"
VOLCAN := VENV_BIN + "volcan-sim"
MOVIGO := VENV_BIN + "movigo-sim"
DATA_SIM := VENV_BIN + "data-sim"
COMPOSE := "podman compose"

# Default: List all available recipes
default:
    @just --list

# Set up local virtual environment with uv (installs uv automatically if not present)
setup-uv:
    #!/usr/bin/env bash
    set -euo pipefail
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    if ! command -v uv >/dev/null 2>&1; then
        echo "==> uv not found in PATH. Installing uv via official installer..."
        if command -v curl >/dev/null 2>&1; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        elif command -v wget >/dev/null 2>&1; then
            wget -qO- https://astral.sh/uv/install.sh | sh
        elif command -v python3 >/dev/null 2>&1; then
            python3 -m pip install --user uv
        else
            pip install --user uv
        fi
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    fi

    if ! command -v uv >/dev/null 2>&1; then
        echo "ERROR: uv could not be found or installed. Please install uv manually." >&2
        exit 1
    fi

    echo "✓ Detected $(uv --version)"

    if [ ! -d ".venv" ]; then
        echo "==> Creating virtual environment (.venv)..."
        uv venv
    fi

    echo "==> Installing dependencies in editable mode via uv..."
    uv pip install -e ".[dev]"
    echo "✓ Local uv environment successfully configured in .venv!"

# Alias for setup-uv
setup: setup-uv

# Install dependencies into virtual environment (delegates to setup-uv)
install: setup-uv

# Clean all generated artifacts, caches, and temporary files
clean:
    rm -rf artifacts/
    rm -rf data/cache/
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    find . -name "*.tmp" -delete
    @echo "✓ Cleaned artifacts, caches, and temporary files."

# Clean all generated artifacts, raw weather caches, and temporary files
clean-all: clean
    rm -rf data/raw/
    @echo "✓ Cleaned all raw weather datasets."

# Fetch/generate weather data from Open-Meteo API for Antojitos Express
fetch-weather-antojitos:
    {{ ANTOJITOS }} fetch-weather

# Fetch/generate weather data from Open-Meteo API for Cooperativa El Volcán
fetch-weather-volcan:
    {{ VOLCAN }} fetch-weather

# Fetch/generate weather data from Open-Meteo API for MoviGo
fetch-weather-movigo:
    {{ MOVIGO }} fetch-weather

# Fetch/generate weather data from Open-Meteo API for all 3 cases (replaces raw data)
fetch-weather:
    @echo "=== [1/3] Fetching weather from Open-Meteo for Antojitos Express ==="
    @just fetch-weather-antojitos
    @echo "\n=== [2/3] Fetching agro-weather from Open-Meteo for Cooperativa El Volcán ==="
    @just fetch-weather-volcan
    @echo "\n=== [3/3] Fetching weather from Open-Meteo for MoviGo ==="
    @just fetch-weather-movigo
    @echo "\n✓ Weather data fetched and raw datasets updated for all 3 cases."

# Alias for fetch-weather
weather: fetch-weather

# Generate dimensional catalog seeds with Gemini API for Antojitos Express
seed-antojitos:
    {{ PYTHON }} scripts/generate_antojitos_seeds.py

# Generate dimensional catalog seeds with Gemini API for Cooperativa El Volcán
seed-volcan:
    {{ PYTHON }} scripts/generate_volcan_seeds.py

# Generate dimensional catalog seeds with Gemini API for MoviGo
seed-movigo:
    {{ PYTHON }} scripts/generate_movigo_seeds.py

# Download OSM tiles and render 4 thematic cartographic maps for MoviGo
maps-movigo:
    {{ PYTHON }} scripts/generate_movigo_maps.py

# Audit MoviGo simulation data in PostgreSQL using DuckDB extension
audit-movigo:
    {{ PYTHON }} scripts/audit_movigo_duckdb.py


# Generate dimensional catalog seeds with Gemini API for all 3 cases
seed-all:
    {{ PYTHON }} scripts/generate_all_seeds.py

# Alias for seed-all
seed: seed-all

# Generate synthetic dataset for Antojitos Express (Caso 1)
generate-antojitos days="":
    @if [ -n "{{ days }}" ]; then \
        {{ ANTOJITOS }} generate --days {{ days }}; \
    else \
        {{ ANTOJITOS }} generate; \
    fi

# Generate synthetic dataset for Cooperativa El Volcán (Caso 2)
generate-volcan days="":
    @if [ -n "{{ days }}" ]; then \
        {{ VOLCAN }} generate --days {{ days }}; \
    else \
        {{ VOLCAN }} generate; \
    fi

# Generate synthetic dataset for MoviGo (Caso 3)
generate-movigo days="":
    @if [ -n "{{ days }}" ]; then \
        {{ MOVIGO }} generate --days {{ days }}; \
    else \
        {{ MOVIGO }} generate; \
    fi

# Generate synthetic datasets for all 3 cases
generate-all days="":
    @echo "=== [1/3] Generating Caso 1: Antojitos Express ==="
    @just generate-antojitos {{ days }}
    @echo "\n=== [2/3] Generating Caso 2: Cooperativa El Volcán ==="
    @just generate-volcan {{ days }}
    @echo "\n=== [3/3] Generating Caso 3: MoviGo ==="
    @just generate-movigo {{ days }}
    @echo "\n✓ All 3 case simulations generated successfully!"

# Inspect summary metrics for Antojitos Express
inspect-antojitos:
    {{ ANTOJITOS }} inspect

# Inspect summary metrics for Cooperativa El Volcán
inspect-volcan:
    {{ VOLCAN }} inspect

# Inspect summary metrics for MoviGo
inspect-movigo:
    {{ MOVIGO }} inspect

# Inspect summary metrics for all 3 cases
inspect-all:
    @echo "=== Summary: Caso 1 (Antojitos Express) ==="
    @just inspect-antojitos
    @echo "\n=== Summary: Caso 2 (Cooperativa El Volcán) ==="
    @just inspect-volcan
    @echo "\n=== Summary: Caso 3 (MoviGo) ==="
    @just inspect-movigo

# Start PostgreSQL service via Podman Compose
db-up:
    {{ COMPOSE }} up -d postgres

# Stop PostgreSQL service
db-down:
    {{ COMPOSE }} stop postgres

# Reset PostgreSQL service and delete stored volume
db-reset:
    {{ COMPOSE }} down -v
    {{ COMPOSE }} up -d postgres
    @echo "Waiting for PostgreSQL to be ready..."
    @until {{ COMPOSE }} exec -T postgres pg_isready -p ${POSTGRES_PORT:-5433} -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-integrador_db} >/dev/null 2>&1; do \
        sleep 0.5; \
    done
    @echo "✓ PostgreSQL is ready."

# Start all services (PostgreSQL + FastAPI API) via Podman Compose
api-up:
    {{ COMPOSE }} up -d --build

# Stop all services (PostgreSQL + FastAPI API)
api-down:
    {{ COMPOSE }} down

# Stream logs for the FastAPI API container
api-logs:
    {{ COMPOSE }} logs -f api

# Restart FastAPI API container
api-restart:
    {{ COMPOSE }} restart api

# Run FastAPI API locally for development without Podman
api-run:
    {{ VENV_BIN }}uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Evaluate FastAPI endpoints against CSV artifacts (e.g. just api-eval or just api-eval volcan)
api-eval case="all":
    {{ PYTHON }} scripts/evaluate_api_vs_csv.py --case {{ case }}

# Open interactive PostgreSQL shell (psql)
db-psql:
    {{ COMPOSE }} exec postgres psql -U postgres -d integrador_db

# Load Antojitos Express data into PostgreSQL (schema raw_staging)
load-antojitos:
    @if [ -f artifacts/antojitos/sql/schema_and_data.sql ]; then \
        {{ COMPOSE }} exec -w /workspace/artifacts/antojitos/csv -T postgres psql -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
    else \
        {{ ANTOJITOS }} load; \
    fi

# Load Cooperativa El Volcán data into PostgreSQL (schema raw_staging_volcan)
load-volcan:
    @if [ -f artifacts/volcan/sql/schema_and_data.sql ]; then \
        {{ COMPOSE }} exec -w /workspace/artifacts/volcan/csv -T postgres psql -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
    else \
        {{ VOLCAN }} load; \
    fi

# Load MoviGo Parquet data into PostgreSQL (schema raw_staging_movigo) in streaming batches
load-movigo batch_size="":
    @if [ -n "{{ batch_size }}" ]; then \
        {{ PYTHON }} scripts/load_movigo_parquet_to_postgres.py --batch-size {{ batch_size }}; \
    else \
        {{ PYTHON }} scripts/load_movigo_parquet_to_postgres.py; \
    fi

# Load all 3 cases into PostgreSQL
load-all:
    @just load-antojitos
    @just load-volcan
    @just load-movigo
    @echo "✓ All 3 case schemas loaded into PostgreSQL."

# Reset PostgreSQL database entirely (wipe volume) and reload all data from artifacts
db-reload:
    @echo "=== [1/2] Resetting PostgreSQL database entirely (wiping storage volume) ==="
    @just db-reset
    @echo "\n=== [2/2] Loading all 3 case schemas and data from artifacts ==="
    @just load-all
    @echo "\n✓ Database successfully reset and fully reloaded from artifacts!"

# Alias for db-reload
reload-db: db-reload

# Drop all 3 staging schemas without restarting the PostgreSQL container
db-reset-schemas:
    @echo "Purging all 3 schemas (raw_staging, raw_staging_volcan, raw_staging_movigo)..."
    @{{ COMPOSE }} exec -T postgres psql -U postgres -d integrador_db -c "DROP SCHEMA IF EXISTS raw_staging CASCADE; DROP SCHEMA IF EXISTS raw_staging_volcan CASCADE; DROP SCHEMA IF EXISTS raw_staging_movigo CASCADE;"
    @echo "✓ Staging schemas purged."

# Reseed all staging schemas from artifacts without restarting the container
db-reseed:
    @just db-reset-schemas
    @just load-all
    @echo "\n✓ Database schemas successfully reseeded from artifacts!"

# Run fast unit and integration tests (Stats, Numerics, Optimization, Relational Integrity)
test-unit:
    {{ PYTHON }} -m unittest discover -s tests -v

# Run full verification test (unit tests, 3-day simulation across all cases, inspect)
test: test-unit
    @echo "\n=== Running fast 3-day verification tests via unified data-sim ==="
    {{ DATA_SIM }} generate --case all --days 3
    @echo "\n=== Verifying generated summary reports ==="
    {{ DATA_SIM }} inspect --case all
    @echo "\n✓ All 3 simulation pipelines verified successfully!"
# Reset all generated artifacts, caches, and database volumes
reset-all:
    @just clean
    @if {{ COMPOSE }} ps -q postgres 2>/dev/null | grep -q .; then \
        just db-reset; \
    fi
    @echo "✓ Full reset completed: artifacts, caches, and database storage wiped."

# End-to-end workflow: clean, regenerate data, inspect, and load into PostgreSQL
pipeline days="":
    @just clean
    @just generate-all {{ days }}
    @just inspect-all
    @if {{ COMPOSE }} ps -q postgres 2>/dev/null | grep -q .; then \
        just load-all; \
    else \
        echo "ℹ PostgreSQL is not running. Start it with 'just db-up' and run 'just load-all' to populate DB."; \
    fi
    @echo "\n✓ End-to-end pipeline completed! Expose API with 'just api-run' (local) or 'just api-up' (podman)."
