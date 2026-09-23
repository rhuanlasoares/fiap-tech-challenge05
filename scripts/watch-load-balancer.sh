#!/usr/bin/env bash
# ==============================================================================
# Continuous Health & Database Monitor via GCP Load Balancer
# FIAP Tech Challenge 05 — SolidaryTech
# ==============================================================================

set -u

# ANSI Color Codes
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

# Default Configurations
PROJECT_ID="${PROJECT_ID:-naconfeitaria}"
ADDRESS_NAME="gke-ip-lb"
SERVICE="donation-service"
INTERVAL=1
TIMEOUT=2
BASE_URL=""

usage() {
    cat << EOF
${BOLD}Usage:${RESET} $0 [OPTIONS]

${BOLD}Options:${RESET}
  -s, --service <NAME>   Service to test: 'donation', 'ngo', 'volunteer', or 'all' (default: donation)
  -p, --project <ID>     GCP Project ID (default: naconfeitaria)
  -i, --interval <SEC>   Interval in seconds between requests (default: 1)
  -t, --timeout <SEC>    Request timeout in seconds (default: 2)
  -u, --url <BASE_URL>   Custom Base URL (default: auto-detect from gke-ip-lb)
  -h, --help             Show this help message

${BOLD}Examples:${RESET}
  $0                                   # Monitor donation-service and PostgreSQL every 1s
  $0 -s ngo                            # Monitor ngo-service and PostgreSQL
  $0 -s volunteer                      # Monitor volunteer-service and DynamoDB
  $0 -s all -i 2                       # Monitor all 3 services every 2s
  $0 -u https://my-custom-domain.com   # Use explicit domain
EOF
    exit 0
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -u|--url)
            BASE_URL="$2"
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

# Normalize service name
case "$SERVICE" in
    donation|donation-service)
        SERVICE="donation-service"
        ;;
    ngo|ngo-service)
        SERVICE="ngo-service"
        ;;
    volunteer|volunteer-service)
        SERVICE="volunteer-service"
        ;;
    all)
        SERVICE="all"
        ;;
    *)
        echo -e "${RED}Serviço inválido: $SERVICE. Escolha entre: donation, ngo, volunteer ou all.${RESET}"
        exit 1
        ;;
esac

# Auto-detect Load Balancer IP if BASE_URL is not provided
if [[ -z "$BASE_URL" ]]; then
    echo -ne "${CYAN}Buscando IP do Load Balancer '${ADDRESS_NAME}' no projeto '${PROJECT_ID}'... ${RESET}"
    GATEWAY_IP=$(gcloud compute addresses describe "$ADDRESS_NAME" --global --format='value(address)' --project "$PROJECT_ID" 2>/dev/null || echo "")

    if [[ -z "$GATEWAY_IP" ]]; then
        echo -e "${RED}[FALHA]${RESET}"
        echo -e "${RED}Erro: Não foi possível obter o IP de '${ADDRESS_NAME}'. Verifique a autenticação do gcloud.${RESET}"
        exit 1
    fi

    echo -e "${GREEN}[OK: ${GATEWAY_IP}]${RESET}"
    BASE_URL="https://solidary-tech.${GATEWAY_IP}.nip.io"
fi

echo -e "\n${BOLD}${CYAN}========================================================================${RESET}"
echo -e "${BOLD}${CYAN}   Monitor Contínuo de Health & Banco via Load Balancer                ${RESET}"
echo -e "${BOLD}${CYAN}========================================================================${RESET}"
echo -e "URL Base:    ${YELLOW}${BASE_URL}${RESET}"
echo -e "Serviço(s):  ${YELLOW}${SERVICE}${RESET}"
echo -e "Intervalo:   ${YELLOW}${INTERVAL}s${RESET} (Timeout: ${TIMEOUT}s)"
echo -e "Pressione ${BOLD}Ctrl+C${RESET} para interromper.\n"

test_service() {
    local svc="$1"
    local health_path=""
    local db_path=""
    local db_type=""

    case "$svc" in
        donation-service)
            health_path="/donation-service/health"
            db_path="/donation-service/donations"
            db_type="PostgreSQL"
            ;;
        ngo-service)
            health_path="/ngo-service/health"
            db_path="/ngo-service/ngos"
            db_type="PostgreSQL"
            ;;
        volunteer-service)
            health_path="/volunteer-service/health"
            db_path="/volunteer-service/volunteers/1"
            db_type="DynamoDB"
            ;;
    esac

    local ts
    ts=$(date +"%H:%M:%S")

    # 1. Testar Health da Aplicação
    local app_res
    app_res=$(curl -k -s -o /dev/null -w "%{http_code}|%{time_total}" -m "$TIMEOUT" "${BASE_URL}${health_path}" 2>/dev/null || echo "ERR|0")
    local app_code="${app_res%%|*}"
    local app_time="${app_res##*|}"
    local app_ms=$(awk "BEGIN {printf \"%.0f\", $app_time * 1000}" 2>/dev/null || echo "0")

    # 2. Testar Conexão com o Banco de Dados (SELECT / Scan)
    local db_res
    db_res=$(curl -k -s -o /dev/null -w "%{http_code}|%{time_total}" -m "$TIMEOUT" "${BASE_URL}${db_path}" 2>/dev/null || echo "ERR|0")
    local db_code="${db_res%%|*}"
    local db_time="${db_res##*|}"
    local db_ms=$(awk "BEGIN {printf \"%.0f\", $db_time * 1000}" 2>/dev/null || echo "0")

    # Formatar App Status
    local app_status
    if [[ "$app_code" == "200" ]]; then
        app_status="${GREEN}OK (200 - ${app_ms}ms)${RESET}"
    elif [[ "$app_code" == "ERR" ]]; then
        app_status="${RED}TIMEOUT/OFFLINE${RESET}"
    else
        app_status="${RED}FALHA (${app_code} - ${app_ms}ms)${RESET}"
    fi

    # Formatar DB Status
    local db_status
    if [[ "$db_code" == "200" ]]; then
        db_status="${GREEN}UP (200 - ${db_ms}ms)${RESET}"
    elif [[ "$db_code" == "ERR" ]]; then
        db_status="${RED}TIMEOUT/OFFLINE${RESET}"
    else
        db_status="${RED}DOWN (${db_code} - ${db_ms}ms)${RESET}"
    fi

    printf "[%s] [%-17s] App: %-28b | Banco (%s): %-28b\n" "$ts" "$svc" "$app_status" "$db_type" "$db_status"
}

# Trap Ctrl+C
trap 'echo -e "\n${YELLOW}Monitoramento encerrado pelo usuário.${RESET}"; exit 0' SIGINT SIGTERM

# Main Loop
while true; do
    if [[ "$SERVICE" == "all" ]]; then
        test_service "donation-service"
        test_service "ngo-service"
        test_service "volunteer-service"
        echo -e "${CYAN}------------------------------------------------------------------------${RESET}"
    else
        test_service "$SERVICE"
    fi
    sleep "$INTERVAL"
done
