#!/usr/bin/env bash
# ==============================================================================
# Disaster Recovery Loop Test Script for FIAP Tech Challenge 05
# Continuously tests microservices and their databases (Cloud SQL / DynamoDB)
# ==============================================================================

set -u

# ANSI Color Codes
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

PROJECT_ID="${PROJECT_ID:-ces-igniteprogram}"
ADDRESS_NAME="gke-ip-lb"
SCHEME="https"
BASE_URL=""
SERVICE="volunteer-service"
INTERVAL=1
TIMEOUT=5
INSECURE="-k"
LOG_FILE=""

usage() {
    echo -e "${BOLD}Usage:${RESET} $0 [OPTIONS]"
    echo ""
    echo -e "${BOLD}Options:${RESET}"
    echo "  -s, --service <NAME> Service to test: 'donation-service', 'ngo-service' or 'volunteer-service' (default: volunteer-service)"
    echo "  -i, --interval <SEC> Loop sleep interval in seconds (default: 1)"
    echo "  -t, --timeout <SEC>  HTTP request timeout in seconds (default: 5)"
    echo "  -p, --project <ID>   GCP Project ID (default: ces-igniteprogram)"
    echo "  --http               Use http:// instead of https://"
    echo "  --https              Use https:// (default)"
    echo "  -u, --url <BASE_URL> Custom Base URL (e.g. https://solidary-tech.8.232.78.3.nip.io)"
    echo "  -l, --log <FILE>     Save log output to specified file"
    echo "  -h, --help           Show this help message"
    echo ""
    echo -e "${BOLD}Examples:${RESET}"
    echo "  $0                                            # Loop test volunteer-service every 1s"
    echo "  $0 --service ngo-service --interval 2         # Loop test ngo-service (Cloud SQL) every 2s"
    echo "  $0 --service donation-service --interval 1    # Loop test donation-service (Cloud SQL) every 1s"
    echo "  $0 --http --log dr-test-results.log           # Loop test over HTTP and save logs"
    exit 0
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--service)
            SERVICE="${2:-volunteer-service}"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="${2:-1}"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="${2:-5}"
            shift 2
            ;;
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
        -l|--log)
            LOG_FILE="${2:-}"
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

# Map Service to Database Type and Routes
HEALTH_PATH=""
DB_PATH=""
DB_TYPE=""

case "$SERVICE" in
    donation-service)
        HEALTH_PATH="/donation-service/health"
        DB_PATH="/donation-service/donations"
        DB_TYPE="CloudSQL"
        ;;
    ngo-service)
        HEALTH_PATH="/ngo-service/health"
        DB_PATH="/ngo-service/ngos"
        DB_TYPE="CloudSQL"
        ;;
    volunteer-service)
        HEALTH_PATH="/volunteer-service/health"
        DB_PATH="/volunteer-service/volunteers/1"
        DB_TYPE="DynamoDB"
        ;;
    *)
        echo -e "${RED}Error: Invalid service '$SERVICE'. Supported: donation-service, ngo-service, volunteer-service${RESET}"
        exit 1
        ;;
esac

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

HEALTH_URL="${BASE_URL%/}${HEALTH_PATH}"
DB_URL="${BASE_URL%/}${DB_PATH}"

# Tracking Metrics
ITERATION=0
TOTAL_REQS=0
SUCCESS_REQS=0
FAIL_REQS=0
START_TIME=$(date +%s)
DOWNTIME_START=0
TOTAL_DOWNTIME=0

log_msg() {
    local msg="$1"
    echo -e "$msg"
    if [[ -n "$LOG_FILE" ]]; then
        echo -e "$msg" | sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE"
    fi
}

cleanup() {
    local END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))

    log_msg "\n\n${BOLD}${CYAN}====================================================${RESET}"
    log_msg "${BOLD}${CYAN}       Disaster Recovery Test Summary              ${RESET}"
    log_msg "${BOLD}${CYAN}====================================================${RESET}"
    log_msg "Target Service:      ${YELLOW}${SERVICE}${RESET}"
    log_msg "Database Backend:    ${YELLOW}${DB_TYPE}${RESET}"
    log_msg "Total Duration:      ${YELLOW}${DURATION}s${RESET}"
    log_msg "Total Requests:      ${YELLOW}${TOTAL_REQS}${RESET}"
    log_msg "Successful (2xx):    ${GREEN}${SUCCESS_REQS}${RESET}"
    log_msg "Failed (5xx/Timeout): ${RED}${FAIL_REQS}${RESET}"
    if [[ "$TOTAL_DOWNTIME" -gt 0 ]]; then
        log_msg "Total Downtime:      ${RED}${TOTAL_DOWNTIME}s${RESET}"
    fi
    log_msg "${CYAN}----------------------------------------------------${RESET}"
    exit 0
}

