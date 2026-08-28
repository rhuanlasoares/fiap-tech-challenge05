# 🌍 SolidaryTech Platform — Resiliência, Self-Healing, AIOps & Disaster Recovery
### 🎓 FIAP Tech Challenge — Fase 5 (Pós-Graduação em Cloud & DevOps / SRE)

![Kubernetes](https://img.shields.io/badge/Kubernetes-GKE-326ce5?logo=kubernetes&logoColor=white)
![GCP](https://img.shields.io/badge/Cloud-Google_Cloud-4285F4?logo=googlecloud&logoColor=white)
![AWS](https://img.shields.io/badge/Cloud-AWS_SQS-FF9900?logo=amazonaws&logoColor=white)
![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform&logoColor=white)
![Ansible](https://img.shields.io/badge/Config-Ansible-EE0000?logo=ansible&logoColor=white)
![ArgoCD](https://img.shields.io/badge/GitOps-Argo_CD-EF7B4D?logo=argo&logoColor=white)
![Gemini](https://img.shields.io/badge/GenAI-Google_Gemini-8E75B2?logo=google&logoColor=white)
![New Relic](https://img.shields.io/badge/Observability-New_Relic-008c99?logo=newrelic&logoColor=white)

---

## 📖 Visão Executiva

A **SolidaryTech** é uma plataforma multi-cloud resiliente e orientada a microsserviços voltada ao ecossistema de ONGs, doações e trabalho voluntário. O projeto foi projetado seguindo as práticas mais avançadas de **Site Reliability Engineering (SRE)**, **GitOps**, **FinOps** e **AIOps**, garantindo alta disponibilidade, tolerância a desastres regionais, auto-remediação (*Self-Healing*) e automação de ponta a ponta.

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
│  │ GOOGLE CLOUD PLATFORM (southamerica-east1)                                                            │  │
│  │                                                                                                       │  │
│  │  [ Cloud Load Balancer ] ──▶ [ Gateway API (L7 Routing - solidary-tech.nip.io) ]                      │  │
│  │                                 │              │              │              │                        │  │
│  │    ┌────────────────────────────┼──────────────┼──────────────┼──────────────┘                        │  │
│  │    ▼                            ▼              ▼              ▼                                       │  │
│  │  ┌────────────────────────┐   ┌──────────────┐ ┌────────────┐ ┌───────────────┐                       │  │
│  │  │ ngo-service (Canary)   │   │ donation-svc │ │ volunteer  │ │ Observability │                       │  │
│  │  └───────────┬────────────┘   └──────┬───────┘ └─────┬──────┘ └───────┬───────┘                       │  │
│  │              │                       │               │                │                               │  │
│  │              ▼                       │ (SQS Event)   ▼                ▼                               │  │
│  │  ┌────────────────────────┐          │         ┌────────────┐ ┌────────────────────────────────────┐  │  │
│  │  │ Cloud SQL PostgreSQL   │          │         │ Cloud SQL  │ │ Prometheus + Grafana + Loki + OTel │  │  │
│  │  │ (Master Instance)      │          │         │ (Master)   │ │ New Relic Full-Stack Telemetry     │  │  │
│  │  └───────────┬────────────┘          │         └────────────┘ └────────────────────────────────────┘  │  │
│  │              │                       │                                                                │  │
│  │              │ (Cross-Region Sync)   │                                                                │  │
│  │              ▼                       │                                                                │  │
│  │  ┌────────────────────────┐          │                                                                │  │
│  │  │ Cloud SQL (DR Replica) │          │                                                                │  │
│  │  │ us-east1 (RPO < 5s)    │          │                                                                │  │
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
│  │ MOTOR DE INTELIGÊNCIA OPERACIONAL (AIOps Engine)                                                      │  │
│  │  Telemetria K8s ──▶ [ ML Predictor ] ──▶ [ Google Gemini 3.5 GenAI ] ──▶ [ Auto-Healing + Slack Alert ]│  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Mapa de Navegação da Documentação

A documentação deste projeto foi dividida em módulos detalhados para aprofundamento técnico em cada disciplina:

| Módulo | Documento | Principais Tópicos Abordados |
| :--- | :--- | :--- |
| **🏗️ Infraestrutura** | [**`iac/README.md`**](./iac/README.md) | Terraform modular (GCP + AWS), Ansible playbooks, VPC, GKE Spot Node Pool, Cloud SQL DR, Secret Manager e Workload Identity. |
| **☸️ Kubernetes & GitOps** | [**`k8s/README.md`**](./k8s/README.md) | Gateway API, Argo CD, Argo Rollouts (Canary Releases com AnalysisTemplates), KEDA, Observabilidade Full-Stack e FinOps com Kubecost. |
| **💻 Aplicações** | [**`apps/README.md`**](./apps/README.md) | Visão geral dos microsserviços (`ngo-service`, `donation-service`, `volunteer-service`, `gcp-status-checker`) e arquitetura de software. |
| **🧠 AIOps Engine** | [**`apps/aiops-engine/README.md`**](./apps/aiops-engine/README.md) | Detecção de anomalias com Machine Learning, diagnóstico com Google Gemini 3.5 GenAI, Auto-Healing de Pods e notificações Slack. |
| **🤖 CI/CD & DevSecOps** | [**`.github/README.md`**](./.github/README.md) | Workflows reutilizáveis, SAST, SCA, Trivy Container Scanning, autenticação sem chaves via OIDC/WIF e replicação de imagens para DR. |
| **📜 Automação & Testes** | [**`scripts/README.md`**](./scripts/README.md) | Scripts de bootstrap, validação de rotas, injeção de carga sintética e testes automatizados de Disaster Recovery. |

---

## 🌟 Os 6 Pilares de Resiliência & SRE

A plataforma foi validada em cenários de alta criticidade e engenharia de caos:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          MATRIZ DE CAPACIDADES DE SRE                                  │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ 1. Linha de Base         │ 📊 Health Check, Grafana (4 Golden Signals) e New Relic     │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 2. Resiliência de Nó     │ 💥 Queda de Node (Drenagem) ➔ PDB & Zero Downtime           │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 3. Progressive Delivery  │ 🚨 Deploy Quebrado ➔ Argo Rollouts + Auto-Rollback          │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 4. Detecção de Desastre  │ 📡 GCP Status Checker ➔ Simulação de Incidente ➔ Alerta     │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 5. DR de Banco de Dados  │ 🗄️ Queda do Cloud SQL Master ➔ Promoção da Réplica          │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 6. DR de Cluster         │ 💾 Velero ➔ Deleção de Namespace ➔ Restauração via GCS      │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

> 💡 *Para o roteiro completo de apresentação executiva e comandos passo a passo de demonstração ao vivo, consulte o [README_planejamento.md](./README_planejamento.md).*

---

## 🚀 Guia de Inicialização Rápida (Quickstart)

### 1. Provisionar a Infraestrutura com Terraform
```bash
cd iac/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
cd ../..
```

### 2. Configurar o Cluster e Aplicações com Ansible
```bash
# Executa a orquestração completa de namespaces, monitoramento, GitOps e apps
bash scripts/ansible.sh
```

### 3. Validar a Saúde da Plataforma
```bash
# Testar todas as rotas e health checks
bash scripts/test-all-routes.sh

# Validar motor de predição do AIOps
bash scripts/test-aiops-prediction.sh
```

---

## 📂 Estrutura de Pastas do Repositório

```
.
├── .github/              # Pipelines de CI/CD, DevSecOps e automações de DR
├── apps/                 # Código-fonte das aplicações e do AIOps Engine
│   ├── aiops-engine/     # Motor de IA com FastAPI, ML e Google Gemini
│   ├── donation-service/ # Microsserviço de doações com SQS + KEDA
│   ├── gcp-status-checker/# Monitor proativo de saúde dos serviços GCP
│   ├── ngo-service/      # Microsserviço de ONGs parceiras
│   └── volunteer-service/# Microsserviço de voluntários
├── iac/                  # Infraestrutura como Código
│   ├── ansible/          # Playbooks e values de Helm para bootstrap do K8s
│   └── terraform/        # Módulos Terraform para GCP e AWS
├── k8s/                  # Manifests Kubernetes, Gateway API, ArgoCD e Rollouts
├── scripts/              # Scripts utilitários de automação e testes de caos
├── README_planejamento.md# Roteiro narrativo para demonstração ao vivo
└── README.md             # Documento central do projeto
```