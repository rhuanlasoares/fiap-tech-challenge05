#!/usr/bin/env bash
# ==============================================================================
# Drain Pod Node — FIAP Tech Challenge 05 (SolidaryTech)
# ==============================================================================
# Identifica o nó onde um pod específico está alocado e executa o drain seguro
# desse nó no Kubernetes (GKE).
# ==============================================================================

set -eo pipefail

# Cores para saída no terminal
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

# Valores padrão
POD_NAME=""
NAMESPACE=""
LABEL_SELECTOR=""
FORCE=true
IGNORE_DAEMONSETS=true
DELETE_EMPTYDIR=true
GRACE_PERIOD=60
DRY_RUN=false
AUTO_CONFIRM=false

usage() {
    echo -e "${BOLD}Uso:${RESET} $0 [OPÇÕES]"
    echo ""
    echo -e "${BOLD}Opções:${RESET}"
    echo -e "  -p, --pod <NOME>          Nome exato do pod"
    echo -e "  -n, --namespace <NS>      Namespace do pod (se omitido, busca em todos os namespaces)"
    echo -e "  -l, --label <KEY=VALUE>   Seletor por label (ex: app=donation-service)"
    echo -e "  -g, --grace-period <SEC>  Período de tolerância para encerramento dos pods (padrão: 60)"
    echo -e "  -d, --dry-run             Apenas simula e exibe o nó, sem executar o drain"
    echo -e "  -y, --yes                 Confirma automaticamente o drain sem prompt interativo"
    echo -e "  -h, --help                Exibe esta mensagem de ajuda"
    echo ""
    echo -e "${BOLD}Exemplos:${RESET}"
    echo -e "  $0 -p donation-service-976b7db58-r5n8w -n donation-ns"
    echo -e "  $0 -l app=donation-service -n donation-ns"
    echo -e "  $0 -l app=volunteer-service -n volunteer-ns --dry-run"
    echo -e "  $0 -p loki-backend-0 -n monitoring-ns -y"
    exit 0
}

# Tratamento de parâmetros
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--pod)
            POD_NAME="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -l|--label)
            LABEL_SELECTOR="$2"
            shift 2
            ;;
        -g|--grace-period)
            GRACE_PERIOD="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -y|--yes)
            AUTO_CONFIRM=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Opção inválida: $1${RESET}"
            usage
            ;;
    esac
done

# Validação inicial de argumentos
if [[ -z "$POD_NAME" && -z "$LABEL_SELECTOR" ]]; then
    echo -e "${RED}Erro: Você deve especificar o nome do pod (-p/--pod) ou um seletor de label (-l/--label).${RESET}\n"
    usage
fi

echo -e "\n${BOLD}${CYAN}========================================================================${RESET}"
echo -e "${BOLD}${CYAN}   Drain do Nó por Pod Alocado — Kubernetes / GKE                      ${RESET}"
echo -e "${BOLD}${CYAN}========================================================================${RESET}\n"

# 1. Localizar o Pod caso tenha sido passado por label selector
if [[ -n "$LABEL_SELECTOR" ]]; then
    echo -e "${CYAN}🔍 Buscando pod com a label '${LABEL_SELECTOR}'...${RESET}"
    NS_ARG=""
    [[ -n "$NAMESPACE" ]] && NS_ARG="-n $NAMESPACE" || NS_ARG="-A"

    FOUND_INFO=$(kubectl get pods $NS_ARG -l "$LABEL_SELECTOR" -o jsonpath='{range .items[0]}{.metadata.name}{" "}{.metadata.namespace}{end}' 2>/dev/null || true)
    
    if [[ -z "$FOUND_INFO" ]]; then
        echo -e "${RED}❌ Nenhum pod encontrado com a label '${LABEL_SELECTOR}'.${RESET}"
        exit 1
    fi

    POD_NAME=$(echo "$FOUND_INFO" | awk '{print $1}')
    NAMESPACE=$(echo "$FOUND_INFO" | awk '{print $2}')
    echo -e "${GREEN}✓ Pod selecionado:${RESET} ${BOLD}${POD_NAME}${RESET} (Namespace: ${YELLOW}${NAMESPACE}${RESET})"
fi

