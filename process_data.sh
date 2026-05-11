#!/bin/bash
# =============================================================================
# FitonDuty March Data Processing Runner
# =============================================================================
# Usage:
#   ./process_data.sh --march <config> --date <YYYYMMDD> [options]
#
# Required Arguments:
#   --march <path>        Path to march configuration file
#   --date <YYYYMMDD>     Processing date (e.g., 20260410)
#
# Optional Arguments:
#   --skip-process        Skip processing steps, only run merge/load
#   --skip-load           Skip database loading step
#   --env-file <path>     Override environment file for database loading
#   --participants <path> Override participants CSV file
#   -h, --help            Show this help message
#
# Examples:
#   # Process data for an existing march on a specific date:
#   ./process_data.sh --march config/marches/march_2_ghent.sh --date 20260410
#
#   # Reprocess without loading to database:
#   ./process_data.sh --march config/marches/march_2_ghent.sh --date 20260410 --skip-load
#
#   # Only run merge and load (skip processing):
#   ./process_data.sh --march config/marches/march_2_ghent.sh --date 20260410 --skip-process
# =============================================================================

set -euo pipefail

# Prevent shellcheck warnings about dynamic source
# shellcheck source=/dev/null

# --- 1. Parse Arguments ------------------------------------------------------

MARCH_CONFIG=""
DATE_YYYYMMDD=""
SKIP_PROCESS=false
SKIP_LOAD=false
ENV_FILE_OVERRIDE=""
PARTICIPANTS_OVERRIDE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --march)
            MARCH_CONFIG="$2"
            shift 2
            ;;
        --date)
            DATE_YYYYMMDD="$2"
            shift 2
            ;;
        --skip-process)
            SKIP_PROCESS=true
            shift
            ;;
        --skip-load)
            SKIP_LOAD=true
            shift
            ;;
        --env-file)
            ENV_FILE_OVERRIDE="$2"
            shift 2
            ;;
        --participants)
            PARTICIPANTS_OVERRIDE="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '2,34p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# --- 2. Validation ----------------------------------------------------------

if [ -z "${MARCH_CONFIG}" ]; then
    echo "Error: --march argument is required"
    echo "Usage: $0 --march <config> --date <YYYYMMDD>"
    exit 1
fi

if [ -z "${DATE_YYYYMMDD}" ]; then
    echo "Error: --date argument is required"
    echo "Usage: $0 --march <config> --date <YYYYMMDD>"
    exit 1
fi

if [ ! -f "${MARCH_CONFIG}" ]; then
    echo "Error: March configuration file not found: ${MARCH_CONFIG}"
    exit 1
fi

# Validate date format (YYYYMMDD)
if ! [[ "${DATE_YYYYMMDD}" =~ ^[0-9]{8}$ ]]; then
    echo "Error: Date must be in YYYYMMDD format (e.g., 20260410)"
    exit 1
fi

# --- 3. Load March Configuration --------------------------------------------

# Source the configuration file (it sets MARCH_ID, coordinates, etc.)
# shellcheck disable=SC1090
source "${MARCH_CONFIG}"

# Validate required fields from config
if [ -z "${MARCH_ID:-}" ]; then
    echo "Error: MARCH_ID must be set in the march configuration file"
    exit 1
fi

if [ -z "${START_LAT:-}" ] || [ -z "${START_LON:-}" ] || [ -z "${END_LAT:-}" ] || [ -z "${END_LON:-}" ]; then
    echo "Error: START_LAT, START_LON, END_LAT, and END_LON must be set in the march configuration file"
    exit 1
fi

# --- 4. Set Defaults & Auto-calculated Values -------------------------------

# Convert 20260410 -> 2026_04_10
DATE_YYYY_MM_DD="${DATE_YYYYMMDD:0:4}_${DATE_YYYYMMDD:4:2}_${DATE_YYYYMMDD:6:2}"

# Defaults
DATA_ROOT="${DATA_ROOT:-/data}"
OUTPUT_ROOT="${OUTPUT_ROOT:-./.output}"
GPS_TOLERANCE="${GPS_TOLERANCE:-150}"
MIN_GPS_CROSSING_DELAY="${MIN_GPS_CROSSING_DELAY:-10000}"

