# 📋 Engenharia de Confiabilidade (SRE) — Post-Mortem, SLA, SLI, SLO & Resiliência Multi-Região
### 🎓 FIAP Tech Challenge — Fase 5 | SolidaryTech Platform

Este documento detalha as práticas e cálculos formais de **Site Reliability Engineering (SRE)**, o ciclo automatizado de emissão de **Post-Mortem com GenAI (Google Gemini)** via Webhook do Slack e a arquitetura de **Resiliência Multi-Região e Disaster Recovery (DR)** implementada na plataforma **SolidaryTech**.

---

## 🟢 1. Post-Mortem Automatizado no Slack via AIOps Engine

O **AIOps Engine** (`apps/aiops-engine`) rastreia o ciclo de vida completo de qualquer incidente ou anomalia operacional no cluster Kubernetes:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CICLO DE VIDA DO INCIDENTE & POST-MORTEM                          │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  [ 1. INCIDENT DETECTED ]                                                                        │
│  ├── Health Score < 90 ou Riscos Preditivos > 0 (Memory Leak, Erros 5xx, Queda de PVC)           │
│  ├── Alerta Imediato disparado no Slack com severidade e diagnóstico de Causa Raiz (RCA)         │
│  └── Início da contagem de tempo do incidente (Time to Detect / T0)                              │
│                                                                                                  │
│  [ 2. AUTO-HEALING & REMEDIAÇÃO ]                                                                │
│  ├── Se AUTO_HEALING_ENABLED=true: Execução de Rollout Restart, ajuste KEDA ou scaling           │
│  └── Se manual: Intervenção da equipe On-Call orientada pelo Playbook gerado pela GenAI          │
│                                                                                                  │
│  [ 3. ESTABILIZAÇÃO DO CLUSTER ]                                                                 │
│  ├── Health Score recuperado para >= 95 e 0 anomalias ativas por ciclos consecutivos             │
│  └── Cálculo exato da duração do incidente (MTTR - Mean Time to Resolution)                      │
│                                                                                                  │
│  [ 4. GERAÇÃO & DISPARO DO POST-MORTEM ]                                                         │
│  ├── Google Gemini GenAI sintetiza: Resumo Executivo + Causa Raiz + Lições + Action Items         │
│  └── Envio de Card Especial de Post-Mortem formatado via Slack Block Kit Webhook                 │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 📋 Estrutura do Relatório de Post-Mortem
1. **Status & Confirmação de Estabilização**: Confirmação visual de que o cluster voltou a operar com nota saudável (ex: `Score: 100/100`).
2. **Tempo Médio de Resolução (MTTR)**: Duração exata desde a primeira anomalia detectada até a normalização dos pods e métricas.
3. **Resumo Executivo**: Síntese de alto nível do impacto no negócio e no tráfego de usuários.
4. **Causa Raiz Técnica (RCA)**: Diagnóstico aprofundado gerado pelo Gemini correlacionando logs do Loki, métricas de memória/CPU e eventos do Kubernetes.
5. **Remediação Aplicada**: Detalhamento da ação que estabilizou o ambiente (ex: *Graceful Rollout Restart*, expiração de deadlocks).
6. **Ações Preventivas (*Action Items*) & Lições Aprendidas**: Recomendações práticas para evitar reincidência (ajuste de *resource limits*, correção de query SQL, testes de carga).

### 🛡️ Resiliência e Fallback Determinístico
Caso a API do Google Gemini esteja momentaneamente inacessível ou com cota excedida, o motor aciona automaticamente o fallback **`_expert_rulebook_rca`**, gerando o Post-Mortem determinístico e mantendo a notificação no Slack sem interrupções.

---

## 📊 2. Metodologia de Cálculo: SLA, SLI, SLO e Error Budget

A plataforma adota o framework de confiabilidade do **Google SRE Book**, baseado na premissa:

$$\mathbf{SLA} < \mathbf{SLO} \le \mathbf{SLI}_{\text{atual}}$$

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   A TRÍADE DE CONFIABILIDADE                            │
├────────────────────────────┬────────────────────────────┬───────────────────────────────┤
│ SLI (Indicador Real)       │ SLO (Meta Interna)         │ SLA (Acordo Contratual)       │
│ O que está sendo medido no │ A meta de qualidade que a  │ O compromisso com o cliente   │
│ cluster em tempo real.     │ engenharia busca manter.   │ final (com penalidades).      │
│ Ex: 99.94% de sucesso HTTP │ Ex: 99.90% em 30 dias      │ Ex: 99.50% de disponibilidade │
└────────────────────────────┴────────────────────────────┴───────────────────────────────┘
```

---

### 2.1 Fórmulas Matemáticas Fundamentais

#### Cálculo do SLI (Baseado em Eventos):
$$\text{SLI} = \frac{\sum \text{Número de Bons Eventos}}{\sum \text{Número Total de Eventos}} \times 100\%$$

#### Cálculo do Error Budget (Orçamento de Erro):
$$\text{Error Budget} = 100\% - \text{SLO}$$
*Para um SLO de **99.90%** em uma janela móvel de 30 dias (43.200 minutos), o Error Budget permite no máximo **43,2 minutos de indisponibilidade** (ou 0,10% de requisições com erro).*

#### Cálculo de Burn Rate (Velocidade de Consumo do Orçamento):
$$\text{Burn Rate} = \frac{\text{Taxa de Erro Atual}}{\text{Taxa de Erro Permitida pelo SLO}}$$
* **Burn Rate = 1**: O orçamento de erro será consumido exatamente no prazo de 30 dias.
* **Burn Rate = 14.4**: O orçamento total de 30 dias será esgotado em apenas **2 dias** $\rightarrow$ Disparo de alerta `CRITICAL` no Slack pelo AIOps!

---

### 2.2 Consultas PromQL dos 4 Golden Signals

| Golden Signal | Descrição do SLI | Expressão PromQL (Janela de 30 dias) |
| :--- | :--- | :--- |
| **Disponibilidade HTTP** | % de requisições sem status `5xx` | `(sum(rate(http_requests_total{status!~"5.."}[30d])) / sum(rate(http_requests_total[30d]))) * 100` |
| **Latência da Aplicação** | % de requisições atendidas em $< 300\text{ms}$ (p95) | `(sum(rate(http_request_duration_seconds_bucket{le="0.3"}[30d])) / sum(rate(http_request_duration_seconds_count[30d]))) * 100` |
| **Mensageria Assíncrona** | % de doações processadas no SQS em $< 60\text{s}$ | `(sum(rate(sqs_messages_processed_success_total[30d])) / sum(rate(sqs_messages_received_total[30d]))) * 100` |
| **Banco de Dados (Cloud SQL)** | % de transações commitadas sem timeout ou deadlock | `(sum(rate(pg_stat_database_xact_commit[30d])) / (sum(rate(pg_stat_database_xact_commit[30d])) + sum(rate(pg_stat_database_xact_rollback[30d])))) * 100` |

---

### 2.3 Como Calcular o SLO do Sistema Inteiro (Composite SLO)

A plataforma SolidaryTech calcula o SLO global através de duas abordagens complementares:

#### A. Composição Ponderada por Volume de Eventos (Global Event-Based SLI)
$$\text{SLI}_{\text{Global}} = \frac{\sum \text{Eventos Válidos}_{\text{Gateway}} + \sum \text{Eventos Válidos}_{\text{Donation}} + \sum \text{Eventos Válidos}_{\text{NGO}} + \sum \text{Eventos Válidos}_{\text{Volunteer}}}{\sum \text{Total Eventos}_{\text{Gateway}} + \sum \text{Total Eventos}_{\text{Donation}} + \sum \text{Total Eventos}_{\text{NGO}} + \sum \text{Total Eventos}_{\text{Volunteer}}} \times 100\%$$

#### B. Jornada Crítica do Usuário (Critical User Journey - CUJ) em Série
Para a jornada de ponta a ponta (Usuário $\rightarrow$ Gateway API $\rightarrow$ `donation-service` $\rightarrow$ Cloud SQL Master):
$$\text{SLO}_{\text{Jornada}} = \text{SLO}_{\text{Gateway L7}} \times \text{SLO}_{\text{Donation Svc}} \times \text{SLO}_{\text{Cloud SQL}} = 99.99\% \times 99.90\% \times 99.95\% = \mathbf{99.84\%}$$

> [!TIP]
> O uso de **AWS SQS** desacopla a ingestão de doações da persistência síncrona. Mesmo em caso de lentidão temporária no banco, o endpoint de doações responde com sucesso imediato ao cliente em **99.99%** das vezes.

---

## 🌍 3. Resiliência Multi-Região & Disaster Recovery (DR)

A infraestrutura provisionada via **Terraform** (`iac/terraform/terraform.tfvars`) contempla resiliência multi-região para tolerância a falhas catastróficas:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           ARQUITETURA DE RESILIÊNCIA MULTI-REGIÃO (DR)                           │
├───────────────────────────────────────────────────┬──────────────────────────────────────────────┤
│ REGIÃO PRIMÁRIA (southamerica-east1)              │ REGIÃO SECUNDÁRIA / DR (us-east1)            │
├───────────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ • GKE Cluster: gke-samerica                       │ • GKE Cluster: gke-useast                    │
│   (should_be_create = true - ATIVO)               │   (should_be_create = false - STANDBY)       │
│                                                   │                                              │
│ • Cloud SQL Master: sql-rhuan-ngo / donation      │ • Cloud SQL Read Replica: Cross-Region       │
│   (Instância primária de escrita e leitura)       │   (enable_cross_region_replica = true - RPO<5s)│
│                                                   │                                              │
│ • Gateway API: solidary-tech.nip.io (L7 Routing)  │ • Cloud DNS / Failover Policy                │
└───────────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

### 3.1 Cloud SQL Cross-Region Read Replica (Provisionada em `us-east1`)
* **Status no IaC**: `enable_cross_region_replica = true` e `replica_region = "us-east1"`.
* **RPO (Recovery Point Objective)**: **$< 5$ segundos** (replicação assíncrona contínua entre São Paulo e Carolina do Sul).
* **RTO (Recovery Time Objective)**: **$< 2$ minutos** (promoção de réplica para master via comando `gcloud sql instances promote-replica`).
* **Impacto no SLO**: Garante que falhas no datacenter da América do Sul não causem perda definitiva de dados cadastrais de ONGs ou registros de doações.

### 3.2 Cluster GKE Disaster Recovery (`should_be_create = false`)
* **Definição no Terraform**:
  ```hcl
  gke = {
    southamerica = {
      cluster_name     = "gke-samerica"
      region           = "southamerica-east1"
      should_be_create = true
    }
    useast = {
      cluster_name     = "gke-useast"
      region           = "us-east1"
      should_be_create = false # Aguardando ativação em cenário de desastre
    }
  }
  ```
* **Estratégia de Ativação (*Pilot Light / Warm DR*)**:
  1. Em caso de indisponibilidade regional prolongada em `southamerica-east1` detectada pelo AIOps Engine, o SRE ou pipeline altera `should_be_create = true` para `useast`.
  2. O Terraform provisiona os node pools do `gke-useast` na sub-rede `subnet-gke-us` (`10.4.0.0/24`).
  3. O **ArgoCD** sincroniza automaticamente todas as aplicações (`apps/` e `k8s/`) no novo cluster a partir do repositório Git.
  4. A réplica do Cloud SQL em `us-east1` é promovida a Master.
* **Elevação do SLO de Disponibilidade Global**:
  * Disponibilidade em Região Única: **99.90%** (~43,2 min/mês de downtime tolerado).
  * Disponibilidade com Failover Multi-Região Ativo: **99.99%** (~4,32 min/mês de downtime tolerado).

---

## 📋 4. Tabela Resumo de SLAs, SLOs e Error Budgets da Plataforma

| Componente / Camada | SLI Monitorado | SLO Alvo (Interno) | SLA Prometido (Contrato) | Error Budget (30 dias) |
| :--- | :--- | :--- | :--- | :--- |
| **Gateway API (L7)** | Taxa de Sucesso HTTP (!= 5xx) | **99.99%** | **99.90%** | 4,32 minutos |
| **donation-service** | Latência $< 250\text{ms}$ & Sucesso | **99.90%** | **99.50%** | 43,20 minutos |
| **ngo-service** | Taxa de Sucesso HTTP 2xx/3xx | **99.90%** | **99.50%** | 43,20 minutos |
| **volunteer-service** | Latência $< 300\text{ms}$ & Sucesso | **99.90%** | **99.50%** | 43,20 minutos |
| **Cloud SQL Master (SA)** | Uptime & Query Latency $< 50\text{ms}$ | **99.95%** | **99.90%** | 21,60 minutos |
| **Cloud SQL DR Replica (US)** | Atraso de Replicação $< 5\text{s}$ | **99.99%** | **99.90%** | 4,32 minutos |
| **AWS SQS Async Queue** | Ingestão e Entrega de Mensagens | **99.99%** | **99.90%** | 4,32 minutos |
| **GKE Cluster Primário** | Disponibilidade dos Nós do Cluster | **99.95%** | **99.90%** | 21,60 minutos |
| **Sistema Completo (Global)** | **Jornada de Ponta a Ponta Ponderada** | **99.85%** | **99.50%** | **64,80 minutos** |
| **Sistema com DR Ativo (US)** | **Multi-Region Failover Ativado** | **99.99%** | **99.90%** | **4,32 minutos** |
