#!/usr/bin/env bash
# ==============================================================================
# PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
# Componente Curricular: Programación en Scripting (DataOps)
# Script: ingesta.sh
# Descripción: Ingesta automatizada de variables driver externas vía API pública
#              (Open-Meteo) para Antojitos Express, El Volcán y MoviGo.
# Técnicas aplicadas: curl, jq, awk, sed, control de errores, reintentos con backoff,
#                     redirección de streams (STDIN/STDOUT/STDERR) y códigos de salida.
# ==============================================================================

set -euo pipefail

# Constantes de configuración
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_RAW_DIR="${BASE_DIR}/data/raw"
MAX_RETRIES=3
RETRY_DELAY=2

# Colores para salida estructurada en terminal
CLR_RESET="\033[0m"
CLR_RED="\033[1;31m"
CLR_GREEN="\033[1;32m"
CLR_YELLOW="\033[1;33m"
CLR_BLUE="\033[1;34m"
CLR_CYAN="\033[1;36m"

# Función de log estructurado
log_info() {
    printf "${CLR_CYAN}[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]${CLR_RESET} %s\n" "$1"
}

log_pass() {
    printf "${CLR_GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] [PASS]${CLR_RESET} %s\n" "$1"
}

log_warn() {
    printf "${CLR_YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]${CLR_RESET} %s\n" "$1" >&2
}

log_error() {
    printf "${CLR_RED}[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR]${CLR_RESET} %s\n" "$1" >&2
}

# Verificación de dependencias esenciales de Linux
check_dependencies() {
    local deps=("curl" "jq" "awk" "sed")
    for cmd in "${deps[@]}"; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Dependencia requerida no encontrada: '$cmd'. Por favor instálela."
            exit 127
        fi
    done
}

# Ingesta con política de reintentos y backoff exponencial
fetch_with_retry() {
    local url="$1"
    local output_path="$2"
    local description="$3"
    local attempt=1
    local delay="$RETRY_DELAY"

    mkdir -p "$(dirname "$output_path")"
    log_info "Iniciando descarga: $description"

    while [[ $attempt -le $MAX_RETRIES ]]; do
        local http_code
        http_code=$(curl -s -w "%{http_code}" -o "$output_path.tmp" "$url" || echo "000")

        if [[ "$http_code" == "200" ]]; then
            # Validación de integridad de JSON mediante jq
            if jq empty "$output_path.tmp" 2>/dev/null; then
                mv "$output_path.tmp" "$output_path"
                local record_count
                record_count=$(jq '.daily.time | length' "$output_path" 2>/dev/null || echo "N/A")
                log_pass "Descarga exitosa ($record_count registros diarios) -> $output_path"
                return 0
            else
                log_warn "Respuesta HTTP 200 pero contenido JSON corrupto (intento $attempt/$MAX_RETRIES)."
            fi
        else
            log_warn "Fallo HTTP $http_code en intento $attempt/$MAX_RETRIES para: $url"
        fi

        attempt=$((attempt + 1))
        if [[ $attempt -le $MAX_RETRIES ]]; then
            log_info "Esperando ${delay}s antes de reintentar..."
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done

    rm -f "$output_path.tmp"
    log_error "Agotados los $MAX_RETRIES intentos para $description."
    return 1
}

# Ingesta Caso 1: Antojitos Express (Managua, Clima Diario 2024)
ingest_antojitos() {
    local target_dir="${DATA_RAW_DIR}/antojitos"
    local target_file="${target_dir}/clima_managua_2024.json"
    local url="https://archive-api.open-meteo.com/v1/archive?latitude=12.1328&longitude=-86.2504&start_date=2024-01-01&end_date=2024-12-31&daily=precipitation_sum,temperature_2m_mean,weather_code&timezone=America/Managua"

    fetch_with_retry "$url" "$target_file" "Clima Diario Managua 2024 (Antojitos Express)"

    # Resumen rápido con jq y awk
    local rain_sum
    rain_sum=$(jq -r '.daily.precipitation_sum[]' "$target_file" | awk '{sum+=$1} END {printf "%.2f", sum}')
    log_info "[Antojitos] Precipitación anual acumulada: ${rain_sum} mm"
}

# Ingesta Caso 2: Cooperativa El Volcán (Jinotega, Clima Agropecuario 2024)
ingest_volcan() {
    local target_dir="${DATA_RAW_DIR}/volcan"
    local target_file="${target_dir}/clima_jinotega_2024.json"
    local url="https://archive-api.open-meteo.com/v1/archive?latitude=13.088&longitude=-86.002&start_date=2024-01-01&end_date=2024-12-31&daily=precipitation_sum,temperature_2m_mean,temperature_2m_min,temperature_2m_max,relative_humidity_2m_mean,weather_code&timezone=America/Managua"

    fetch_with_retry "$url" "$target_file" "Clima Agropecuario Jinotega 2024 (Cooperativa El Volcán)"

    local temp_avg
    temp_avg=$(jq -r '.daily.temperature_2m_mean[]' "$target_file" | awk '{sum+=$1; count++} END {printf "%.2f", sum/count}')
    log_info "[El Volcán] Temperatura media anual Jinotega: ${temp_avg} °C"
}

# Ingesta Caso 3: MoviGo (Managua, Clima & Tráfico 2024)
ingest_movigo() {
    local target_dir="${DATA_RAW_DIR}/movigo"
    local target_file="${target_dir}/clima_managua_movigo_2024.json"
    local url="https://archive-api.open-meteo.com/v1/archive?latitude=12.1364&longitude=-86.2514&start_date=2024-01-01&end_date=2024-12-31&daily=precipitation_sum,temperature_2m_mean,weather_code&timezone=America/Managua"

    fetch_with_retry "$url" "$target_file" "Clima y Tráfico Urbano Managua 2024 (MoviGo)"

    local max_rain
    max_rain=$(jq -r '.daily.precipitation_sum[]' "$target_file" | sort -nr | head -n 1)
    log_info "[MoviGo] Precipitación máxima diaria en Managua: ${max_rain} mm"
}

# Menú de ayuda
show_help() {
    cat <<EOH
Uso: \$0 [OPCIÓN]

Opciones disponibles:
  all         Ejecuta la ingesta para los tres casos de estudio (por defecto).
  antojitos   Ingesta datos climáticos de Managua para Antojitos Express.
  volcan      Ingesta datos agroclimáticos de Jinotega para Cooperativa El Volcán.
  movigo      Ingesta datos de lluvia y tráfico de Managua para MoviGo.
  help, -h    Muestra esta ayuda.
EOH
}

# Punto de entrada principal
main() {
    check_dependencies
    local target="${1:-all}"

    case "$target" in
        antojitos)
            ingest_antojitos
            ;;
        volcan)
            ingest_volcan
            ;;
        movigo)
            ingest_movigo
            ;;
        all)
            log_info "Iniciando pipeline de ingesta para todos los casos de estudio (2024)..."
            ingest_antojitos
            ingest_volcan
            ingest_movigo
            log_pass "Ingesta completa finalizada con éxito."
            ;;
        help|-h|--help)
            show_help
            ;;
        *)
            log_error "Objetivo desconocido: '$target'"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
