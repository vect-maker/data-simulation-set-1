#!/usr/bin/env bash
# ==============================================================================
# PROYECTO INTEGRADOR: DE LOS DATOS A LA DECISIÓN
# Componente Curricular: Programación en Scripting (DataOps)
# Script: exportar_resultados.sh
# Descripción: Extracción versionada de datos analíticos con compresión y
#              generación de sumas de verificación criptográficas (sha256sum).
# Técnicas aplicadas: psql, tar, gzip, sha256sum, sustitución de comandos,
#                     manejo de fechas, arrays y separación estricta de datos.
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACTS_DIR="${BASE_DIR}/artifacts"
EXPORTS_DIR="${BASE_DIR}/data/exports"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BUNDLE_DIR="${EXPORTS_DIR}/bundle_${TIMESTAMP}"

# Colores
CLR_RESET="\033[0m"
CLR_GREEN="\033[1;32m"
CLR_CYAN="\033[1;36m"
CLR_YELLOW="\033[1;33m"
CLR_RED="\033[1;31m"

log_info() {
    printf "${CLR_CYAN}[EXPORT INFO]${CLR_RESET} %s\n" "$1"
}

log_pass() {
    printf "${CLR_GREEN}[EXPORT PASS]${CLR_RESET} %s\n" "$1"
}

log_error() {
    printf "${CLR_RED}[EXPORT ERROR]${CLR_RESET} %s\n" "$1" >&2
}

mkdir -p "$BUNDLE_DIR"

log_info "Creando exportación versionada: timestamp $TIMESTAMP"

# Copiar artefactos CSV generados
for caso in antojitos volcan movigo; do
    local_csv_dir="${ARTIFACTS_DIR}/${caso}/csv"
    if [[ -d "$local_csv_dir" ]]; then
        mkdir -p "${BUNDLE_DIR}/${caso}"
        cp "${local_csv_dir}"/*.csv "${BUNDLE_DIR}/${caso}/" 2>/dev/null || true
        cp "${ARTIFACTS_DIR}/${caso}/simulation_summary.json" "${BUNDLE_DIR}/${caso}/" 2>/dev/null || true
        log_info "Copiados artefactos de $caso."
    else
        log_error "No se encontraron CSVs para $caso en $local_csv_dir. ¿Ejecutó just generate-all?"
    fi
done

# Generar manifiesto con sha256sum
log_info "Generando firmas de integridad SHA-256..."
MANIFEST_FILE="${BUNDLE_DIR}/checksums.sha256"
find "$BUNDLE_DIR" -type f ! -name "checksums.sha256" -exec sha256sum {} + | sed "s|${BUNDLE_DIR}/||" > "$MANIFEST_FILE"

# Empacar y comprimir
ARCHIVE_PATH="${EXPORTS_DIR}/export_integrador_${TIMESTAMP}.tar.gz"
tar -czf "$ARCHIVE_PATH" -C "$EXPORTS_DIR" "bundle_${TIMESTAMP}"
rm -rf "$BUNDLE_DIR"

log_pass "Exportación empaquetada exitosamente:"
printf "  Archivo:  ${CLR_GREEN}%s${CLR_RESET}\n" "$ARCHIVE_PATH"
printf "  Tamaño:   ${CLR_YELLOW}%s${CLR_RESET}\n" "$(du -h "$ARCHIVE_PATH" | cut -f1)"
printf "  SHA-256:  ${CLR_CYAN}%s${CLR_RESET}\n" "$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')"
