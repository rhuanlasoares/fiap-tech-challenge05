# 💻 Aplicações & Microsserviços

Esta pasta contém o código-fonte de todos os microsserviços de negócio da plataforma **SolidaryTech** e do motor inteligente de operações **AIOps Engine**.

---

## 🧭 Catálogo de Aplicações

```
apps/
├── aiops-engine/         # 🧠 Motor inteligente de AIOps (FastAPI + ML + Google Gemini GenAI)
├── ngo-service/          # 🏢 Gestão e cadastro de ONGs e causas sociais
├── donation-service/     # 💳 Processamento assíncrono de doações integrado ao AWS SQS
├── volunteer-service/    # 🤝 Cadastro e alocação de voluntários para ações sociais
└── gcp-status-checker/   # 📡 Monitor proativo de integridade de serviços da Google Cloud
```

---

## 📋 Resumo dos Microsserviços

| Aplicação | Linguagem / Framework | Finalidade | Principais Integrações |
| :--- | :--- | :--- | :--- |
| **`aiops-engine`** | Python 3.12+ (FastAPI) | Detecção de anomalias, análise de causa raiz com IA (Gemini 3.5), auto-remediação de pods e alertas no Slack | Kubernetes API, Prometheus, Loki, Google Gemini, Slack Webhooks |
| **`ngo-service`** | Python / Flask | Gerenciamento de ONGs parceiras, cadastro e consulta de projetos sociais | PostgreSQL (Cloud SQL), OpenTelemetry, Prometheus |
| **`donation-service`** | Python / Flask | Recepção e liquidação assíncrona de doações financeiras | Amazon SQS, PostgreSQL (Cloud SQL), KEDA, OpenTelemetry |
| **`volunteer-service`** | Python / Flask | Gestão de perfis e engajamento de voluntários | PostgreSQL (Cloud SQL), OpenTelemetry, Prometheus |
| **`gcp-status-checker`** | Python | Varredura de incidentes públicos da GCP na região com modo de simulação de desastres | GCP Incident RSS/API, New Relic, Slack Webhooks |

---

## 🧠 Destaque: AIOps Engine

Para ver a documentação completa, arquitetura de ML, prompts da IA generativa e endpoints da API de AIOps, consulte o documento dedicado:

👉 **[Documentação Completa do AIOps Engine](./aiops-engine/README.md)**

---

## 🐳 Build e Teste Local das Imagens

Você pode compilar e enviar todas as imagens de contêiner utilizando o script:

```bash
# Constrói e envia as imagens Docker para o GCP Artifact Registry
bash scripts/build-push-images.sh
```