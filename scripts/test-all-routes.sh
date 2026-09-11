#!/usr/bin/env bash
# ==============================================================================
# Integration Test Script for FIAP Tech Challenge 05 Microservices
# Tests all REAL API endpoints via GCP Load Balancer (Gateway API)
# ==============================================================================

set -u

# ANSI Color Codes
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

PROJECT_ID="${PROJECT_ID:-naconfeitaria}"
ADDRESS_NAME="gke-ip-lb"
SCHEME="https"
BASE_URL=""
TIMEOUT=10
INSECURE="-k"

usage() {
    echo -e "${BOLD}Usage:${RESET} $0 [OPTIONS]"
    echo ""
    echo -e "${BOLD}Options:${RESET}"
    echo "  -p, --project <ID>   GCP Project ID (default: naconfeitaria)"
    echo "  --http               Use http:// instead of https://"
    echo "  --https              Use https:// (default)"
    echo "  -u, --url <BASE_URL> Custom Base URL (e.g. https://solidary-tech.8.232.78.3.nip.io)"
    echo "  -t, --timeout <SEC>  Timeout in seconds for each HTTP request (default: 10)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo -e "${BOLD}Examples:${RESET}"
    echo "  $0                                   # Auto-fetch Load Balancer IP and test all external routes"
    echo "  $0 --http                            # Test via http://solidary-tech.<IP>.nip.io"
    echo "  $0 --project naconfeitaria"
    echo "  $0 --url https://my-custom-domain.com"
    exit 0
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--project)
            PROJECT_ID="${2:-naconfeitaria}"
            shift 2
            ;;
        --http)
            SCHEME="http"
            shift
            ;;
        --https)
            SCHEME="https"
            shift
            ;;
        -u|--url)
            BASE_URL="${2:-}"
            if [[ -z "$BASE_URL" ]]; then
                echo -e "${RED}Error: --url requires a base URL argument.${RESET}"
                exit 1
            fi
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="${2:-10}"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${RESET}"
            usage
            ;;
    esac
done

# Resolve Base URL if not provided explicitly
if [[ -z "$BASE_URL" ]]; then
    echo -e "${CYAN}Fetching Load Balancer IP '${ADDRESS_NAME}' for project '${PROJECT_ID}'...${RESET}"
    GATEWAY_IP=$(gcloud compute addresses describe "$ADDRESS_NAME" --global --format='value(address)' --project "$PROJECT_ID" 2>/dev/null || echo "")

    if [[ -z "$GATEWAY_IP" ]]; then
        echo -e "${RED}Error: Could not retrieve IP address for Load Balancer '${ADDRESS_NAME}'.${RESET}"
        echo -e "${YELLOW}Ensure gcloud is authenticated and project ID is correct.${RESET}"
        exit 1
    fi

    echo -e "${GREEN}Load Balancer IP found: ${BOLD}${GATEWAY_IP}${RESET}"
    BASE_URL="${SCHEME}://solidary-tech.${GATEWAY_IP}.nip.io"
fi

echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "${BOLD}${CYAN}   Microservices Real API Endpoints Test            ${RESET}"
echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "Target Base URL: ${YELLOW}${BASE_URL}${RESET}"
echo -e "Timeout: ${YELLOW}${TIMEOUT}s${RESET}"
echo -e "${CYAN}----------------------------------------------------${RESET}\n"

PASSED_COUNT=0
TOTAL_COUNT=0

run_test() {
    local svc_name="$1"
    local method="$2"
    local path="$3"
    local expected_code="$4"
    local payload="${5:-}"

    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    local full_url="${BASE_URL%/}${path}"

    echo -ne "Testing [${BOLD}${svc_name}${RESET}] ${YELLOW}${method}${RESET} ${CYAN}${full_url}${RESET}... "

    local res=""
    if [[ "$method" == "GET" ]]; then
        res=$(curl $INSECURE -s -m "$TIMEOUT" -w "\n%{http_code}" "$full_url" 2>/dev/null || echo "FAILED")
    else
        res=$(curl $INSECURE -s -m "$TIMEOUT" -X "$method" -H "Content-Type: application/json" -d "$payload" -w "\n%{http_code}" "$full_url" 2>/dev/null || echo "FAILED")
    fi

    if [[ "$res" == "FAILED" || -z "$res" ]]; then
        echo -e "${RED}[FAIL]${RESET} - Connection failed or timed out"
        return 1
    fi

    local body
    body=$(echo "$res" | head -n -1)
    local http_code
    http_code=$(echo "$res" | tail -n 1)

    if [[ "$http_code" == "$expected_code" ]]; then
        echo -e "${GREEN}[OK]${RESET} (HTTP ${http_code}) - Response: ${body}"
        PASSED_COUNT=$((PASSED_COUNT + 1))
        return 0
    else
        echo -e "${RED}[FAIL]${RESET} (HTTP ${http_code}) - Response: ${body}"
        return 1
    fi
}

RAND_SUFFIX=$((RANDOM % 9000 + 1000))
NGO_EMAIL="ong${RAND_SUFFIX}@esperanca.org"
VOL_EMAIL="voluntario${RAND_SUFFIX}@exemplo.com"

# --- 1. NGO SERVICE ROUTES ---
echo -e "${BOLD}${CYAN}--- 1. ngo-service ---${RESET}"
run_test "ngo-service" "GET" "/ngo-service/health" "200" ""
run_test "ngo-service" "POST" "/ngo-service/ngos" "201" "{\"name\":\"ONG Esperanca ${RAND_SUFFIX}\",\"email\":\"${NGO_EMAIL}\",\"cause\":\"Educacao\",\"city\":\"Sao Paulo\"}"
run_test "ngo-service" "GET" "/ngo-service/ngos" "200" ""
echo ""

# --- 2. DONATION SERVICE ROUTES ---
echo -e "${BOLD}${CYAN}--- 2. donation-service ---${RESET}"
run_test "donation-service" "GET" "/donation-service/health" "200" ""
run_test "donation-service" "POST" "/donation-service/donations" "201" "{\"ngo_id\":1,\"amount\":150.75,\"donor_name\":\"Maria Silva ${RAND_SUFFIX}\"}"
run_test "donation-service" "GET" "/donation-service/donations" "200" ""
echo ""

# --- 3. VOLUNTEER SERVICE ROUTES ---
echo -e "${BOLD}${CYAN}--- 3. volunteer-service ---${RESET}"
run_test "volunteer-service" "GET" "/volunteer-service/health" "200" ""
run_test "volunteer-service" "POST" "/volunteer-service/volunteers" "201" "{\"name\":\"Carlos Santos ${RAND_SUFFIX}\",\"email\":\"${VOL_EMAIL}\",\"ngo_id\":1}"
run_test "volunteer-service" "GET" "/volunteer-service/volunteers/1" "200" ""
run_test "volunteer-service" "GET" "/volunteer-service/error" "500" ""
echo ""

echo -e "${CYAN}----------------------------------------------------${RESET}"
if [[ "$PASSED_COUNT" -eq "$TOTAL_COUNT" ]]; then
    echo -e "${GREEN}${BOLD}Summary: ALL PASS (${PASSED_COUNT}/${TOTAL_COUNT} external endpoints working)${RESET}"
    exit 0
else
    echo -e "${RED}${BOLD}Summary: FAIL (${PASSED_COUNT}/${TOTAL_COUNT} external endpoints working)${RESET}"
    exit 1
fi
