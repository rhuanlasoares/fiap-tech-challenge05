#!/usr/bin/env bash
# ==============================================================================
# Health Check Script for FIAP Tech Challenge 05 Microservices
# Tests real external endpoints via GCP Load Balancer (Gateway API)
# ==============================================================================

set -u

# ANSI Color Codes
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

# Real External Health Routes Configuration: "Name|EndpointPath"
SERVICES=(
    "ngo-service|/ngo-service/health"
    "donation-service|/donation-service/health"
    "volunteer-service|/volunteer-service/health"
)

PROJECT_ID="${PROJECT_ID:-ces-igniteprogram}"
ADDRESS_NAME="gke-ip-lb"
SCHEME="https"
BASE_URL=""
TIMEOUT=10
INSECURE="-k"

usage() {
    echo -e "${BOLD}Usage:${RESET} $0 [OPTIONS]"
    echo ""
    echo -e "${BOLD}Options:${RESET}"
    echo "  -p, --project <ID>   GCP Project ID (default: ces-igniteprogram)"
    echo "  --http               Use http:// instead of https://"
    echo "  --https              Use https:// (default)"
    echo "  -u, --url <BASE_URL> Custom Base URL (e.g. https://solidary-tech.8.232.78.3.nip.io)"
    echo "  -t, --timeout <SEC>  Timeout in seconds for each request (default: 10)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo -e "${BOLD}Examples:${RESET}"
    echo "  $0                                   # Auto-fetch Load Balancer IP and test https://solidary-tech.<IP>.nip.io"
    echo "  $0 --http                            # Test via http://solidary-tech.<IP>.nip.io"
    echo "  $0 --project ces-igniteprogram"
    echo "  $0 --url https://my-domain.com"
    exit 0
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--project)
            PROJECT_ID="${2:-ces-igniteprogram}"
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
echo -e "${BOLD}${CYAN}   Microservices External Health Check Validator    ${RESET}"
echo -e "${BOLD}${CYAN}====================================================${RESET}"
echo -e "Target URL: ${YELLOW}${BASE_URL}${RESET}"
echo -e "Timeout: ${YELLOW}${TIMEOUT}s${RESET}"
echo -e "${CYAN}----------------------------------------------------${RESET}\n"

PASSED_COUNT=0
TOTAL_COUNT=${#SERVICES[@]}

for svc_item in "${SERVICES[@]}"; do
    IFS='|' read -r name path <<< "$svc_item"
    full_url="${BASE_URL%/}${path}"

    echo -ne "Testing ${BOLD}${name}${RESET} at ${CYAN}${full_url}${RESET}... "

    res=$(curl $INSECURE -s -m "$TIMEOUT" -w "\n%{http_code}" "$full_url" 2>/dev/null || echo "FAILED")

    if [[ "$res" == "FAILED" || -z "$res" ]]; then
        echo -e "${RED}[FAIL]${RESET} - Connection failed or timed out"
        continue
    fi

    body=$(echo "$res" | head -n -1)
    http_code=$(echo "$res" | tail -n 1)

    if [[ "$http_code" == "200" ]]; then
        echo -e "${GREEN}[OK]${RESET} (HTTP ${http_code}) - Body: ${body}"
        PASSED_COUNT=$((PASSED_COUNT + 1))
    else
        echo -e "${RED}[FAIL]${RESET} (HTTP ${http_code}) - Body: ${body}"
    fi
done

echo -e "\n${CYAN}----------------------------------------------------${RESET}"
if [[ "$PASSED_COUNT" -eq "$TOTAL_COUNT" ]]; then
    echo -e "${GREEN}${BOLD}Result: PASS (${PASSED_COUNT}/${TOTAL_COUNT} services healthy)${RESET}"
    exit 0
else
    echo -e "${RED}${BOLD}Result: FAIL (${PASSED_COUNT}/${TOTAL_COUNT} services healthy)${RESET}"
    exit 1
fi
