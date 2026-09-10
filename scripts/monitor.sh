#!/usr/bin/env bash
# ==============================================================================
# PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
# Componente Curricular: Programación en Scripting (DataOps)
# Script: monitor.sh
# Descripción: Supervisión continua de CPU, memoria, almacenamiento y salud
#              del contenedor de base de datos PostgreSQL.
# Técnicas aplicadas: Comando trap para manejo de señales (SIGINT/SIGTERM),
#                     parseo de /proc o ps, grep, awk, redirección a logs y rotación.
# ==============================================================================

set -uo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${BASE_DIR}/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/monitor_$(date '+%Y%m%d').log"

INTERVAL=5
ONCE=false

# Colores
CLR_RESET="\033[0m"
CLR_RED="\033[1;31m"
CLR_GREEN="\033[1;32m"
CLR_YELLOW="\033[1;33m"
CLR_CYAN="\033[1;36m"

# Manejo de señales con trap (Requerimiento explícito del programa de Scripting)
cleanup() {
    printf "\n${CLR_YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] Señal de terminación recibida. Deteniendo monitor.${CLR_RESET}\n" | tee -a "$LOG_FILE"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Parseo de argumentos CLI
while [[ $# -gt 0 ]]; do
    case "$1" in
        --once)
            ONCE=true
            shift
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        *)
            echo "Uso: $0 [--once] [--interval segundos]"
            exit 1
            ;;
    esac
done

# Función de recolección de métricas
collect_metrics() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # CPU Load Average (1 min)
    local cpu_load="N/A"
    if [[ -f /proc/loadavg ]]; then
        cpu_load=$(awk '{print $1}' /proc/loadavg)
    fi

    # Memoria RAM (libre / total en MB)
    local mem_used="N/A"
    local mem_total="N/A"
    if command -v free &>/dev/null; then
        mem_used=$(free -m | awk '/Mem:/ {print $3}')
        mem_total=$(free -m | awk '/Mem:/ {print $2}')
    fi

    # Disco: espacio libre en partición del proyecto
    local disk_avail
    disk_avail=$(df -h "$BASE_DIR" | awk 'NR==2 {print $4}')

    # Salud del contenedor PostgreSQL
    local pg_status="INACTIVO"
    if command -v docker &>/dev/null; then
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "postgres"; then
            pg_status="ACTIVO (Docker)"
        fi
    fi
    if [[ "$pg_status" == "INACTIVO" ]] && command -v pg_isready &>/dev/null; then
        if pg_isready -h localhost -p 5432 &>/dev/null; then
            pg_status="ACTIVO (Local)"
        fi
    fi

    # Formateo de salida para terminal y archivo
    local log_entry="[$timestamp] CPU Load: ${cpu_load} | RAM: ${mem_used}MB / ${mem_total}MB | Disco Disp: ${disk_avail} | PostgreSQL: ${pg_status}"
    echo "$log_entry" >> "$LOG_FILE"

    printf "${CLR_CYAN}[%s]${CLR_RESET} CPU Load: ${CLR_GREEN}%s${CLR_RESET} | RAM: ${CLR_YELLOW}%sMB/%sMB${CLR_RESET} | Disco: ${CLR_GREEN}%s${CLR_RESET} | PG: ${CLR_GREEN}%s${CLR_RESET}\n" \
        "$timestamp" "$cpu_load" "$mem_used" "$mem_total" "$disk_avail" "$pg_status"
}

printf "${CLR_GREEN}=== Monitor de Sistema y Contenedores Iniciado ===${CLR_RESET}\n"
printf "Guardando telemetría en: %s\n" "$LOG_FILE"
printf "Presione Ctrl+C para detener.\n\n"

if [[ "$ONCE" == true ]]; then
    collect_metrics
    exit 0
fi

while true; do
    collect_metrics
    sleep "$INTERVAL"
done
