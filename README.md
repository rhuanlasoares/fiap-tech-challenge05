# 🌍 SolidaryTech Platform — Resiliência, Self-Healing, SRE, FinOps, AIOps & Disaster Recovery
### 🎓 FIAP Tech Challenge — Fase 5 (Hackathon Final de Pós-Graduação em Cloud & DevOps / SRE)

![Kubernetes](https://img.shields.io/badge/Kubernetes-GKE-326ce5?logo=kubernetes&logoColor=white)
![GCP](https://img.shields.io/badge/Cloud-Google_Cloud-4285F4?logo=googlecloud&logoColor=white)
![AWS](https://img.shields.io/badge/Cloud-AWS_SQS-FF9900?logo=amazonaws&logoColor=white)
![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform&logoColor=white)
![Ansible](https://img.shields.io/badge/Config-Ansible-EE0000?logo=ansible&logoColor=white)
![ArgoCD](https://img.shields.io/badge/GitOps-Argo_CD-EF7B4D?logo=argo&logoColor=white)
![Gemini](https://img.shields.io/badge/GenAI-Google_Gemini_3.6-8E75B2?logo=google&logoColor=white)
![New Relic](https://img.shields.io/badge/Observability-New_Relic_APM-008c99?logo=newrelic&logoColor=white)
![Prometheus](https://img.shields.io/badge/Monitoring-Prometheus-E6522C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Dashboards-Grafana-F46800?logo=grafana&logoColor=white)
![FinOps](https://img.shields.io/badge/FinOps-Kubecost_&_Tags-107C41?logo=databricks&logoColor=white)

---

## 📖 Visão Executiva do Projeto

A **SolidaryTech** é uma plataforma multi-cloud resiliente, escalável e orientada a microsserviços voltada a conectar ONGs, doadores e voluntários em todo o Brasil. Recentemente, com o destaque nacional da iniciativa, o tráfego da aplicação sofreu picos exponenciais e imprevisíveis.

Para suportar essa demanda crítica sem comprometer a viabilidade financeira da ONG nem interromper doações durante falhas regionais, este projeto foi projetado com os pilares mais avançados de **Site Reliability Engineering (SRE)**, **FinOps**, **ITSM/AIOps Autônomo com GenAI** e **Disaster Recovery (DR) Multi-Região**.

---

## 🏛️ Arquitetura Geral da Plataforma

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ARQUITETURA GERAL DA PLATAFORMA SOLIDARYTECH                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│  [ Clientes / Tráfego Externo ]                                  [ GitHub Actions CI/CD ]                   │
│          │                                                                  │ (OIDC / WIF)                  │
│          ▼                                                                  ▼                               │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ GOOGLE CLOUD PLATFORM (southamerica-east1 - Região Primária)                                          │  │
│  │                                                                                                       │  │
│  │  [ Cloud Load Balancer ] ──▶ [ Gateway API (L7 Routing - solidary-tech.nip.io) ]                      │  │
│  │                                 │              │              │              │                        │  │
│  │    ┌────────────────────────────┼──────────────┼──────────────┼──────────────┘                        │  │
│  │    ▼                            ▼              ▼              ▼                                       │  │
│  │  ┌────────────────────────┐   ┌──────────────┐ ┌────────────┐ ┌────────────────────────────────────┐  │  │
│  │  │ ngo-service (Rollout)  │   │ donation-svc │ │ volunteer  │ │ aiops-engine (FastAPI + GenAI)     │  │  │
│  │  └───────────┬────────────┘   └──────┬───────┘ └─────┬──────┘ └─────────────────┬──────────────────┘  │  │
│  │              │                       │               │                          │                     │  │
│  │              ▼                       │ (SQS Event)   ▼                          │ (Auto-Healing K8s)  │  │
│  │  ┌────────────────────────┐          │         ┌────────────┐                   ▼                     │  │
│  │  │ Cloud SQL PostgreSQL   │          │         │ Cloud SQL  │ ┌────────────────────────────────────┐  │  │
│  │  │ (Master Instance)      │          │         │ (Master)   │ │ Prometheus + Grafana + Loki + OTel │  │  │
│  │  └───────────┬────────────┘          │         └────────────┘ │ New Relic Full-Stack Telemetry     │  │  │
│  │              │                       │                        └────────────────────────────────────┘  │  │
│  │              │ (Sync assíncrono)     │                                                                │  │
│  │              ▼                       │                                                                │  │
│  │  ┌────────────────────────┐          │                                                                │  │
│  │  │ Cloud SQL Read Replica │          │                                                                │  │
│  │  │ (us-east1 - RPO < 5s)  │          │                                                                │  │
│  │  └────────────────────────┘          │                                                                │  │
│  └──────────────────────────────────────┼────────────────────────────────────────────────────────────────┘  │
│                                         │                                                                   │
│                                         ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ AMAZON WEB SERVICES (AWS)                                                                             │  │
│  │  [ Amazon SQS Queue ] ◀─── (Async Donations) ──── [ KEDA Event-driven Scaler (GKE) ]                  │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ DISASTER RECOVERY CLUSTER (us-east1 - Standby Ativo-Passivo via Terraform)                            │  │
│  │  [ GKE gke-useast ] ◀─── (Ativação via should_be_create=true) ──── [ ArgoCD GitOps Sync ]             │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Ecossistema de Microsserviços

| Microsserviço | Linguagem / Stack | Função no Ecossistema | Resiliência & Escala |
| :--- | :--- | :--- | :--- |
| **`donation-service`** | **Go 1.22+** | **Caminho Crítico (Hot Path)** de processamento de doações financeiras. | Desacoplado via AWS SQS + KEDA, PDB, Argo Rollouts (Canary), OTel Tracing. |
| **`ngo-service`** | **Python 3.11+** (FastAPI) | Cadastro, credenciamento e gestão de ONGs parceiras. | Cloud SQL PostgreSQL, HPA, PDB, Health Probes ativas e NetworkPolicies. |
| **`volunteer-service`** | **Python 3.11+** (FastAPI) | Matching inteligente entre voluntários e oportunidades. | Cloud SQL PostgreSQL, HPA, TopologySpreadConstraints multi-zona. |
| **`aiops-engine`** | **Python 3.11+** (FastAPI) | Cérebro SRE autônomo com Machine Learning e Google Gemini GenAI. | Varredura de métricas/logs a cada 30s, predição de Memory Leak, Self-Healing e Post-Mortem. |
| **`gcp-status-checker`** | **Python 3.11+** | Verificador contínuo de status dos serviços Google Cloud. | CronJob K8s com relatórios periódicos de integridade de conectividade. |

---

## 🎯 Os 5 Pilares de Excelência da Fase 5 (Atendimento ao Edital)

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       PILARES DE MATURIDADE DO HACKATHON                                    │
├───────────────────┬───────────────────┬───────────────────┬─────────────────────┬───────────────────────────┤
│ 1. Fundação       │ 2. SRE & Golden   │ 3. FinOps &       │ 4. ITSM & AIOps     │ 5. Multicloud, Segurança  │
│    DevOps         │    Metrics        │    Tagging        │    Preditivo        │    & Disaster Recovery    │
├───────────────────┼───────────────────┼───────────────────┼─────────────────────┼───────────────────────────┤
│ • Docker Multi-stg│ • SLOs/SLIs (99.9)│ • Tags em 100% IaC│ • GenAI Gemini 3.6  │ • PCN (RPO<5s, RTO<2m)    │
│ • Terraform IaC   │ • Error Budget    │ • Rightsizing K8s │ • Detecção ML Leaks │ • Cloud SQL DR Replica    │
│ • GitHub Actions  │ • Dashboard Grafan│ • Kubecost        │ • Auto-Healing K8s  │ • GKE Standby (Terraform) │
│ • ArgoCD GitOps   │ • MTTR < 2 min    │ • 56,2% Economia  │ • Slack Post-Mortem │ • Velero Backup GCS       │
└───────────────────┴───────────────────┴───────────────────┴─────────────────────┴───────────────────────────┘
```

---

### 1. 🏗️ Fundação DevOps & DevSecOps
- **Imagens OCI Otimizadas**: Multi-stage builds com imagens base mínimas (`alpine` / `distroless`), usuários não-root (`USER nonroot`) e `.dockerignore` rigoroso.
- **Infraestrutura como Código**: 100% dos recursos provisionados via Terraform modular (VPC com PSA, GKE Spot Node Pools, Cloud SQL, AWS SQS, Secret Manager, Cloud NAT e IAM).
- **Pipelines CI/CD com DevSecOps & IA**: GitHub Actions modulares com **SAST (Gosec/Bandit/Trivy Secrets)**, **SCA (Trivy/OWASP)**, **Container Scan**, linting automatizado com auto-fix e **Triagem Inteligente de Issues com Google Gemini (Google AI Studio)** — filtrando falsos positivos, gerando planos de remediação automáticos e auto-resolvendo issues fechadas. Autenticação federada sem chaves via **Workload Identity Federation (WIF / OIDC)**.
- **GitOps com Argo CD & Rollouts**: Deploy contínuo automatizado com **Canary Releases** progressivos e análise automática de métricas para auto-rollback em caso de falha.

---

### 2. 📊 SRE: Confiabilidade, SLIs, SLOs & Error Budget
- **Regra Fundamental SRE**: $\mathbf{SLA} < \mathbf{SLO} \le \mathbf{SLI}_{	ext{atual}}$
- **SLIs do `donation-service` (Caminho Crítico)**:
  - **Disponibilidade**: % de requisições com status $!= 5xx$ $
ightarrow$ **SLO: 99.90%** (SLA: 99.50%).
  - **Latência**: % de requisições respondidas em $< 250	ext{ms}$ (p95) $
ightarrow$ **SLO: 99.90%**.
- **Error Budget**: Orçamento mensal de **43,20 minutos de erro permitidos** ($100\% - 99.90\% = 0.10\%$).
- **Dashboard Grafana Dedicado**: Painel [`slo-error-budget.json`](./iac/ansible/playbooks/dashboard/slo-error-budget.json) com medidores em tempo real de queima de orçamento e alarme de **Burn Rate** $> 14.4	ext{x}$.
- **Redução de MTTR**: O AIOps Engine reduz o tempo médio de resolução de **~15 minutos (manual) para $< 2$ minutos (automático)**.

---

### 3. 💰 FinOps: Otimização Financeira, Tagging & Forecast de Custos
- **Política Estrita de Tagging**: Todos os recursos do Terraform possuem tags obrigatórias:
  `Project=solidary-tech`, `Environment=production`, `CostCenter=ngo-core`, `CreatedBy=rhuan`, `Terraform=true`.
- **Rightsizing dos Pods**: CPU e Memória ajustados nos manifestos `rollout.yaml` para evitar capacidade ociosa (*Idle Waste*).
- **Projeção de Custos (Forecast Mensal)**:
  - Custo On-Demand tradicional: \$139.26 / mês.
  - Custo Otimizado SolidaryTech: **\$60.93 / mês** (**Economia comprovada de 56,2%**).
- **Otimizações Nativas de Nuvem**:
  - GKE Spot Node Pools com PDB (~70% de economia em computação).
  - AWS SQS Free Tier perpétuo (1.000.000 requisições/mês grátis).
  - KEDA *Scale-to-Zero* eliminando consumo de CPU em períodos sem doações.
  - Kubecost instalado para rateio financeiro por namespace e pod.

---

### 4. 🤖 ITSM & AIOps Preditivo com Google Gemini GenAI
- **Coleta Multi-Sinal (30s)**: Correlaciona 4 Golden Signals do Prometheus, logs de exceção do Loki e eventos de Warning do Kubernetes.
- **Predição por Machine Learning**: Detecta tendências lineares de *Memory Leak* e prevê o tempo exato até o pod sofrer `OOMKilled`.
- **RCA Inteligente com GenAI**: Aciona o **Google Gemini 3.6 Flash** para sintetizar diagnósticos de causa raiz e comandos de mitigação.
- **Self-Healing Seguro**: Se `AUTO_HEALING_ENABLED=true`, dispara *Rollout Restarts* preventivos no Kubernetes.
- **Post-Mortem Automatizado no Slack**: Quando o cluster estabiliza (`Health Score >= 95` e 0 anomalias), envia card executivo formatado no Slack com MTTR, Causa Raiz e *Action Items* preventivos.

---

### 5. 🛡️ Multicloud, Segurança & Disaster Recovery (DR)
- **Plano de Continuidade de Negócios (PCN)**:
  - **RPO (Recovery Point Objective)**: **0 segundos (Zero Data Loss)** no hot path de doações via buffer durável em AWS SQS (`PENDING_BUFFERED`) e worker de auto-drain.
  - **RTO (Recovery Time Objective)**: **< 60 segundos** para Regional HA Failover, **< 2 minutos** para promoção do Cloud SQL e **< 5 minutos** para GKE DR.
- **Estratégias Avançadas de Resiliência & SRE**:
  - **Isolamento Fino de Falhas**: Matriz para falha isolada de GKE, falha isolada de Cloud SQL e blackout regional total.
  - **Blindagem contra Drift no Terraform**: Diretiva `lifecycle { ignore_changes = [master_instance_name, ...] }` impede que pipelines destruam bancos promovidos na crise.
  - **Watchdog Autônomo com Fast-Confirmation Loop**: Monitor externo no GitHub Actions detecta incidentes oficiais da GCP e confirma falhas em **~65 segundos** (evitando espera de 15 minutos), com persistência em GCS e alertas no Slack.
  - **Operação 1-Click via GitHub Actions**: Workflow `.github/workflows/disaster-recovery.yaml` com guardrails e CLI padronizado `scripts/disaster-recovery-manager.sh`.
  - **Backup Cross-Region com Velero**: Snapshots periódicos de namespaces críticos e volumes no bucket multi-region.

---

## 📚 Central de Documentação do Projeto (`docs/`)

Todos os relatórios executivos, planos de continuidade, guias SRE e documentações técnicas foram centralizados na pasta [**`docs/`**](./docs/):

| Documento | Localização | Descrição / Finalidade |
| :--- | :--- | :--- |
| **🛡️ Plano de Continuidade (PCN)** | [**`docs/PCN_PLANO_CONTINUIDADE_NEGOCIOS.md`**](./docs/PCN_PLANO_CONTINUIDADE_NEGOCIOS.md) | Documento formal de PCN com BIA, RTO/RPO e 4 procedimentos de Disaster Recovery. |
| **💰 FinOps & Forecast de Custos** | [**`docs/FINOPS_FORECAST_CUSTOS.md`**](./docs/FINOPS_FORECAST_CUSTOS.md) | Relatório de governança de custos, evidências de tagging, rightsizing e economia de 56,2%. |
| **🎓 Relatório Final (.PDF Blueprint)** | [**`docs/RELATORIO_FINAL_HACKATHON.md`**](./docs/RELATORIO_FINAL_HACKATHON.md) | Minuta formatada com as 4 seções obrigatórias para geração do relatório PDF da entrega. |
| **📋 SRE, SLOs & Post-Mortem** | [**`docs/README_postmortem.md`**](./docs/README_postmortem.md) | Fórmulas de SLI/SLO/SLA, Error Budget, Golden Signals PromQL e Post-Mortem AIOps. |
| **🏗️ Infraestrutura como Código** | [**`docs/README_iac.md`**](./docs/README_iac.md) | Documentação dos módulos Terraform (GCP/AWS) e playbooks Ansible. |
| **☸️ Kubernetes & GitOps** | [**`docs/README_k8s.md`**](./docs/README_k8s.md) | Gateway API, ArgoCD, Argo Rollouts, KEDA e RBAC. |
| **💻 Microsserviços da Aplicação** | [**`docs/README_apps.md`**](./docs/README_apps.md) | Arquitetura de software, endpoints REST e variáveis dos serviços. |
| **🧠 AIOps Predictive Engine** | [**`docs/README_aiops.md`**](./docs/README_aiops.md) | Arquitetura do motor preditivo, integração com Gemini e simulações de caos. |
| **🤖 CI/CD & DevSecOps** | [**`docs/README_github.md`**](./docs/README_github.md) | Workflows do GitHub Actions, SAST, SCA, Trivy, Triagem Inteligente com Gemini e WIF/OIDC. |
| **📜 Automação & Testes** | [**`docs/README_scripts.md`**](./docs/README_scripts.md) | Scripts de bootstrap, validação de rotas e simulações de Disaster Recovery. |

---

## 🎬 Roteiro de Demonstração em Vídeo (Até 20 Minutos)

A estrutura recomendada para a gravação do vídeo de avaliação divide a apresentação em duas partes:

1. **Parte 1: Pitch Executivo para Diretoria (00:00 - 07:00)**:
   - Apresentação do desafio da ONG, impacto social, PCN com RPO $< 5\text{s}$ e RTO $< 2\text{m}$, redução de 56% no Forecast FinOps e governança com SLAs/SLOs.
2. **Parte 2: Demo Técnica Operacional (07:00 - 20:00)**:
   - **ATO 1**: Linha de Base (Grafana SRE SLO Dashboard, New Relic APM e ArgoCD Synced).
   - **ATO 2**: Caos de Infraestrutura (Drenagem de nó do GKE, PDB, HPA e Zero Downtime).
   - **ATO 3**: Self-Healing de Release (Deploy com erro, Argo Rollouts Auto-Rollback).
   - **ATO 4**: AIOps Preditivo (Detecção de Memory Leak, Gemini GenAI RCA, Slack Post-Mortem).
   - **ATO 5**: Disaster Recovery de Banco (Falha no Cloud SQL Master, Promoção da réplica em `us-east1`).
   - **ATO 6**: DR de Cluster & Backup (Restauração via Velero GCS + Ativação GKE DR no Terraform).

---

## 👥 Identificação da Equipe

* **Instituição**: FIAP — Pós-Graduação em Cloud & DevOps / SRE
* **Projeto**: Tech Challenge Fase 5 (Hackathon Final)
* **Integrante**: Rhuan Soares (RM: 369545)
* **Repositório**: [https://github.com/rhuanlasoares/fiap-tech-challenge05](https://github.com/rhuanlasoares/fiap-tech-challenge05)
* **LinkedIn**: https://www.linkedin.com/in/rhuan-soares/