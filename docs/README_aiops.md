# 🧠 AIOps Predictive Engine (FastAPI + Machine Learning + Google Gemini GenAI)

O **AIOps Engine** é o cérebro operacional e de auto-remediação (*Self-Healing*) da plataforma **SolidaryTech**. Ele atua como um engenheiro autônomo de Site Reliability Engineering (SRE), executando coleta contínua de telemetria, detecção antecipada de anomalias via Machine Learning, diagnóstico inteligente de causa raiz (RCA) via **Google Gemini GenAI**, auto-remediação no Kubernetes e emissão automatizada de **Post-Mortem** no Slack após a estabilização do cluster.

> 📖 **Para detalhes completos sobre o cálculo de SLA, SLI, SLO, Error Budget e arquitetura de Disaster Recovery Multi-Região, consulte o documento na raiz: [README_postmortem.md](../../README_postmortem.md).**

---

## 🏛️ Fluxo Operacional & Ciclo de Análise Contínua

O AIOps executa um loop assíncrono em background a cada **30 segundos** (configurável via `ANALYSIS_INTERVAL_SECONDS`):

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FLUXO OPERACIONAL DO AIOPS ENGINE                                │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  1. COLETA MULTI-SINAL (A cada 30 segundos)                                                      │
│     ├── Prometheus ──▶ 4 Golden Signals (Latência, Tráfego, Erros 5xx, Saturação) + RAM + PVCs   │
│     ├── Grafana Loki ─▶ Varredura de logs em busca de "Exception", "Error" e HTTP 5xx           │
│     └── K8s API    ──▶ Eventos de Warning (OOMKilled, CrashLoopBackOff, Unhealthy, NodePressure)│
│                                                                                                  │
│  2. FILTRO PREDITIVO COM MACHINE LEARNING (Local)                                                │
│     ├── Detecção de Memory Leaks lineares (calcula taxa de crescimento e minutos até OOMKill)    │
│     ├── Previsão estatística de esgotamento de Persistent Volume Claims (PVCs)                   │
│     └── Cálculo do Cluster Health Score (0 a 100)                                                │
│     💡 EFICIÊNCIA DE CUSTO: Se o cluster estiver 100% estável, o ciclo encerra sem gastar IA.  │
│                                                                                                  │
│  3. DIAGNÓSTICO INTELIGENTE COM GENAI (Google Gemini 3.6 Flash / 3.5 Flash Lite)                 │
│     ├── Acionado automaticamente quando uma anomalia ou risco é detectado                        │
│     ├── Correlaciona em tempo real: [Métricas] + [Logs do Loki] + [Eventos K8s]                  │
│     └── Retorna RCA estruturado: Causa Raiz, Impacto, Comando Recomendado e Playbook de Ação     │
│                                                                                                  │
│  4. AÇÃO AUTOMÁTICA & DISPATCH                                                                   │
│     ├── Web Dashboard & REST API (Exibição interativa em tempo real)                             │
│     ├── Notificação no Slack (Card formatado com badges de severidade e análise da IA)          │
│     └── Self-Healing Autônomo (Se AUTO_HEALING_ENABLED=true: reinício de pods / ajuste de réplica│
│                                                                                                  │
│  5. ESTABILIZAÇÃO & POST-MORTEM                                                                  │
│     ├── Ao atingir Health Score >= 95 sem riscos residuais: sintetiza relatório de Post-Mortem  │
│     └── Envia card com MTTR, Causa Raiz e Action Items ao canal do Slack via Webhook            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Como Obter e Configurar a Chave Gratuita do Google Gemini (Free Tier)

Para utilizar o modelo do Gemini **100% de graça (sem necessidade de cartão de crédito ou créditos pré-pagos)**, siga o passo a passo abaixo:

### 📋 Passo a Passo para Gerar a Chave Grátis:
1. Acesse o portal do **[Google AI Studio - API Keys](https://aistudio.google.com/app/apikey)**.
2. Faça login com a sua conta Google.
3. Clique no botão azul **"Create API key"**.
4. ⚠️ **IMPORTANTE:** Na janela que abrir, selecione a opção **"Create API key in new project"** (Criar chave em um novo projeto).
   > *Criar em um projeto novo garante que a chave fique vinculada ao **Free Tier padrão**, que oferece **15 requisições por minuto (RPM) gratuitas**, sem conflitar com projetos que possuam faturamento pré-pago esgotado.*
5. Copie a chave gerada (ela começa com `AIzaSy...`).

---

## 🤖 Modelos Recomendados & Compatibilidade

A aplicação possui **descoberta dinâmica de modelos** e suporta a geração mais recente do Gemini:

| Modelo | Status | Finalidade | Cota Free Tier |
| :--- | :--- | :--- | :--- |
| **`gemini-3.6-flash`** | ⭐ **Recomendado** | Modelo padrão de alta velocidade e raciocínio para SRE | 15 RPM Grátis |
| **`gemini-3.5-flash-lite`** | Ativo | Modelo ultra rápido e leve para microdiagnósticos | 15 RPM Grátis |
| **`gemini-3.1-pro-preview`** | Ativo | Análises complexas e diagnósticos aprofundados | Disponível |

---

## 🛡️ Resiliência & Fallback Determinístico

Se por qualquer motivo a conexão com a API do Google falhar (falta de internet, chave expirada ou quota temporariamente excedida), o AIOps Engine **não para e não quebra**. Ele aciona automaticamente o módulo de fallback **`_expert_rulebook_rca`**, que gera o diagnóstico de causa raiz, as ações de remediação e o Post-Mortem de forma local e determinística, mantendo 100% de disponibilidade.

---

## 🐳 Como Rodar Localmente via Docker

### 1. Build da Imagem
```bash
docker build -t aiops-engine apps/aiops-engine
```

### 2. Executar o Contêiner com a Chave e Webhook do Slack
```bash
docker run -d --name aiops-engine-test \
  -p 8000:8000 \
  -e GEMINI_API_KEY="AIzaSySuaChaveAqui" \
  -e GEMINI_MODEL="gemini-3.6-flash" \
  -e AUTO_HEALING_ENABLED="true" \
  -e SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
  aiops-engine
```

---

## 🧪 Como Testar a Inteligência da IA

O AIOps Engine possui endpoints de simulação (*Chaos Engineering*) para validar o comportamento da IA:

### Simulação 1: Memory Leak (Prevenção de OOMKill)
```bash
curl -X POST http://localhost:8000/api/simulate-anomaly \
  -H "Content-Type: application/json" \
  -d '{"scenario": "memory_leak"}' | jq .
```

### Simulação 2: Surto de Erros HTTP 5xx
```bash
curl -X POST http://localhost:8000/api/simulate-anomaly \
  -H "Content-Type: application/json" \
  -d '{"scenario": "5xx_surge"}' | jq .
```

### Consultar os Diagnósticos Gerados pela IA
```bash
curl -s http://localhost:8000/api/insights | jq .
```

---

## 🖥️ Dashboard Web Interativo

Acesse no navegador:
👉 **[http://localhost:8000](http://localhost:8000)**

Recursos do Dashboard:
* **Cluster Health Index:** Indicador circular com score de 0 a 100 e gradiente dinâmico.
* **Diagnósticos Gemini GenAI:** Cards com RCA, causa raiz, comando sugerido e playbook.
* **Painel de Simulação:** Botões interativos para simular falhas e testar auto-remediação.
* **Log Stream do Loki:** Visualizador em tempo real dos logs de erro do cluster.

---

## 🔌 Tabela de Endpoints da API REST

| Método | Rota | Descrição |
| :--- | :--- | :--- |
| `GET` | `/` | Retorna o dashboard web interativo. |
| `GET` | `/health` | Health check nativo da aplicação (K8s probes). |
| `GET` | `/api/status` | Retorna o payload completo de telemetria e estado atual. |
| `GET` | `/api/health-score` | Retorna a nota de saúde atual do cluster (0 a 100). |
| `GET` | `/api/predictions` | Lista todas as previsões ativas de esgotamento de memória e PVCs. |
| `GET` | `/api/anomalies` | Lista anomalias de latência e taxas de erro HTTP detectadas. |
| `GET` | `/api/insights` | Retorna os diagnósticos de RCA gerados pelo Google Gemini. |
| `POST` | `/api/simulate-anomaly` | Dispara cenários de caos sintéticos (`memory_leak`, `5xx_surge`). |
| `POST` | `/api/analyze-now` | Força a execução imediata de um ciclo de análise completo. |
| `POST` | `/api/remediate/{id}` | Dispara manualmente a remediação de um risco específico. |

---

## ⚙️ Variáveis de Ambiente

| Variável | Padrão | Descrição |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `""` | Chave de API do Google Gemini (Google AI Studio). |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Modelo do Gemini para geração de Root Cause Analysis e Post-Mortem. |
| `ANALYSIS_INTERVAL_SECONDS` | `30` | Intervalo em segundos entre ciclos de análise em background. |
| `AUTO_HEALING_ENABLED` | `false` | Habilita ações automáticas de auto-cura no Kubernetes. |
| `PROMETHEUS_URL` | `http://monitoring-kube-prometheus-prometheus.monitoring-ns:9090` | Endpoint do Prometheus no cluster. |
| `LOKI_URL` | `http://loki.monitoring-ns:3100` | Endpoint do Loki no cluster. |
| `TARGET_NAMESPACES` | `donation-ns,ngo-ns,volunteer-ns,monitoring-ns,kubecost` | Namespaces monitorados pelo motor. |
| `SLACK_WEBHOOK_URL` | `""` | Webhook do Slack para alertas de incidentes e Post-Mortem. |
