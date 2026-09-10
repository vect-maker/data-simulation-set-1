#!/usr/bin/env bash
# ==============================================================================
# PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
# Componente Curricular: Programación en Scripting (DataOps)
# Script: orquestador.sh
# Descripción: Menú interactivo de orquestación para el ciclo de vida del pipeline
#              analítico (Ingesta -> Simulación -> Carga -> Inspección -> Exportación).
# Técnicas aplicadas: Funciones, interfaces de texto ANSI, control de errores,
#                     arrays asociativos, trap para salida limpia y códigos de retorno.
# ==============================================================================

set -uo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${BASE_DIR}/.venv/bin/python"

# Colores y formato
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_RED="\033[1;31m"
CLR_GREEN="\033[1;32m"
CLR_YELLOW="\033[1;33m"
CLR_BLUE="\033[1;34m"
CLR_MAGENTA="\033[1;35m"
CLR_CYAN="\033[1;36m"

# Manejo de señales para salida ordenada
cleanup() {
    printf "\n${CLR_YELLOW}[orquestador.sh] Sesión interrumpida por el usuario. Saliendo...${CLR_RESET}\n"
    exit 0
}
trap cleanup SIGINT SIGTERM

log_step() {
    printf "${CLR_CYAN}==>${CLR_RESET} ${CLR_BOLD}%s${CLR_RESET}\n" "$1"
}

log_pass() {
    printf "  ${CLR_GREEN}✓ [PASS]${CLR_RESET} %s\n" "$1"
}

log_warn() {
    printf "  ${CLR_YELLOW}⚠ [WARN]${CLR_RESET} %s\n" "$1"
}

log_error() {
    printf "  ${CLR_RED}✗ [ERROR]${CLR_RESET} %s\n" "$1" >&2
}

# 1. Verificación de entorno y dependencias
verificar_entorno() {
    log_step "Verificando entorno de ejecución y dependencias..."
    local ok=true

    # Python
    if [[ -x "$VENV_PYTHON" ]]; then
        local py_version
        py_version=$("$VENV_PYTHON" --version)
        log_pass "Entorno virtual Python detectado: $py_version"
    else
        log_warn "Entorno virtual .venv no detectado en $VENV_PYTHON. Usando python3 del sistema si existe."
        if command -v python3 &>/dev/null; then
            VENV_PYTHON="python3"
            log_pass "Python del sistema: $(python3 --version)"
        else
            log_error "Python 3 no disponible. Ejecute: just install"
            ok=false
        fi
    fi

    # Docker / PostgreSQL
    if command -v docker &>/dev/null; then
        if docker info &>/dev/null; then
            log_pass "Docker daemon activo."
        else
            log_warn "Docker está instalado pero el demonio no responde."
        fi
    else
        log_warn "Docker no encontrado en PATH (opcional si usa PostgreSQL local)."
    fi

    # Herramientas esenciales de Linux
    local tools=("curl" "jq" "awk" "sed" "psql")
    for t in "${tools[@]}"; do
        if command -v "$t" &>/dev/null; then
            log_pass "Herramienta CLI '$t' disponible."
        else
            log_warn "Herramienta CLI '$t' no encontrada en PATH."
        fi
    done

    if [[ "$ok" == true ]]; then
        log_pass "Chequeo de precondiciones finalizado exitosamente."
    else
        log_error "Se detectaron problemas en el entorno."
    fi
}

# 2. Ingesta meteorológica
ejecutar_ingesta() {
    log_step "Disparando script de ingesta automatizada (ingesta.sh)..."
    if "${BASE_DIR}/scripts/ingesta.sh" all; then
        log_pass "Ingesta completada correctamente."
    else
        log_error "Falló el pipeline de ingesta."
    fi
}

# 3. Generación de simulaciones sintéticas
ejecutar_simulacion() {
    local dias="${1:-}"
    log_step "Ejecutando motores de simulación transaccional (2024)..."

    local dias_flag=""
    if [[ -n "$dias" ]]; then
        dias_flag="--days $dias"
        log_info "Generando período reducido: $dias días."
    fi

    printf "${CLR_BLUE}--> [1/3] Simulando Caso 1: Antojitos Express...${CLR_RESET}\n"
    "$VENV_PYTHON" -m antojitos_sim.cli generate $dias_flag || { log_error "Error en Antojitos Express"; return 1; }

    printf "${CLR_BLUE}--> [2/3] Simulando Caso 2: Cooperativa El Volcán...${CLR_RESET}\n"
    "$VENV_PYTHON" -m volcan_sim.cli generate $dias_flag || { log_error "Error en Cooperativa El Volcán"; return 1; }

    printf "${CLR_BLUE}--> [3/3] Simulando Caso 3: MoviGo...${CLR_RESET}\n"
    "$VENV_PYTHON" -m movigo_sim.cli generate $dias_flag || { log_error "Error en MoviGo"; return 1; }

    log_pass "Simulaciones generadas con éxito para los 3 casos."
}