# Derived paths
MARCH_DATA_DIR="${DATA_ROOT}/${DATE_YYYYMMDD}_march"
WATCH_DATA_DIR="${WATCH_DATA_DIR:-${MARCH_DATA_DIR}/station_march_${DATE_YYYY_MM_DD}/watch_data/}"
STATION_DIR="${STATION_DIR:-${MARCH_DATA_DIR}/admin_march_${DATE_YYYY_MM_DD}/station_march_${DATE_YYYY_MM_DD}/}"
OUTPUT_DIR="${OUTPUT_ROOT}/${DATE_YYYYMMDD}"
PARTICIPANTS_CSV="${PARTICIPANTS_OVERRIDE:-${PARTICIPANTS_CSV:-config/seed-data/participants_${DATE_YYYYMMDD}.csv}}"

# Determine environment file
if [ -n "${ENV_FILE_OVERRIDE}" ]; then
    ENV_FILE="${ENV_FILE_OVERRIDE}"
elif [ -n "${ENV_FILE:-}" ]; then
    ENV_FILE="${ENV_FILE}"
else
    # Check multiple locations for env file
    if [ -f ".env.${DATE_YYYYMMDD}" ]; then
        ENV_FILE=".env.${DATE_YYYYMMDD}"
    elif [ -f "config/environments/.env.${DATE_YYYYMMDD}" ]; then
        ENV_FILE="config/environments/.env.${DATE_YYYYMMDD}"
    else
        ENV_FILE=".env.${DATE_YYYYMMDD}"
    fi
fi

# --- 5. Configuration Summary -----------------------------------------------

echo "==================================================================="
echo "  FitonDuty March Data Processing"
echo "==================================================================="
echo "Date:               ${DATE_YYYYMMDD} (${DATE_YYYY_MM_DD})"
echo "March Config:       ${MARCH_CONFIG}"
echo "March ID:           ${MARCH_ID}"
echo "March Name:         ${MARCH_NAME:-(not set)}"
echo "March City:         ${MARCH_CITY:-(not set)}"
echo ""
echo "Coordinates:"
echo "  Start:            ${START_LAT}, ${START_LON}"
echo "  End:              ${END_LAT}, ${END_LON}"
echo ""
echo "Paths:"
echo "  Data Root:        ${DATA_ROOT}"
echo "  Watch Data Dir:   ${WATCH_DATA_DIR}"
echo "  Station Dir:      ${STATION_DIR}"
echo "  Output Dir:       ${OUTPUT_DIR}"
echo "  Participants CSV: ${PARTICIPANTS_CSV}"
echo "  Env File:         ${ENV_FILE}"
echo ""
echo "Options:"
echo "  GPS Tolerance:    ${GPS_TOLERANCE}"
echo "  Skip Process:     ${SKIP_PROCESS}"
echo "  Skip Load:        ${SKIP_LOAD}"
echo "==================================================================="

# --- 6. Pre-flight Checks ---------------------------------------------------

ERRORS=0

if [ ! -d "${WATCH_DATA_DIR}" ]; then
    echo "WARNING: Watch data directory not found: ${WATCH_DATA_DIR}"
    ERRORS=$((ERRORS + 1))
fi

if [ ! -d "${STATION_DIR}" ]; then
    echo "WARNING: Station directory not found: ${STATION_DIR}"
    ERRORS=$((ERRORS + 1))
fi

if [ ! -f "${PARTICIPANTS_CSV}" ]; then
    echo "WARNING: Participants CSV not found: ${PARTICIPANTS_CSV}"
    ERRORS=$((ERRORS + 1))
fi

if [ "${SKIP_LOAD}" = false ] && [ ! -f "${ENV_FILE}" ]; then
    echo "WARNING: Environment file not found: ${ENV_FILE}"
    ERRORS=$((ERRORS + 1))
fi

if [ "${SKIP_LOAD}" = false ]; then
    echo ""
    echo "Press Enter to continue or Ctrl+C to cancel..."
    read -r