# Trap Ctrl+C (SIGINT) and exit nicely
trap cleanup SIGINT SIGTERM

log_msg "${BOLD}${CYAN}====================================================${RESET}"
log_msg "${BOLD}${CYAN}   Disaster Recovery Continuous Health Loop Test    ${RESET}"
log_msg "${BOLD}${CYAN}====================================================${RESET}"
log_msg "Target Service:  ${YELLOW}${SERVICE}${RESET}"
log_msg "Database Engine: ${YELLOW}${DB_TYPE}${RESET}"
log_msg "Health Route:    ${CYAN}${HEALTH_URL}${RESET}"
log_msg "Database Route:  ${CYAN}${DB_URL}${RESET}"
log_msg "Loop Interval:   ${YELLOW}${INTERVAL}s${RESET}"
log_msg "Press ${BOLD}Ctrl+C${RESET} at any time to stop and view DR summary.\n"
log_msg "${CYAN}----------------------------------------------------${RESET}"

while true; do
    ITERATION=$((ITERATION + 1))
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

    # 1. Test Health Endpoint
    HEALTH_RES=$(curl $INSECURE -s -m "$TIMEOUT" -w "\n%{http_code}\n%{time_total}" "$HEALTH_URL" 2>/dev/null || echo "FAILED")

    HEALTH_STATUS="FAIL"
    HEALTH_CODE="000"
    HEALTH_TIME="0"
    if [[ "$HEALTH_RES" != "FAILED" && -n "$HEALTH_RES" ]]; then
        HEALTH_CODE=$(echo "$HEALTH_RES" | tail -n 2 | head -n 1)
        HEALTH_TIME=$(echo "$HEALTH_RES" | tail -n 1)
        HEALTH_TIME_MS=$(awk "BEGIN {print int($HEALTH_TIME * 1000)}")
    else
        HEALTH_TIME_MS="0"
    fi

    # 2. Test Database Route (Cloud SQL ou DynamoDB)
    DB_RES=$(curl $INSECURE -s -m "$TIMEOUT" -w "\n%{http_code}\n%{time_total}" "$DB_URL" 2>/dev/null || echo "FAILED")

    DB_STATUS="FAIL"
    DB_CODE="000"
    DB_TIME="0"
    if [[ "$DB_RES" != "FAILED" && -n "$DB_RES" ]]; then
        DB_CODE=$(echo "$DB_RES" | tail -n 2 | head -n 1)
        DB_TIME=$(echo "$DB_RES" | tail -n 1)
        DB_TIME_MS=$(awk "BEGIN {print int($DB_TIME * 1000)}")
    else
        DB_TIME_MS="0"
    fi

    TOTAL_REQS=$((TOTAL_REQS + 1))

    # Format Health Output
    if [[ "$HEALTH_CODE" == "200" ]]; then
        H_STR="${GREEN}Health: 200 OK (${HEALTH_TIME_MS}ms)${RESET}"
    else
        H_STR="${RED}Health: ${HEALTH_CODE} (${HEALTH_TIME_MS}ms)${RESET}"
    fi

    # Format Database Output
    if [[ "$DB_CODE" == "200" || "$DB_CODE" == "201" ]]; then
        DB_STR="${GREEN}${DB_TYPE}: ${DB_CODE} OK (${DB_TIME_MS}ms)${RESET}"
        SUCCESS_REQS=$((SUCCESS_REQS + 1))

        if [[ "$DOWNTIME_START" -ne 0 ]]; then
            NOW=$(date +%s)
            INC_DOWNTIME=$((NOW - DOWNTIME_START))
            TOTAL_DOWNTIME=$((TOTAL_DOWNTIME + INC_DOWNTIME))
            log_msg "${GREEN}${BOLD}>>> RECOVERY DETECTED after ${INC_DOWNTIME}s of downtime! <<<${RESET}"
            DOWNTIME_START=0
        fi
    else
        DB_STR="${RED}${DB_TYPE}: ${DB_CODE} FAIL (${DB_TIME_MS}ms)${RESET}"
        FAIL_REQS=$((FAIL_REQS + 1))

        if [[ "$DOWNTIME_START" -eq 0 ]]; then
            DOWNTIME_START=$(date +%s)
            log_msg "${RED}${BOLD}>>> OUTAGE DETECTED! Microservice DB (${DB_TYPE}) connection lost at ${TIMESTAMP} <<<${RESET}"
        fi
    fi

    log_msg "[${TIMESTAMP}] #${ITERATION} | ${H_STR} | ${DB_STR}"

    sleep "$INTERVAL"
done