# 4. Inspección analítica
inspeccionar_metricas() {
    log_step "Desplegando reportes estadísticos, numéricos y de optimización..."
    printf "\n${CLR_BOLD}=== CASO 1: ANTOJITOS EXPRESS ===${CLR_RESET}\n"
    "$VENV_PYTHON" -m antojitos_sim.cli inspect || true

    printf "\n${CLR_BOLD}=== CASO 2: COOPERATIVA EL VOLCÁN ===${CLR_RESET}\n"
    "$VENV_PYTHON" -m volcan_sim.cli inspect || true

    printf "\n${CLR_BOLD}=== CASO 3: MOVIGO ===${CLR_RESET}\n"
    "$VENV_PYTHON" -m movigo_sim.cli inspect || true
}

# 5. Carga a PostgreSQL
cargar_datos() {
    log_step "Cargando artefactos en esquemas de PostgreSQL..."
    if command -v just &>/dev/null; then
        just load-all || log_warn "Carga vía just retornó advertencias. Verifique si PostgreSQL está activo (just db-up)."
    else
        "$VENV_PYTHON" -m antojitos_sim.cli load || true
        "$VENV_PYTHON" -m volcan_sim.cli load || true
        "$VENV_PYTHON" -m movigo_sim.cli load || true
    fi
}

# 6. Monitoreo en segundo plano
lanzar_monitor() {
    log_step "Iniciando monitor de procesos y telemetría (monitor.sh)..."
    if [[ -x "${BASE_DIR}/scripts/monitor.sh" ]]; then
        "${BASE_DIR}/scripts/monitor.sh" &
        local mon_pid=$!
        log_pass "Monitor corriendo en background (PID: $mon_pid)."
        log_info "Para detenerlo: kill $mon_pid"
    else
        log_error "scripts/monitor.sh no encontrado o sin permisos de ejecución."
    fi
}

# 7. Exportación versionada
exportar_datos() {
    log_step "Exportando datasets versionados para análisis (exportar_resultados.sh)..."
    if [[ -x "${BASE_DIR}/scripts/exportar_resultados.sh" ]]; then
        "${BASE_DIR}/scripts/exportar_resultados.sh"
    else
        log_error "scripts/exportar_resultados.sh no encontrado o sin permisos."
    fi
}

# Despliegue de banner
print_banner() {
    printf "${CLR_CYAN}"
    cat <<'EOB'
╔══════════════════════════════════════════════════════════════════════════╗
║        ORQUESTADOR DATAOPS - PROYECTO INTEGRADOR (NICARAGUA)            ║
║  De los Datos a la Decisión: BD Analíticas | Estadística | Numérico | Opt ║
╚══════════════════════════════════════════════════════════════════════════╝
EOB
    printf "${CLR_RESET}\n"
}

# Bucle interactivo principal
menu_principal() {
    while true; do
        print_banner
        printf "Seleccione una operación a ejecutar:\n\n"
        printf "  ${CLR_BOLD}[1]${CLR_RESET} Verificar entorno y dependencias del sistema\n"
        printf "  ${CLR_BOLD}[2]${CLR_RESET} Ingesta meteorológica externa (Open-Meteo API -> data/raw)\n"
        printf "  ${CLR_BOLD}[3]${CLR_RESET} Ejecutar simulación completa (Antojitos, El Volcán, MoviGo)\n"
        printf "  ${CLR_BOLD}[4]${CLR_RESET} Ejecutar simulación rápida de prueba (3 días de verificación)\n"
        printf "  ${CLR_BOLD}[5]${CLR_RESET} Cargar datasets simulados en PostgreSQL (raw_staging)\n"
        printf "  ${CLR_BOLD}[6]${CLR_RESET} Inspeccionar métricas, supuestos OLS y modelos de optimización\n"
        printf "  ${CLR_BOLD}[7]${CLR_RESET} Lanzar monitor de salud del sistema y contenedores\n"
        printf "  ${CLR_BOLD}[8]${CLR_RESET} Exportar datasets analíticos versionados con checksums\n"
        printf "  ${CLR_BOLD}[0]${CLR_RESET} Salir\n\n"
        read -rp "Opción [0-8]: " opt

        case "$opt" in
            1) verificar_entorno ;;
            2) ejecutar_ingesta ;;
            3) ejecutar_simulacion ;;
            4) ejecutar_simulacion 3 ;;
            5) cargar_datos ;;
            6) inspeccionar_metricas ;;
            7) lanzar_monitor ;;
            8) exportar_datos ;;
            0|q|exit)
                printf "${CLR_GREEN}Sesión de orquestación finalizada. ¡Buen trabajo!${CLR_RESET}\n"
                exit 0
                ;;
            *)
                log_error "Opción no válida: '$opt'"
                ;;
        esac

        printf "\nPresione ENTER para volver al menú principal..."
        read -r
        clear || true
    done
}

# Ejecución por argumentos CLI directos o menú interactivo
if [[ $# -gt 0 ]]; then
    case "$1" in
        check)      verificar_entorno ;;
        ingest)     ejecutar_ingesta ;;
        sim)        ejecutar_simulacion "${2:-}" ;;
        inspect)    inspeccionar_metricas ;;
        load)       cargar_datos ;;
        export)     exportar_datos ;;
        *)
            echo "Uso: $0 [check|ingest|sim|inspect|load|export] o sin argumentos para menú interactivo."
            exit 1
            ;;
    esac
else
    menu_principal
fi
