# ☸️ Kubernetes, GitOps, Roteamento & Observabilidade

Esta pasta contém todos os manifests e especificações declarativas para o ecossistema Kubernetes rodando no **Google Kubernetes Engine (GKE)**.

---

## 🏛️ Visão Geral da Arquitetura do Cluster

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                ARQUITETURA DO CLUSTER GKE (GITOPS & L7)                          │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  [ Usuários & Clientes ] ──▶ [ GCP External Application Load Balancer ]                          │
│                                           │                                                      │
│                                           ▼                                                      │
│                      ┌────────────────────────────────────────┐                                  │
│                      │ Gateway API (Gateway Controller - L7)  │                                  │
│                      └────────────────────┬───────────────────┘                                  │
│                                           │                                                      │
│      ┌──────────────────┬─────────────────┼─────────────────┬───────────────────┐                │
│      ▼                  ▼                 ▼                 ▼                   ▼                │
│ [/ngo-service]   [/donation-service] [/volunteer]      [/grafana]          [/argocd & /kubecost] │
│      │                  │                 │                 │                   │                │
│      ▼                  ▼                 ▼                 ▼                   ▼                │
│ ┌────────────┐   ┌────────────┐    ┌────────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│ │ ngo-service│   │donation-svc│    │ volunteer  │    │ Grafana &    │    │ Argo CD GitOps &    │ │
│ │ (Canary    │   │ (Canary +  │    │ (Canary    │    │ Prometheus   │    │ Kubecost FinOps     │ │
│ │  Rollout)  │   │  KEDA SQS) │    │  Rollout)  │    │ Golden Sign. │    │ Governance          │ │
│ └─────┬──────┘   └─────┬──────┘    └─────┬──────┘    └──────┬───────┘    └─────────────────────┘ │
│       │                │                 │                  │                                    │
│       └────────────────┼─────────────────┴──────────────────┘                                    │
│                        │                                                                         │
│                        ▼                                                                         │
│       ┌──────────────────────────────────────────────────────────────┐                           │
│       │                 AIOps Engine (FastAPI + ML)                  │                           │
│       │  Coleta Telemetria ➔ Diagnóstico Gemini ➔ Auto-Remediação    │                           │
│       └──────────────────────────────────────────────────────────────┘                           │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Estrutura de Diretórios

| Diretório | Responsabilidade |
| :--- | :--- |
| **`gateway-api/`** | Definição da Gateway (com listeners HTTP:80 e HTTPS:443) e HTTPRoute de redirecionamento automático 301 (HTTP -> HTTPS) via `RequestRedirect` filter no GCP Load Balancer. |
| **`microsservices/`** | Manifests de deploy dos microsserviços (`ngo-service`, `donation-service`, `volunteer-service`, `job-service`) utilizando **Argo Rollouts**, Services, PDBs e HPA/KEDA. |
| **`aiops/`** | Deployment, Service, ServiceAccount (GCP Workload Identity) e ClusterRole RBAC para o **AIOps Engine**. |
| **`argocd/`** | Configurações do Argo CD Application e sincronização declarativa contínua do repositório Git. |
| **`monitoring/`** | Regras de alertas dos 4 Golden Signals (`golden-signals-rules.yaml`) e Secret do New Relic (o watchdog do `gcp-status-checker` roda externamente no GitHub Actions). |
| **`kubecost/`** | Roteamento HTTPRoute e parametrização do Kubecost para governança de custos (FinOps). |
| **`namespaces/`** | Declaração dos namespaces da aplicação com labels de segurança e quotas. |

---

## 🚀 Principais Tecnologias & Capacidades Implementadas

### 1. Gateway API (Next-Gen Ingress)
Substitui o Ingress clássico pela **Kubernetes Gateway API**, oferecendo:
* Desacoplamento entre a infraestrutura de rede (`Gateway`) e o roteamento das aplicações (`HTTPRoute`).
* Roteamento baseado em prefixos de caminhos (`/ngo-service`, `/donation-service`, etc.).
* Integração nativa com o Cloud Load Balancing do Google Cloud.

### 2. Progressive Delivery & Self-Healing de Release (Argo Rollouts)
Em vez de deploys padrão `RollingUpdate`, utilizamos **Canary Releases** com análise automatizada de SLOs:
* Cada aplicação possui um `AnalysisTemplate` (`golden-signals-analysis`) que consulta o **Prometheus** em tempo real.
* A nova versão recebe 20% do tráfego. Se a taxa de erro HTTP 5xx ultrapassar 5% ou a latência exceder os limiares de SLO, o Argo Rollouts executa o **Auto-Rollback instantâneo**, protegendo 100% dos usuários finais.

### 3. Autoscaling Orientado a Eventos com KEDA
* O `donation-service` utiliza um `ScaledObject` do **KEDA** monitorando a fila da **Amazon SQS**.
* Quando o backlog de mensagens aumenta, o KEDA escala o número de réplicas de 1 até 10 pods instantaneamente, retornando a zero ou à capacidade mínima quando a fila é drenada.

### 4. Observabilidade Full-Stack & 4 Golden Signals
* **Latência:** Duração média e p95/p99 de requisições por rota.
* **Tráfego:** Taxa de requisições por segundo (RPS) atendidas.
* **Erros:** Contagem e porcentagem de respostas HTTP 4xx e 5xx.
* **Saturação:** Uso de CPU e Memória em relação aos Requests e Limits declarados.
* **Telemetria Distribuída:** Coleta de spans e traces via **OpenTelemetry Collector** exportados diretamente para a plataforma **New Relic**.

### 5. FinOps com Kubecost
* Auditoria de custos em tempo real por namespace, deployment e pod.
* Identificação de capacidade ociosa e sugestões de dimensionamento de *requests/limits*.

---

## 🛠️ Comandos Úteis para o Cluster

```bash
# Obter credenciais do cluster GKE
gcloud container clusters get-credentials gke-samerica --region southamerica-east1 --project $PROJECT_ID

# Acompanhar um Rollout em tempo real
kubectl argo rollouts get rollout ngo-service -n ngo-ns --watch

# Inspecionar Pods e PodDisruptionBudgets
kubectl get pods,pdb -A

# Visualizar eventos e alertas de métricas
kubectl get analysisruns -A
```