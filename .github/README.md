# 🤖 CI/CD, DevSecOps & Automações do GitHub Actions

Esta pasta contém todos os fluxos de trabalho (**Workflows**) do GitHub Actions responsáveis pela governança de código, esteiras de DevSecOps, compilação de imagens Docker, sincronização GitOps e replicação de imagens para **Disaster Recovery (DR)**.

---

## 🗺️ Mapa de Workflows

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             ESTEIRA DE CI/CD & DEVSECOPS (GITHUB ACTIONS)                        │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  [ Git Push / Pull Request ]                                                                     │
│               │                                                                                  │
│               ▼                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 1. QUALIDADE & DEVSECOPS REUTILIZÁVEL                                                      │  │
│  │    ├── reusable-lint.yaml   ➔ Verificação de sintaxe e estilo (Flake8, ESLint)             │  │
│  │    ├── reusable-sast.yaml   ➔ Análise estática de segurança de código (Semgrep)            │  │
│  │    ├── reusable-sca.yaml    ➔ Análise de vulnerabilidades em dependências (CVEs)           │  │
│  │    └── tf-lint.yaml         ➔ Validação e linting de Terraform (tflint + fmt)              │  │
│  └─────────────────────────────────────────────┬──────────────────────────────────────────────┘  │
│                                                │                                                 │
│                                                ▼                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 2. BUILD & SEGURANÇA DE CONTÊINERES                                                        │  │
│  │    ├── Docker Build         ➔ Compilação das imagens OCI dos microsserviços e AIOps        │  │
│  │    ├── reusable-scan.yaml   ➔ Varredura de vulnerabilidades da imagem com Trivy (Bloqueante)│ │
│  │    └── Push Artifact Reg.   ➔ Envio seguro para GCP Artifact Registry (southamerica-east1) │  │
│  └─────────────────────────────────────────────┬──────────────────────────────────────────────┘  │
│                                                │                                                 │
│                                                ▼                                                 │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 3. GITOPS DEPLOY & REPLICAÇÃO DR                                                           │  │
│  │    ├── build-push-gitops    ➔ Atualização declarativa das tags no repositório K8s (Argo CD)│  │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Catálogo dos Workflows

| Workflow | Tipo | Descrição |
| :--- | :--- | :--- |
| **`build-push-gitops.yaml`** | Pipeline Principal | Compila imagens dos microsserviços, roda verificações de segurança, envia para o Google Artifact Registry e atualiza manifests GitOps. |
| **`deploy-*-service.yaml`** | Deploy Específico | Workflows dedicados para acionamento pontual de deploy por microsserviço (`ngo-service`, `donation-service`, `volunteer-service`). |
| **`reusable-lint.yaml`** | DevSecOps Reutilizável | Executa linters estáticos nas linguagens Python, Go e Node. |
| **`reusable-sast.yaml`** | Segurança de Código | Executa testes estáticos de segurança (SAST) para detectar falhas de segurança e segredos vazados no código-fonte. |
| **`reusable-sca.yaml`** | Gestão de Dependências | Analisa dependências e bibliotecas em busca de CVEs conhecidas em pacotes `requirements.txt` e `package.json`. |
| **`reusable-container-scan.yaml`** | Segurança de Contêineres | Varre as camadas da imagem Docker gerada com **Trivy**, bloqueando o deploy em caso de vulnerabilidades `CRITICAL` ou `HIGH`. |
| **`tf-lint.yaml`** | Qualidade de IaC | Valida formatação (`terraform fmt`), sintaxe (`terraform validate`) e boas práticas de Terraform com `tflint`. |

---

## 🔐 Autenticação Segura: Workload Identity Federation (WIF)

Todas as esteiras utilizam autenticação federada **OIDC (OpenID Connect)** com a Google Cloud:
* **Zero Service Account Keys:** Nenhuma chave JSON estática ou de longa duração é gravada nos Secrets do GitHub.
* **Tokens Temporários:** O GitHub Actions solicita um token temporário diretamente ao Google Cloud IAM via Workload Identity Pool configurado via Terraform.