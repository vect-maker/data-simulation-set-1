set dotenv-load := true
set shell := ["bash", "-uc"]

VENV_BIN := if path_exists(".venv/bin") == "true" { ".venv/bin/" } else { "" }
PYTHON := VENV_BIN + "python"
PIP := VENV_BIN + "pip"
ANTOJITOS := VENV_BIN + "antojitos-sim"
VOLCAN := VENV_BIN + "volcan-sim"
MOVIGO := VENV_BIN + "movigo-sim"

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
    docker compose exec postgres psql -U antojitos_user -d antojitos_db

# Load Antojitos Express data into PostgreSQL (schema raw_staging)
load-antojitos:
    @if [ -f artifacts/antojitos/sql/schema_and_data.sql ]; then \
        cd artifacts/antojitos/csv && PGPASSWORD=antojitos_secure_password psql -h localhost -U antojitos_user -d antojitos_db -f ../sql/schema_and_data.sql; \
    else \
        {{ ANTOJITOS }} load; \
    fi

# Load Cooperativa El Volcán data into PostgreSQL (schema raw_staging_volcan)
load-volcan:
    @if [ -f artifacts/volcan/sql/schema_and_data.sql ]; then \
        cd artifacts/volcan/csv && PGPASSWORD=antojitos_secure_password psql -h localhost -U antojitos_user -d antojitos_db -f ../sql/schema_and_data.sql; \
    else \
        {{ VOLCAN }} load; \
    fi

# Load MoviGo data into PostgreSQL (schema raw_staging_movigo)
load-movigo:
    @if [ -f artifacts/movigo/sql/schema_and_data.sql ]; then \
        cd artifacts/movigo/csv && PGPASSWORD=antojitos_secure_password psql -h localhost -U antojitos_user -d antojitos_db -f ../sql/schema_and_data.sql; \
    else \
        {{ MOVIGO }} load; \
    fi

# Load all 3 cases into PostgreSQL
load-all:
    @just load-antojitos
    @just load-volcan
    @just load-movigo
    @echo "✓ All 3 case schemas loaded into PostgreSQL."

# Run quick verification test (3 days per case) and clean up
test:
    @echo "=== Running fast 3-day verification tests across all 3 engines ==="
    {{ ANTOJITOS }} generate --days 3
    {{ VOLCAN }} generate --days 3
    {{ MOVIGO }} generate --days 3
    @echo "\n=== Verifying generated summary reports ==="
    {{ ANTOJITOS }} inspect
    {{ VOLCAN }} inspect
    {{ MOVIGO }} inspect
    @echo "\n✓ All 3 simulation pipelines verified successfully!"
    @just clean