fi

# --- 7. Processing Steps ----------------------------------------------------

if [ "${SKIP_PROCESS}" = false ]; then
    echo ""
    echo "--- Step 1: Process Watch Data ---"
    uv run scripts/data/process_watch_data.py \
        --data-dir "${WATCH_DATA_DIR}" \
        --march-id "${MARCH_ID}" \
        --start-lat "${START_LAT}" \
        --start-lon "${START_LON}" \
        --end-lat "${END_LAT}" \
        --end-lon "${END_LON}" \
        --gps-tolerance "${GPS_TOLERANCE}" \
        --min-gps-crossing-delay "${MIN_GPS_CROSSING_DELAY}" \
        --output "${OUTPUT_DIR}"

    echo ""
    echo "--- Step 2: Fill Non-Watch Data ---"
    uv run scripts/data/fill_non_watch_data.py \
        --output-dir "${OUTPUT_DIR}" \
        --station-dir "${STATION_DIR}" \
        --participants-csv "${PARTICIPANTS_CSV}" \
        --march-id "${MARCH_ID}"

    echo ""
    echo "--- Step 3: Process Step Data ---"
    uv run scripts/data/process_step_data.py \
        --data-dir "${STATION_DIR}" \
        --march-id "${MARCH_ID}" \
        --gps-trim-file "${OUTPUT_DIR}/gps_crossing_times.json" \
        --output "${OUTPUT_DIR}"

    echo ""
    echo "--- Step 4: Process Temperature Data ---"
    uv run scripts/data/process_temp_data.py \
        --data-dir "${STATION_DIR}" \
        --march-id "${MARCH_ID}" \
        --gps-trim-file "${OUTPUT_DIR}/gps_crossing_times.json" \
        --output "${OUTPUT_DIR}"

    echo ""
    echo "--- Step 5: Merge Data ---"
    uv run scripts/data/merge_march_data.py \
        --watch-data "${OUTPUT_DIR}/march_timeseries_data.csv" \
        --step-data "${OUTPUT_DIR}/march_step_data.csv" \
        --watch-summary "${OUTPUT_DIR}/march_health_metrics.csv" \
        --step-summary "${OUTPUT_DIR}/march_step_summary.csv" \
        --temp-summary "${OUTPUT_DIR}/march_temp_summary.csv" \
        --output "${OUTPUT_ROOT}"

    # Post-merge file movements
    echo ""
    echo "--- Moving merged files ---"
    mv "${OUTPUT_ROOT}/march_timeseries_data_merged.csv" "${OUTPUT_ROOT}/march_timeseries_data.csv"
    mv "${OUTPUT_ROOT}/march_health_metrics_merged.csv" "${OUTPUT_ROOT}/march_health_metrics.csv"
    cp "${OUTPUT_DIR}/march_gps_positions.csv" "${OUTPUT_ROOT}/march_gps_positions.csv"
    cp "${OUTPUT_DIR}/march_hr_zones.csv" "${OUTPUT_ROOT}/march_hr_zones.csv"
    cp "${OUTPUT_DIR}/march_temp_data.csv" "${OUTPUT_ROOT}/march_temp_data.csv"
fi

# --- 8. Database Loading ----------------------------------------------------

if [ "${SKIP_LOAD}" = false ]; then
    echo ""
    echo "--- Step 6: Load Data to Database ---"

    if [ -f "${ENV_FILE}" ]; then
        echo "Loading environment from: ${ENV_FILE}"
        # shellcheck source=/dev/null
        source "${ENV_FILE}"
    else
        echo "ERROR: Environment file not found: ${ENV_FILE}"
        echo "Cannot proceed with database loading."
        exit 1
    fi

    uv run scripts/data/load_march_data.py \
        --data-dir "${OUTPUT_ROOT}/" \
        --march-id "${MARCH_ID}" \
        --yes
fi

# --- 9. Completion ----------------------------------------------------------

echo ""
echo "==================================================================="
echo "  Processing Complete for March ID ${MARCH_ID} - ${DATE_YYYYMMDD}"
echo "==================================================================="
