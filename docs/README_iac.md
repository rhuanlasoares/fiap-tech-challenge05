# 🏗️ Infraestrutura como Código (IaC) & Gerenciamento de Configuração

Esta pasta contém toda a automação de infraestrutura da plataforma **SolidaryTech**, dividida em duas camadas fundamentais:
1. **[Terraform](./terraform)**: Provisionamento de recursos Cloud (GCP e AWS) e federação de identidades.
2. **[Ansible](./ansible)**: Configuração, bootstrap e orquestração de manifests/Helm charts no Kubernetes (GKE).

---

## 🗺️ Topologia de Infraestrutura

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 TOPOLOGIA DE INFRAESTRUTURA (IaC)                                │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ GOOGLE CLOUD PLATFORM (GCP)                                                                │  │
│  │                                                                                            │  │
│  │  VPC: vpc-rhuan (Cloud NAT + Cloud Router)                                                 │  │
│  │  ├── Subnet Primary (southamerica-east1: 10.0.0.0/24)                                      │  │
│  │  │   ├── GKE Cluster (gke-samerica) ➔ Spot Node Pool (e2-medium, 1-5 nós)                  │  │
│  │  │   └── Cloud SQL PostgreSQL Master (sql-rhuan-ngo & sql-rhuan-donation)                  │  │
│  │  │                                                                                         │  │
│  │  └── Subnet Secondary DR (us-east1: 10.4.0.0/24)                                           │  │
│  │      └── Cloud SQL Cross-Region Read Replica (RPO < 5s para Failover)                      │  │
│  │                                                                                            │  │
│  │  Serviços de Suporte GCP:                                                                  │  │
│  │  ├── Secret Manager (Credenciais DB, Tokens AWS, New Relic API Key, Gemini Key)           │  │
│  │  ├── Artifact Registry (Docker Repositories: southamerica-east1 + us-east1 DR)             │  │
│  │  ├── Cloud Storage (Buckets GCS: Retenção Loki Logs + Backups Velero DR)                   │  │
│  │  └── Workload Identity Federation (Autenticação GitHub Actions OIDC sem Chaves)            │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ AMAZON WEB SERVICES (AWS)                                                                  │  │
│  │  └── Amazon SQS Queue (sm-sqs-queue-url ➔ Mensageria Assíncrona de Doações)                │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Componentes do Terraform (`iac/terraform`)

O provisionamento segue uma arquitetura modularizada, garantindo isolamento, reusabilidade e baixo acoplamento:

| Módulo | Descrição | Principais Recursos |
| :--- | :--- | :--- |
| **`modules/vpc`** | Rede Virtual Privada isolada | VPC Custom, Subnets (`southamerica-east1` e `us-east1`), Cloud Router, Cloud NAT e IP estático global para Gateway API |
| **`modules/gke`** | Cluster Kubernetes Gerenciado | Cluster privado, Workload Identity, Node Pool com instâncias **Spot** (`e2-medium`), autoscaling elástico (1-5 nós) e Image Streaming (`gcfs_config`) |
| **`modules/cloud_sql`** | Banco de Dados Relacional | Instâncias PostgreSQL primária com **Cross-Region Read Replica** em `us-east1` para Disaster Recovery (RPO < 5s) |
| **`modules/bucket`** | Armazenamento de Objetos | Buckets GCS dedicados para retenção de logs do Loki e backups completos do Velero |
| **`modules/secret_manager`** | Cofre de Segredos | Gerenciamento de credenciais de bancos, tokens AWS, chaves de API da New Relic e do Google Gemini |
| **`modules/wifederation`** | Segurança CI/CD sem Chaves | Workload Identity Federation (WIF) permitindo que o GitHub Actions se autentique via OIDC sem armazenar `service_account_keys` JSON |
| **`modules/iam`** | Permissões & Workload Identity | Mapeamento de Service Accounts GCP com ServiceAccounts do K8s (`sa-gke`) via Workload Identity para acesso granular aos recursos |
| **`modules/artifact_registry`** | Registro de Contêineres | Repositórios OCI para as imagens dos microsserviços e do AIOps Engine |
| **`modules/aws`** | Integração Multi-Cloud | Criação de fila Amazon SQS para comunicação assíncrona de eventos |

### 🚀 Como Executar o Terraform

```bash
cd iac/terraform

# 1. Inicializar providers e módulos
terraform init

# 2. Validar sintaxe e formatação
terraform fmt -check
terraform validate

# 3. Gerar plano de execução
terraform plan -out=tfplan

# 4. Aplicar infraestrutura
terraform apply tfplan
```

---

## ⚙️ Componentes do Ansible (`iac/ansible`)

