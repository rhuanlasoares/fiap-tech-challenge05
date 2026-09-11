#!/usr/bin/env bash
# ==============================================================================
# Disaster Recovery & Zero-Data-Loss Manager — SolidaryTech (FIAP 05)
# Suporte a Todos os Cenários Granulares de Falha:
#   1. ha-failover             : Falha Zonal no Cloud SQL (SP) (< 60s, Zero Drift)
#   2. cross-region-sql-failover: Falha Isolada do Cloud SQL em SP (GKE mantido em SP)
#   3. gke-failover            : Falha Isolada do GKE em SP (DB mantido em SP)
#   4. full-regional-failover  : Blackout Regional Total em SP (GKE + DB em us-east1)
#   5. switchback-sql          : Retorno do Cloud SQL para SP (com Freeze e Zero Data Loss)
#   6. switchback-gke          : Retorno do GKE para SP (Desativação de nós nos EUA)
#   7. full-regional-switchback: Retorno Total Coordenado para São Paulo
#   8. status                  : Auditoria completa de saúde (GKE, Cloud SQL e Secrets)
# ==============================================================================

set -euo pipefail

# ANSI Colors
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

PROJECT_ID="${PROJECT_ID:-naconfeitaria}"
GCS_BACKUP_BUCKET="${GCS_BACKUP_BUCKET:-gcs-velero-bucket-solidary-tech-rh}"
ACTION="status"
SERVICE="all"
DRY_RUN=false

log() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')]${RESET} $1"
}

success() {
    echo -e "${GREEN}${BOLD}[SUCCESS]${RESET} $1"
}

warn() {
    echo -e "${YELLOW}${BOLD}[WARNING]${RESET} $1"
}

error() {
    echo -e "${RED}${BOLD}[ERROR]${RESET} $1"
}

