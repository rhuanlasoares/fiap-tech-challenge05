#!/usr/bin/env bash
# ==============================================================================
# Apache Benchmark (ab) Test Script for Microservice Endpoints
# FIAP Tech Challenge 05
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

# Default Configuration Values
PROJECT_ID="${PROJECT_ID:-ces-igniteprogram}"
ADDRESS_NAME="gke-ip-lb"
SCHEME="https"
BASE_URL=""
PATH_URL="/volunteer-service/health"
REQUESTS=1000
CONCURRENCY=50
METHOD="GET"
KEEP_ALIVE=true
PAYLOAD_DATA=""
PAYLOAD_FILE=""
EXTRA_HEADERS=()
TMP_PAYLOAD_FILE=""

cleanup() {
    if [[ -n "${TMP_PAYLOAD_FILE}" && -f "${TMP_PAYLOAD_FILE}" ]]; then
        rm -f "${TMP_PAYLOAD_FILE}"
    fi
}
trap cleanup EXIT

usage() {
    cat << EOF
${BOLD}Usage:${RESET} $0 [PATH] [REQUESTS] [CONCURRENCY] [OPTIONS]

${BOLD}Positional Arguments:${RESET}
  1. PATH          Endpoint path (default: /ngo-service/health)
  2. REQUESTS      Total number of requests (default: 1000)
  3. CONCURRENCY   Number of multiple concurrent requests (default: 50)

${BOLD}Options:${RESET}
  -p, --path <PATH>       Endpoint path (e.g. /donation-service/donations)
  -n, --requests <NUM>    Total number of requests (default: 1000)
  -c, --concurrency <NUM> Concurrent requests (default: 50)
  -m, --method <METHOD>   HTTP method: GET, POST, PUT, DELETE (default: GET)
  -d, --data <JSON>       JSON body data string for POST/PUT requests
  -f, --file <PATH>       Path to JSON payload file for POST/PUT requests
  -H, --header <HEADER>   Custom HTTP header (can be used multiple times)
  -u, --url <BASE_URL>    Custom Base URL (e.g. https://solidary-tech.34.111.65.194.nip.io)
  --no-keepalive          Disable HTTP Keep-Alive (-k)
  --http                  Use http:// scheme instead of https://
  -h, --help              Show this help message

${BOLD}Examples:${RESET}
  # Quick positional test on health endpoint
  $0 /ngo-service/health 500 20

  # Flag-based GET test on donation service
  $0 -p /donation-service/donations -n 1000 -c 50

  # POST request test with JSON payload
  $0 -p /ngo-service/ngos -m POST -d '{"name":"ONG Teste","email":"test@ong.org","city":"SP","cause":"Educação"}' -n 200 -c 10

EOF
    exit 0
}

# Parse Command Line Arguments
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            ;;
        -p|--path)
            PATH_URL="$2"
            shift 2
            ;;
        -n|--requests)
            REQUESTS="$2"
            shift 2
            ;;
        -c|--concurrency)
            CONCURRENCY="$2"
            shift 2
            ;;
        -m|--method)
            METHOD="$(echo "$2" | tr '[:lower:]' '[:upper:]')"
            shift 2
            ;;
        -d|--data)
            PAYLOAD_DATA="$2"
            shift 2
            ;;
        -f|--file)
            PAYLOAD_FILE="$2"
            shift 2
            ;;
        -H|--header)
            EXTRA_HEADERS+=("-H" "$2")
            shift 2
            ;;
        -u|--url)
            BASE_URL="$2"
            shift 2
            ;;
        --no-keepalive)
            KEEP_ALIVE=false
            shift
            ;;
        --http)
            SCHEME="http"
            shift
            ;;
        -*)
            echo -e "${RED}Error: Unknown option $1${RESET}" >&2
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Assign Positional Arguments if provided
if [[ ${#POSITIONAL_ARGS[@]} -ge 1 ]]; then
    PATH_URL="${POSITIONAL_ARGS[0]}"
fi
if [[ ${#POSITIONAL_ARGS[@]} -ge 2 ]]; then
    REQUESTS="${POSITIONAL_ARGS[1]}"
fi
if [[ ${#POSITIONAL_ARGS[@]} -ge 3 ]]; then
    CONCURRENCY="${POSITIONAL_ARGS[2]}"
fi

# Ensure path starts with /
if [[ "${PATH_URL}" != /* ]]; then
    PATH_URL="/${PATH_URL}"
fi

# Check if ab is installed
if ! command -v ab >/dev/null 2>&1; then
    echo -e "${RED}Error: Apache Benchmark ('ab') tool is not installed.${RESET}"
    echo -e "${YELLOW}Install it using: sudo apt-get update && sudo apt-get install -y apache2-utils${RESET}"
    exit 1
fi

# Auto-detect Load Balancer IP if Base URL is empty
if [[ -z "${BASE_URL}" ]]; then
    echo -e "${CYAN}Fetching Load Balancer IP '${ADDRESS_NAME}' for project '${PROJECT_ID}'...${RESET}"
    set +e
    LB_IP=$(gcloud compute addresses describe "${ADDRESS_NAME}" \
        --project="${PROJECT_ID}" \
        --global \
        --format='value(address)' 2>/dev/null)
    if [[ -z "${LB_IP}" ]]; then
        LB_IP=$(gcloud compute addresses describe "${ADDRESS_NAME}" \
            --project="${PROJECT_ID}" \
            --region="southamerica-east1" \
            --format='value(address)' 2>/dev/null)
    fi
    set -e

    if [[ -z "${LB_IP}" ]]; then
        echo -e "${RED}Error: Failed to obtain Load Balancer IP. Provide -u/--url explicitly.${RESET}" >&2
        exit 1
    fi
    echo -e "${GREEN}Load Balancer IP found: ${LB_IP}${RESET}"
    BASE_URL="${SCHEME}://solidary-tech.${LB_IP}.nip.io"
fi

FULL_URL="${BASE_URL%/}${PATH_URL}"

# Build Apache Benchmark options array
AB_CMD=("ab" "-n" "${REQUESTS}" "-c" "${CONCURRENCY}" "-l")

if [[ "${KEEP_ALIVE}" == true ]]; then
    AB_CMD+=("-k")
fi

# Handle POST/PUT payloads
if [[ "${METHOD}" == "POST" || "${METHOD}" == "PUT" ]]; then
    if [[ -n "${PAYLOAD_DATA}" ]]; then
        TMP_PAYLOAD_FILE=$(mktemp /tmp/ab_payload_XXXXXX.json)
        echo "${PAYLOAD_DATA}" > "${TMP_PAYLOAD_FILE}"
        BODY_FILE="${TMP_PAYLOAD_FILE}"
    elif [[ -n "${PAYLOAD_FILE}" ]]; then
        if [[ ! -f "${PAYLOAD_FILE}" ]]; then
            echo -e "${RED}Error: Payload file '${PAYLOAD_FILE}' not found.${RESET}" >&2
            exit 1
        fi
        BODY_FILE="${PAYLOAD_FILE}"
    else
        # Default fallback sample payload if none specified
        TMP_PAYLOAD_FILE=$(mktemp /tmp/ab_payload_XXXXXX.json)
        echo '{"name":"Benchmark Test","email":"bench@test.com"}' > "${TMP_PAYLOAD_FILE}"
        BODY_FILE="${TMP_PAYLOAD_FILE}"
    fi

    if [[ "${METHOD}" == "POST" ]]; then
        AB_CMD+=("-p" "${BODY_FILE}" "-T" "application/json")
    else
        AB_CMD+=("-u" "${BODY_FILE}" "-T" "application/json")
    fi
elif [[ "${METHOD}" != "GET" ]]; then
    AB_CMD+=("-m" "${METHOD}")
fi

# Add custom headers if any
if [[ ${#EXTRA_HEADERS[@]} -gt 0 ]]; then
    AB_CMD+=("${EXTRA_HEADERS[@]}")
fi

AB_CMD+=("${FULL_URL}")

echo -e "\n${BOLD}${CYAN}====================================================${RESET}"
echo -e "${BOLD}${CYAN}   Apache Benchmark Load Test                       ${RESET}"
echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "${BOLD}Target URL:${RESET}      ${FULL_URL}"
echo -e "${BOLD}Total Requests:${RESET}  ${REQUESTS}"
echo -e "${BOLD}Concurrency:${RESET}     ${CONCURRENCY}"
echo -e "${BOLD}HTTP Method:${RESET}     ${METHOD}"
echo -e "${BOLD}Keep-Alive:${RESET}      ${KEEP_ALIVE}"
echo -e "${CYAN}----------------------------------------------------${RESET}\n"

echo -e "${YELLOW}Executing Command:${RESET} ${AB_CMD[*]}\n"

# Run Apache Benchmark
"${AB_CMD[@]}"

echo -e "\n${GREEN}✔ Benchmark Completed Successfully!${RESET}"