# 2. Localizar o Namespace se não tiver sido informado
if [[ -z "$NAMESPACE" ]]; then
    echo -e "${CYAN}🔍 Buscando namespace do pod '${POD_NAME}'...${RESET}"
    NAMESPACE=$(kubectl get pods -A -o jsonpath='{range .items[?(@.metadata.name=="'"$POD_NAME"'")]}{.metadata.namespace}{end}' 2>/dev/null || true)

    if [[ -z "$NAMESPACE" ]]; then
        echo -e "${RED}❌ Pod '${POD_NAME}' não encontrado em nenhum namespace.${RESET}"
        exit 1
    fi
    echo -e "${GREEN}✓ Namespace encontrado:${RESET} ${YELLOW}${NAMESPACE}${RESET}"
fi

# 3. Obter o Node onde o Pod está alocado
echo -e "${CYAN}🔍 Identificando o nó do pod '${POD_NAME}' em '${NAMESPACE}'...${RESET}"
NODE_NAME=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.nodeName}' 2>/dev/null || true)

if [[ -z "$NODE_NAME" || "$NODE_NAME" == "<none>" ]]; then
    echo -e "${RED}❌ Não foi possível identificar o nó do pod '${POD_NAME}'. O pod pode estar em estado Pending ou não existir.${RESET}"
    exit 1
fi

echo -e "${GREEN}✓ Nó identificado:${RESET} ${BOLD}${YELLOW}${NODE_NAME}${RESET}\n"

# 4. Obter detalhes do nó
NODE_STATUS=$(kubectl get node "$NODE_NAME" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
NODE_ZONE=$(kubectl get node "$NODE_NAME" -o jsonpath='{.metadata.labels.topology\.kubernetes\.io/zone}' 2>/dev/null || echo "Unknown")
POD_COUNT=$(kubectl get pods -A --field-selector spec.nodeName="$NODE_NAME" --no-headers 2>/dev/null | wc -l || echo "0")

echo -e "${BOLD}Resumo do Alvo:${RESET}"
echo -e "  • ${BOLD}Pod:${RESET}         $POD_NAME ($NAMESPACE)"
echo -e "  • ${BOLD}Nó Alvo:${RESET}     $NODE_NAME"
echo -e "  • ${BOLD}Status do Nó:${RESET} Ready=$NODE_STATUS"
echo -e "  • ${BOLD}Zona GCP:${RESET}    $NODE_ZONE"
echo -e "  • ${BOLD}Pods no Nó:${RESET}  $POD_COUNT pod(s) alocado(s)\n"

# 5. Modo Dry-Run
if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}⚠️  MODO DRY-RUN ATIVADO: O nó não será drenado.${RESET}"
    echo -e "Comando que seria executado:"
    echo -e "  ${BOLD}kubectl drain \"$NODE_NAME\" --ignore-daemonsets --delete-emptydir-data --force --grace-period=$GRACE_PERIOD${RESET}\n"
    exit 0
fi

# 6. Confirmação do Usuário
if [[ "$AUTO_CONFIRM" != true ]]; then
    echo -e "${YELLOW}⚠️  ATENÇÃO: O comando 'drain' isolará o nó (cordon) e despejará (evict) todos os pods elegíveis.${RESET}"
    read -r -p "Deseja continuar com o drain do nó '${NODE_NAME}'? [s/N]: " CONFIRM
    case "$CONFIRM" in
        [sS][iI][mM]|[sS]|[yY][eE][sS]|[yY])
            echo ""
            ;;
        *)
            echo -e "\n${RED}Operação cancelada pelo usuário.${RESET}"
            exit 0
            ;;
    esac
fi

# 7. Executar o Drain
echo -e "${BOLD}${CYAN}🚀 Executando drain no nó '${NODE_NAME}'...${RESET}"
DRAIN_CMD=(kubectl drain "$NODE_NAME" --ignore-daemonsets="$IGNORE_DAEMONSETS" --delete-emptydir-data="$DELETE_EMPTYDIR" --force="$FORCE" --grace-period="$GRACE_PERIOD")

echo -e "${CYAN}Comando:${RESET} ${DRAIN_CMD[*]}\n"

if "${DRAIN_CMD[@]}"; then
    echo -e "\n${GREEN}✅ Drain do nó '${NODE_NAME}' concluído com sucesso!${RESET}\n"
    echo -e "${BOLD}Para reativar o nó (permitir novos pods), execute:${RESET}"
    echo -e "  ${YELLOW}kubectl uncordon \"$NODE_NAME\"${RESET}\n"
else
    echo -e "\n${RED}❌ Erro durante o drain do nó '${NODE_NAME}'. Verifique os detalhes acima.${RESET}"
    exit 1
fi