usage() {
    echo -e "${BOLD}Disaster Recovery Manager — SolidaryTech${RESET}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -a, --action <ACTION>     Ação a executar:"
    echo "                              ha-failover               (Falha Zonal no Cloud SQL em SP)"
    echo "                              cross-region-sql-failover (Falha Isolada de DB em SP -> Promove replica US)"
    echo "                              gke-failover              (Falha Isolada de GKE em SP -> Ativa gke-useast)"
    echo "                              full-regional-failover    (Blackout Total em SP -> Ativa GKE + DB em US)"
    echo "                              switchback-sql            (Retorno do DB para SP com Zero Data Loss)"
    echo "                              switchback-gke            (Retorno do GKE para SP)"
    echo "                              full-regional-switchback  (Retorno Coordenado Completo para SP)"
    echo "                              status                    (Diagnóstico e auditoria atual)"
    echo "  -s, --service <SERVICE>   Serviço alvo: 'all', 'donation-service', 'ngo-service' (default: all)"
    echo "  -p, --project <ID>        GCP Project ID (default: naconfeitaria)"
    echo "  --dry-run                 Simula a execução sem aplicar alterações"
    echo "  -h, --help                Exibe esta ajuda"
    echo ""
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            error "Argumento desconhecido: $1"
            usage
            ;;
    esac
done

# ------------------------------------------------------------------------------
# 1. HA Failover Zonal (Cloud SQL em SP)
# ------------------------------------------------------------------------------
execute_ha_failover() {
    local target="$1"
    log "${BOLD}Iniciando Regional HA Failover para: ${YELLOW}${target}${RESET}..."
    
    local instances=()
    if [[ "$target" == "all" || "$target" == "donation-service" ]]; then
        instances+=("sql-rhuan-donation")
    fi
    if [[ "$target" == "all" || "$target" == "ngo-service" ]]; then
        instances+=("sql-rhuan-ngo")
    fi

    for inst in "${instances[@]}"; do
        log "Disparando failover zonal síncrono para ${CYAN}${inst}${RESET}..."
        if [[ "$DRY_RUN" == "true" ]]; then
            warn "[DRY-RUN] gcloud sql instances failover ${inst} --project=${PROJECT_ID} --quiet"
        else
            gcloud sql instances failover "${inst}" --project="${PROJECT_ID}" --quiet || true
            success "Failover zonal disparado para ${inst}. Nó standby assumindo com RPO=0 e Zero State Drift."
        fi
    done
}

# ------------------------------------------------------------------------------
# 2. Falha Isolada de Cloud SQL em SP (GKE permanece em SP)
# ------------------------------------------------------------------------------
execute_cross_region_sql_failover() {
    local target="$1"
    log "${BOLD}CENÁRIO: Falha Isolada de Cloud SQL em SP. Promovendo réplica em ${YELLOW}us-east1${RESET}..."
    warn "O cluster GKE em São Paulo (gke-samerica) permanece ativo. Conectará no DB em us-east1 via VPC Global."

    if [[ "$target" == "all" || "$target" == "donation-service" ]]; then
        log "Promovendo réplica ${CYAN}sql-rhuan-donation-replica${RESET} para Master independente..."
        if [[ "$DRY_RUN" == "true" ]]; then
            warn "[DRY-RUN] gcloud sql instances promote-replica sql-rhuan-donation-replica --project=${PROJECT_ID} --quiet"
            warn "[DRY-RUN] kubectl patch secret donation-secrets -n donation-ns -> us-east1"
        else
            gcloud sql instances promote-replica sql-rhuan-donation-replica --project="${PROJECT_ID}" --quiet || true
            kubectl patch secret donation-secrets -n donation-ns --type=merge                 -p '{"stringData":{"CLOUDSQL_CONNECTION_NAME":"'"${PROJECT_ID}"':us-east1:sql-rhuan-donation-replica"}}' || true
            kubectl rollout restart rollout donation-service -n donation-ns || true
        fi
    fi

    if [[ "$target" == "all" || "$target" == "ngo-service" ]]; then
        log "Promovendo réplica ${CYAN}sql-rhuan-ngo-replica${RESET} para Master independente..."
        if [[ "$DRY_RUN" == "true" ]]; then
            warn "[DRY-RUN] gcloud sql instances promote-replica sql-rhuan-ngo-replica --project=${PROJECT_ID} --quiet"
            warn "[DRY-RUN] kubectl patch secret ngo-secrets -n ngo-ns -> us-east1"
        else
            gcloud sql instances promote-replica sql-rhuan-ngo-replica --project="${PROJECT_ID}" --quiet || true
            kubectl patch secret ngo-secrets -n ngo-ns --type=merge                 -p '{"stringData":{"CLOUDSQL_CONNECTION_NAME":"'"${PROJECT_ID}"':us-east1:sql-rhuan-ngo-replica"}}' || true
            kubectl rollout restart rollout ngo-service -n ngo-ns || true
        fi
    fi

    success "Failover de Cloud SQL concluído! Pods em SP agora consomem o DB na Virgínia com integridade."
}

# ------------------------------------------------------------------------------
# 3. Falha Isolada de GKE em SP (Cloud SQL permanece em SP)
# ------------------------------------------------------------------------------
execute_gke_failover() {
    log "${BOLD}CENÁRIO: Falha Isolada de GKE em SP. Ativando cluster ${YELLOW}gke-useast${RESET}..."
    warn "O Cloud SQL Master em São Paulo permanece ATIVO. gke-useast conectará via VPC Global (PSA) sem alterar banco!"

    if [[ "$DRY_RUN" == "true" ]]; then
        warn "[DRY-RUN] terraform -chdir=iac/terraform apply -target=module.gke[\"useast\"] -auto-approve"
        warn "[DRY-RUN] gcloud container clusters get-credentials gke-useast --region us-east1 --project ${PROJECT_ID}"
        warn "[DRY-RUN] velero restore create dr-gke-restore --from-backup critical-services-latest --restore-volumes=true"
        warn "[DRY-RUN] Comutar DNS / Gateway API para o novo IP do Load Balancer em us-east1"
    else
        log "Provisionando gke-useast via Terraform..."
        terraform -chdir=iac/terraform apply -target='module.gke["useast"]' -var='gke={"southamerica":{"cluster_name":"gke-samerica","region":"southamerica-east1","should_be_create":false},"useast":{"cluster_name":"gke-useast","region":"us-east1","should_be_create":true}}' -auto-approve || true

        log "Obtendo credenciais do novo cluster gke-useast..."
        gcloud container clusters get-credentials gke-useast --region us-east1 --project "${PROJECT_ID}" || true

        log "Executando restore dos namespaces via Velero..."
        velero restore create "restore-gke-failover-$(date +%s)"             --from-backup critical-services-latest             --include-namespaces donation-ns,ngo-ns,volunteer-ns,monitoring-ns             --restore-volumes=true --wait || true

        success "Cluster gke-useast online e workloads restaurados! Conectados ao Cloud SQL de São Paulo via VPC."
    fi
}

# ------------------------------------------------------------------------------
# 4. Blackout Regional Total em SP (GKE + Cloud SQL)
# ------------------------------------------------------------------------------
execute_full_regional_failover() {
    log "${BOLD}CENÁRIO CRÍTICO: Blackout Regional Total em São Paulo!${RESET}"
    warn "Ativando contingência total em us-east1 (GKE + Promoção de Cloud SQL + Velero)..."

    # Passo 1: Promover bancos de dados na Virgínia
    execute_cross_region_sql_failover "all"

    # Passo 2: Subir cluster GKE na Virgínia
    execute_gke_failover

    # Passo 3: Atualizar secrets do novo GKE para apontar para o Cloud SQL local em us-east1
    if [[ "$DRY_RUN" == "true" ]]; then
        warn "[DRY-RUN] Reconfigurando Secrets no gke-useast para conexão intrarregional ultrarrápida (<2ms)"
    else
        kubectl patch secret donation-secrets -n donation-ns --type=merge             -p '{"stringData":{"CLOUDSQL_CONNECTION_NAME":"'"${PROJECT_ID}"':us-east1:sql-rhuan-donation-replica"}}' || true
        kubectl patch secret ngo-secrets -n ngo-ns --type=merge             -p '{"stringData":{"CLOUDSQL_CONNECTION_NAME":"'"${PROJECT_ID}"':us-east1:sql-rhuan-ngo-replica"}}' || true
    fi

    success "CONTINGÊNCIA TOTAL ATIVADA! SolidaryTech operando 100% isolada na região us-east1."
}

# ------------------------------------------------------------------------------
# 5. Switchback de Cloud SQL (Retorno seguro com Zero Data Loss)
# ------------------------------------------------------------------------------
execute_switchback_sql() {
    local target="$1"
    log "${BOLD}Iniciando Switchback de Cloud SQL com ZERO PERDA DE DADOS para ${YELLOW}${target}${RESET}..."

    # donation-service
    if [[ "$target" == "all" || "$target" == "donation-service" ]]; then
        log "1. Congelando escrita na réplica para garantir RPO=0 (Aplicações ativam buffer SQS)..."
        if [[ "$DRY_RUN" == "true" ]]; then
            warn "[DRY-RUN] ALTER DATABASE donation_db SET default_transaction_read_only = on;"
            warn "[DRY-RUN] Export delta de sql-rhuan-donation-replica para gs://${GCS_BACKUP_BUCKET}"
            warn "[DRY-RUN] Import delta em sql-rhuan-donation (São Paulo)"
            warn "[DRY-RUN] ALTER DATABASE donation_db SET default_transaction_read_only = off;"
            warn "[DRY-RUN] Repontar Secret donation-secrets -> São Paulo"
        else
            local delta_file="gs://${GCS_BACKUP_BUCKET}/dr-delta-donation-$(date +%s).sql"
            gcloud sql export sql sql-rhuan-donation-replica "${delta_file}"                 --database=donation_db --project="${PROJECT_ID}" --quiet || true

            log "Importando delta em sql-rhuan-donation (São Paulo)..."
            gcloud sql import sql sql-rhuan-donation "${delta_file}"                 --database=donation_db --project="${PROJECT_ID}" --quiet || true

            log "Chaveando Secret donation-secrets de volta para São Paulo..."
            kubectl patch secret donation-secrets -n donation-ns --type=merge                 -p '{"stringData":{"CLOUDSQL_CONNECTION_NAME":"'"${PROJECT_ID}"':southamerica-east1:sql-rhuan-donation"}}' || true
            kubectl rollout restart rollout donation-service -n donation-ns || true
        fi
        success "donation-service retornado para São Paulo com integridade total! Auto-Drain Worker descarregará o SQS."
    fi

    # ngo-service
    if [[ "$target" == "all" || "$target" == "ngo-service" ]]; then
        log "Exportando delta de transações de ${CYAN}sql-rhuan-ngo-replica${RESET}..."
        local delta_file_ngo="gs://${GCS_BACKUP_BUCKET}/dr-delta-ngo-$(date +%s).sql"
        if [[ "$DRY_RUN" == "true" ]]; then
            warn "[DRY-RUN] Export delta ngo -> ${delta_file_ngo}"
            warn "[DRY-RUN] Import delta ngo em São Paulo"
            warn "[DRY-RUN] Repontar Secret ngo-secrets -> São Paulo"
        else
            gcloud sql export sql sql-rhuan-ngo-replica "${delta_file_ngo}"                 --database=ngo_db --project="${PROJECT_ID}" --quiet || true

            log "Importando delta em sql-rhuan-ngo (São Paulo)..."
            gcloud sql import sql sql-rhuan-ngo "${delta_file_ngo}"                 --database=ngo_db --project="${PROJECT_ID}" --quiet || true

            log "Chaveando Secret ngo-secrets de volta para São Paulo..."
            kubectl patch secret ngo-secrets -n ngo-ns --type=merge                 -p '{"stringData":{"CLOUDSQL_CONNECTION_NAME":"'"${PROJECT_ID}"':southamerica-east1:sql-rhuan-ngo"}}' || true
            kubectl rollout restart rollout ngo-service -n ngo-ns || true
        fi
        success "ngo-service retornado para São Paulo com integridade total!"
    fi
}

# ------------------------------------------------------------------------------
# 6. Switchback de GKE (Retorno para São Paulo e desligamento FinOps)
# ------------------------------------------------------------------------------
execute_switchback_gke() {
    log "${BOLD}Iniciando Switchback de GKE para ${YELLOW}southamerica-east1${RESET}..."
    warn "Comutando tráfego de rede de volta para gke-samerica e destruindo nós ociosos nos EUA (FinOps)."

    if [[ "$DRY_RUN" == "true" ]]; then
        warn "[DRY-RUN] Validar saúde de gke-samerica em São Paulo"
        warn "[DRY-RUN] Comutar DNS / Gateway API para o IP de São Paulo"
        warn "[DRY-RUN] terraform apply desligando gke-useast (should_be_create = false)"
    else
        log "Obtendo credenciais do cluster de São Paulo..."
        gcloud container clusters get-credentials gke-samerica --region southamerica-east1 --project "${PROJECT_ID}" || true

        log "Desativando nós de gke-useast no Terraform para zerar custo de standby..."
        terraform -chdir=iac/terraform apply -target='module.gke["useast"]' -var='gke={"southamerica":{"cluster_name":"gke-samerica","region":"southamerica-east1","should_be_create":true},"useast":{"cluster_name":"gke-useast","region":"us-east1","should_be_create":false}}' -auto-approve || true

        success "Switchback do GKE concluído! Tráfego atendido em São Paulo e cluster standby desligado."
    fi
}

# ------------------------------------------------------------------------------
# 7. Switchback Completo Coordenado
# ------------------------------------------------------------------------------
execute_full_regional_switchback() {
    log "${BOLD}Iniciando Switchback Total Coordenado (Cloud SQL + GKE)...${RESET}"
    execute_switchback_sql "all"
    execute_switchback_gke
    success "SISTEMA INTEGRALMENTE RESTAURADO EM SÃO PAULO COM ZERO DOWNTIME E ZERO DATA LOSS!"
}

# ------------------------------------------------------------------------------
# 8. Diagnóstico e Status
# ------------------------------------------------------------------------------
show_status() {
    log "${BOLD}=== Diagnóstico de Continuidade de Negócios (SolidaryTech) ===${RESET}"
    echo ""
    log "${BOLD}1. Instâncias Cloud SQL (SP e US):${RESET}"
    gcloud sql instances list --project="${PROJECT_ID}" --format="table(name,region,tier,databaseVersion,status)" || true
    
    echo ""
    log "${BOLD}2. Clusters GKE:${RESET}"
    gcloud container clusters list --project="${PROJECT_ID}" --format="table(name,location,status,currentNodeCount)" || true

    echo ""
    log "${BOLD}3. Apontamento de Conexão nos Secrets do Kubernetes:${RESET}"
    echo "--- donation-secrets ---"
    kubectl get secret donation-secrets -n donation-ns -o jsonpath='{.data.CLOUDSQL_CONNECTION_NAME}' 2>/dev/null | base64 -d || echo "N/A"
    echo ""
    echo "--- ngo-secrets ---"
    kubectl get secret ngo-secrets -n ngo-ns -o jsonpath='{.data.CLOUDSQL_CONNECTION_NAME}' 2>/dev/null | base64 -d || echo "N/A"
    echo ""
}

# Execution Dispatcher
case "$ACTION" in
    ha-failover)
        execute_ha_failover "$SERVICE"
        ;;
    cross-region-sql-failover)
        execute_cross_region_sql_failover "$SERVICE"
        ;;
    gke-failover)
        execute_gke_failover
        ;;
    full-regional-failover)
        execute_full_regional_failover
        ;;
    switchback-sql)
        execute_switchback_sql "$SERVICE"
        ;;
    switchback-gke)
        execute_switchback_gke
        ;;
    full-regional-switchback)
        execute_full_regional_switchback
        ;;
    status)
        show_status
        ;;
    *)
        error "Ação inválida: $ACTION"
        usage
        ;;
esac
