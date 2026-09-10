set dotenv-load := true
set shell := ["bash", "-uc"]

VENV_BIN := if path_exists(".venv/bin") == "true" { ".venv/bin/" } else { "" }
PYTHON := VENV_BIN + "python"
PIP := VENV_BIN + "pip"
ANTOJITOS := VENV_BIN + "antojitos-sim"
VOLCAN := VENV_BIN + "volcan-sim"
MOVIGO := VENV_BIN + "movigo-sim"
DATA_SIM := VENV_BIN + "data-sim"

# Default: List all available recipes
default:
    @just --list

# Set up virtual environment and install dependencies in editable mode
install:
    {{ PIP }} install -e .

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

# Start mock Open-Meteo API server for Antojitos Express (port 8000)
mock-antojitos port="8000":
    {{ ANTOJITOS }} mock-api --port {{ port }}

# Start mock Open-Meteo API server for Cooperativa El Volcán (port 8001)
mock-volcan port="8001":
    {{ VOLCAN }} mock-api --port {{ port }}

# Start mock Open-Meteo API server for MoviGo (port 8002)
mock-movigo port="8002":
    {{ MOVIGO }} mock-api --port {{ port }}

# Start PostgreSQL service via Docker Compose
db-up:
    docker compose up -d

# Stop PostgreSQL service
db-down:
    docker compose down

# Reset PostgreSQL service and delete stored volume
db-reset:
    docker compose down -v
    docker compose up -d

# Open interactive PostgreSQL shell (psql)
db-psql:
    docker compose exec postgres psql -U postgres -d integrador_db

# Load Antojitos Express data into PostgreSQL (schema raw_staging)
load-antojitos:
	@if [ -f artifacts/antojitos/sql/schema_and_data.sql ]; then \
		if command -v psql >/dev/null 2>&1; then \
			cd artifacts/antojitos/csv && PGPASSWORD=postgres psql -h localhost -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
		else \
			docker compose exec -w /workspace/artifacts/antojitos/csv -T postgres psql -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
		fi \
	else \
		{{ ANTOJITOS }} load; \
	fi

# Load Cooperativa El Volcán data into PostgreSQL (schema raw_staging_volcan)
load-volcan:
	@if [ -f artifacts/volcan/sql/schema_and_data.sql ]; then \
		if command -v psql >/dev/null 2>&1; then \
			cd artifacts/volcan/csv && PGPASSWORD=postgres psql -h localhost -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
		else \
			docker compose exec -w /workspace/artifacts/volcan/csv -T postgres psql -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
		fi \
	else \
		{{ VOLCAN }} load; \
	fi

# Load MoviGo data into PostgreSQL (schema raw_staging_movigo)
load-movigo:
	@if [ -f artifacts/movigo/sql/schema_and_data.sql ]; then \
		if command -v psql >/dev/null 2>&1; then \
			cd artifacts/movigo/csv && PGPASSWORD=postgres psql -h localhost -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
		else \
			docker compose exec -w /workspace/artifacts/movigo/csv -T postgres psql -U postgres -d integrador_db -f ../sql/schema_and_data.sql; \
		fi \
	else \
		{{ MOVIGO }} load; \
	fi

# Load all 3 cases into PostgreSQL
load-all:
    @just load-antojitos
    @just load-volcan
    @just load-movigo
    @echo "✓ All 3 case schemas loaded into PostgreSQL."

# Run fast unit and integration tests (Stats, Numerics, Optimization, Relational Integrity)
test-unit:
    {{ PYTHON }} -m unittest discover -s tests -v

# Run full verification test (unit tests, 3-day simulation across all cases, inspect, and bundle)
test: test-unit
    @echo "\n=== Running fast 3-day verification tests via unified data-sim ==="
    {{ DATA_SIM }} generate --case all --days 3
    @echo "\n=== Verifying generated summary reports ==="
    {{ DATA_SIM }} inspect --case all
    @echo "\n=== Verifying student bundle generation ==="
    {{ DATA_SIM }} bundle --case all
    @echo "\n✓ All 3 simulation pipelines and student bundles verified successfully!"
    @just clean

# Package student capstone bundle for Antojitos Express
bundle-antojitos:
    {{ DATA_SIM }} bundle --case antojitos

# Package student capstone bundle for Cooperativa El Volcán
bundle-volcan:
    {{ DATA_SIM }} bundle --case volcan

# Package student capstone bundle for MoviGo
bundle-movigo:
    {{ DATA_SIM }} bundle --case movigo

# Package student capstone bundles for all 3 cases
bundle-all:
    {{ DATA_SIM }} bundle --case all

# Alias for bundle-all
bundle: bundle-all


# DataOps: Interactive Pipeline Orchestrator
orchestrate:
    ./scripts/orquestador.sh

# DataOps: Ingest weather & driver variables via public APIs
ingest target="all":
    ./scripts/ingesta.sh {{ target }}

# DataOps: Resource & PostgreSQL telemetry monitor
monitor:
    ./scripts/monitor.sh

# DataOps: Versioned data export with checksums
export:
    ./scripts/exportar_resultados.sh