O Ansible é utilizado para realizar o **Day-2 Configuration & Bootstrap** do cluster GKE através de playbooks idempotentes:

```
iac/ansible/playbooks/
├── namespaces.yaml       # Criação de namespaces isolados (donation-ns, ngo-ns, volunteer-ns, aiops, monitoring-ns, kubecost, argocd, velero)
├── argocd.yaml           # Instalação do Argo CD para GitOps
├── argo-rollouts.yaml    # Instalação do Argo Rollouts Controller & Metric plugins
├── keda.yaml             # Instalação do KEDA (Kubernetes Event-driven Autoscaling)
├── monitoring.yaml       # Instalação do kube-prometheus-stack, Loki e OpenTelemetry
├── kubecost.yaml         # Instalação do Kubecost para FinOps e alocação de custos
├── aiops.yaml            # Deploy do AIOps Engine e RBAC
├── applications.yaml     # Inicialização dos microsserviços e Jobs de secrets
└── velero.yaml           # Configuração do Velero para Backup & DR de Namespaces
```

### 🚀 Executando os Playbooks via Script Automatizado

O repositório disponibiliza um script unificado que obtém o IP do Gateway e aplica os playbooks em ordem:

```bash
# Executa todos os playbooks sequencialmente
bash scripts/ansible.sh
```

---


---

## 🛡️ CI/CD & Segurança da Infraestrutura (DevSecOps IaC)

Toda alteração de infraestrutura no diretório `iac/terraform` passa por uma esteira automatizada de governança em duas etapas no GitHub Actions:

```text
[ Push / PR em iac/terraform/** ]
              │
              ▼
┌──────────────────────────────────────────────┐
│ 1. tf-lint.yaml                              │
│    ├── terraform init -backend=false         │
│    ├── terraform validate                    │
│    └── terraform fmt (auto-fix bot)          │
└──────────────────────┬───────────────────────┘
                       │ (workflow_run: success)
                       ▼
┌──────────────────────────────────────────────┐
│ 2. tf-security.yaml                          │
│    ├── Trivy IaC Scan (motor TFSec + CIS)    │
│    ├── ai-issue-analyzer (Google Gemini)     │
│    │   ├── Issue com código HCL corrigido    │
│    │   └── Auto-close ao resolver problemas  │
│    └── Bloqueio Parametrizado                │
│        (block_on_critical: true/false)       │
└──────────────────────────────────────────────┘
```

### 1. Validação & Lint: `tf-lint.yaml`
- **Gatilho**: Disparado em `push` ou `pull_request` alterando arquivos dentro de `iac/terraform/**`.
- **Ações**: Inicializa providers sem backend remoto, valida sintaxe (`terraform validate`) e corrige indentação HCL (`terraform fmt`).

### 2. Scanner de Segurança & Triagem com IA: `tf-security.yaml`
- **Gatilho Encadeado (`workflow_run`)**: Executado automaticamente após a conclusão com sucesso de `Terraform Lint & Validate`.
- **Motor de Análise**: **Trivy IaC**, incorporando oficialmente as regras de mercado do **TFSec**, verificando configurações inseguras de rede, IAM, armazenamento e conformidade com CIS Benchmarks para GCP e AWS.
- **Triagem com Google Gemini**: Invoca a action `ai-issue-analyzer` com `scan-type: iac`. A IA analisa as más configurações e abre uma GitHub Issue estruturada com o trecho exato de **código HCL corrigido**, impacto de segurança e plano de ação.
- **Auto-fechamento**: Quando os problemas são sanados em um commit posterior, a pipeline encerra a Issue aberta de forma 100% autônoma.
- **Bloqueio Parametrizado (`block_on_critical`)**:
  - **Manual (`workflow_dispatch`)**: Caixa de seleção booleana (`true` ou `false`) para definir se falhas `HIGH` ou `CRITICAL` devem interromper a esteira.
  - **Automático (`workflow_run`)**: Controlado pela variável `vars.TF_BLOCK_ON_CRITICAL` (ou valor padrão `true` no workflow).

## 🔒 Segurança e Melhores Práticas Aplicadas

1. **Princípio do Menor Privilégio (PoLP):** Cada namespace do Kubernetes utiliza Service Accounts distintas mapeadas via GCP Workload Identity.
2. **Zero Hardcoded Secrets:** Senhas e tokens nunca são comitados; são gerenciados via GCP Secret Manager e injetados nos Pods em runtime.
3. **Eficiência de Custos & FinOps:** Utilização de instâncias Spot no GKE com `e2-medium` e monitoramento contínuo de custo via Kubecost.
4. **Sem Credenciais Estáticas no GitHub:** Autenticação das esteiras via OpenTelemetry/OIDC com Workload Identity Federation.