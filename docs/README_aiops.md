# ðŸ§  AIOps Predictive Engine (FastAPI + Machine Learning + Google Gemini GenAI)

O **AIOps Engine** Ã© o cÃ©rebro operacional e de auto-remediaÃ§Ã£o (*Self-Healing*) da plataforma **SolidaryTech**. Ele atua como um engenheiro autÃ´nomo de Site Reliability Engineering (SRE), executando coleta contÃ­nua de telemetria, detecÃ§Ã£o antecipada de anomalias via Machine Learning, diagnÃ³stico inteligente de causa raiz (RCA) via **Google Gemini GenAI**, auto-remediaÃ§Ã£o no Kubernetes e emissÃ£o automatizada de **Post-Mortem** no Slack apÃ³s a estabilizaÃ§Ã£o do cluster.

> ðŸ“– **Para detalhes completos sobre o cÃ¡lculo de SLA, SLI, SLO, Error Budget e arquitetura de Disaster Recovery Multi-RegiÃ£o, consulte o documento na raiz: [README_postmortem.md](../../README_postmortem.md).**

---

## ðŸ›ï¸ Fluxo Operacional & Ciclo de AnÃ¡lise ContÃ­nua

O AIOps executa um loop assÃ­ncrono em background a cada **30 segundos** (configurÃ¡vel via `ANALYSIS_INTERVAL_SECONDS`):

```text
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                                 FLUXO OPERACIONAL DO AIOPS ENGINE                                â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                                                  â”‚
â”‚  1. COLETA MULTI-SINAL (A cada 30 segundos)                                                      â”‚
â”‚     â”œâ”€â”€ Prometheus â”€â”€â–¶ 4 Golden Signals (LatÃªncia, TrÃ¡fego, Erros 5xx, SaturaÃ§Ã£o) + RAM + PVCs   â”‚
â”‚     â”œâ”€â”€ Grafana Loki â”€â–¶ Varredura de logs em busca de "Exception", "Error" e HTTP 5xx           â”‚
â”‚     â””â”€â”€ K8s API    â”€â”€â–¶ Eventos de Warning (OOMKilled, CrashLoopBackOff, Unhealthy, NodePressure)â”‚
â”‚                                                                                                  â”‚
â”‚  2. FILTRO PREDITIVO COM MACHINE LEARNING (Local)                                                â”‚
â”‚     â”œâ”€â”€ DetecÃ§Ã£o de Memory Leaks lineares (calcula taxa de crescimento e minutos atÃ© OOMKill)    â”‚
â”‚     â”œâ”€â”€ PrevisÃ£o estatÃ­stica de esgotamento de Persistent Volume Claims (PVCs)                   â”‚
â”‚     â””â”€â”€ CÃ¡lculo do Cluster Health Score (0 a 100)                                                â”‚
â”‚     ðŸ’¡ EFICIÃŠNCIA DE CUSTO: Se o cluster estiver 100% estÃ¡vel, o ciclo encerra sem gastar IA.  â”‚
â”‚                                                                                                  â”‚
â”‚  3. DIAGNÃ“STICO INTELIGENTE COM GENAI (Google Gemini 3.6 Flash / 3.5 Flash Lite)                 â”‚
â”‚     â”œâ”€â”€ Acionado automaticamente quando uma anomalia ou risco Ã© detectado                        â”‚
â”‚     â”œâ”€â”€ Correlaciona em tempo real: [MÃ©tricas] + [Logs do Loki] + [Eventos K8s]                  â”‚
â”‚     â””â”€â”€ Retorna RCA estruturado: Causa Raiz, Impacto, Comando Recomendado e Playbook de AÃ§Ã£o     â”‚
â”‚                                                                                                  â”‚
â”‚  4. AÃ‡ÃƒO AUTOMÃTICA & DISPATCH                                                                   â”‚
â”‚     â”œâ”€â”€ Web Dashboard & REST API (ExibiÃ§Ã£o interativa em tempo real)                             â”‚
â”‚     â”œâ”€â”€ NotificaÃ§Ã£o no Slack (Card formatado com badges de severidade e anÃ¡lise da IA)          â”‚
â”‚     â””â”€â”€ Self-Healing AutÃ´nomo (Se AUTO_HEALING_ENABLED=true: reinÃ­cio de pods / ajuste de rÃ©plicaâ”‚
â”‚                                                                                                  â”‚
â”‚  5. ESTABILIZAÃ‡ÃƒO & POST-MORTEM                                                                  â”‚
â”‚     â”œâ”€â”€ Ao atingir Health Score >= 95 sem riscos residuais: sintetiza relatÃ³rio de Post-Mortem  â”‚
â”‚     â””â”€â”€ Envia card com MTTR, Causa Raiz e Action Items ao canal do Slack via Webhook            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## ðŸ”‘ Como Obter e Configurar a Chave Gratuita do Google Gemini (Free Tier)

Para utilizar o modelo do Gemini **100% de graÃ§a (sem necessidade de cartÃ£o de crÃ©dito ou crÃ©ditos prÃ©-pagos)**, siga o passo a passo abaixo:

### ðŸ“‹ Passo a Passo para Gerar a Chave GrÃ¡tis:
1. Acesse o portal do **[Google AI Studio - API Keys](https://aistudio.google.com/app/apikey)**.
2. FaÃ§a login com a sua conta Google.
3. Clique no botÃ£o azul **"Create API key"**.
4. âš ï¸ **IMPORTANTE:** Na janela que abrir, selecione a opÃ§Ã£o **"Create API key in new project"** (Criar chave em um novo projeto).
   > *Criar em um projeto novo garante que a chave fique vinculada ao **Free Tier padrÃ£o**, que oferece **15 requisiÃ§Ãµes por minuto (RPM) gratuitas**, sem conflitar com projetos que possuam faturamento prÃ©-pago esgotado.*
5. Copie a chave gerada (ela comeÃ§a com `AIzaSy...`).

---

## ðŸ¤– Modelos Recomendados & Compatibilidade

A aplicaÃ§Ã£o possui **descoberta dinÃ¢mica de modelos** e suporta a geraÃ§Ã£o mais recente do Gemini:

| Modelo | Status | Finalidade | Cota Free Tier |
| :--- | :--- | :--- | :--- |
| **`gemini-3.6-flash`** | â­ **Recomendado** | Modelo padrÃ£o de alta velocidade e raciocÃ­nio para SRE | 15 RPM GrÃ¡tis |
| **`gemini-3.5-flash-lite`** | Ativo | Modelo ultra rÃ¡pido e leve para microdiagnÃ³sticos | 15 RPM GrÃ¡tis |
| **`gemini-3.1-pro-preview`** | Ativo | AnÃ¡lises complexas e diagnÃ³sticos aprofundados | DisponÃ­vel |

---

## ðŸ›¡ï¸ ResiliÃªncia & Fallback DeterminÃ­stico

Se por qualquer motivo a conexÃ£o com a API do Google falhar (falta de internet, chave expirada ou quota temporariamente excedida), o AIOps Engine **nÃ£o para e nÃ£o quebra**. Ele aciona automaticamente o mÃ³dulo de fallback **`_expert_rulebook_rca`**, que gera o diagnÃ³stico de causa raiz, as aÃ§Ãµes de remediaÃ§Ã£o e o Post-Mortem de forma local e determinÃ­stica, mantendo 100% de disponibilidade.

---

## ðŸ³ Como Rodar Localmente via Docker

### 1. Build da Imagem
```bash
docker build -t aiops-engine apps/aiops-engine
```

### 2. Executar o ContÃªiner com a Chave e Webhook do Slack
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

## ðŸ§ª Como Testar a InteligÃªncia da IA

O AIOps Engine possui endpoints de simulaÃ§Ã£o (*Chaos Engineering*) para validar o comportamento da IA:

### SimulaÃ§Ã£o 1: Memory Leak (PrevenÃ§Ã£o de OOMKill)
```bash
curl -X POST http://localhost:8000/api/simulate-anomaly \
  -H "Content-Type: application/json" \
  -d '{"scenario": "memory_leak"}' | jq .
```

### SimulaÃ§Ã£o 2: Surto de Erros HTTP 5xx
```bash
curl -X POST http://localhost:8000/api/simulate-anomaly \
  -H "Content-Type: application/json" \
  -d '{"scenario": "5xx_surge"}' | jq .
```

### Consultar os DiagnÃ³sticos Gerados pela IA
```bash
curl -s http://localhost:8000/api/insights | jq .
```

---

## ðŸ–¥ï¸ Dashboard Web Interativo

Acesse no navegador:
ðŸ‘‰ **[http://localhost:8000](http://localhost:8000)**

Recursos do Dashboard:
* **Cluster Health Index:** Indicador circular com score de 0 a 100 e gradiente dinÃ¢mico.
* **DiagnÃ³sticos Gemini GenAI:** Cards com RCA, causa raiz, comando sugerido e playbook.
* **Painel de SimulaÃ§Ã£o:** BotÃµes interativos para simular falhas e testar auto-remediaÃ§Ã£o.
* **Log Stream do Loki:** Visualizador em tempo real dos logs de erro do cluster.

---

## ðŸ”Œ Tabela de Endpoints da API REST

| MÃ©todo | Rota | DescriÃ§Ã£o |
| :--- | :--- | :--- |
| `GET` | `/` | Retorna o dashboard web interativo. |
| `GET` | `/health` | Health check nativo da aplicaÃ§Ã£o (K8s probes). |
| `GET` | `/api/status` | Retorna o payload completo de telemetria e estado atual. |
| `GET` | `/api/health-score` | Retorna a nota de saÃºde atual do cluster (0 a 100). |
| `GET` | `/api/predictions` | Lista todas as previsÃµes ativas de esgotamento de memÃ³ria e PVCs. |
| `GET` | `/api/anomalies` | Lista anomalias de latÃªncia e taxas de erro HTTP detectadas. |
| `GET` | `/api/insights` | Retorna os diagnÃ³sticos de RCA gerados pelo Google Gemini. |
| `POST` | `/api/simulate-anomaly` | Dispara cenÃ¡rios de caos sintÃ©ticos (`memory_leak`, `5xx_surge`). |
| `POST` | `/api/analyze-now` | ForÃ§a a execuÃ§Ã£o imediata de um ciclo de anÃ¡lise completo. |
| `POST` | `/api/remediate/{id}` | Dispara manualmente a remediaÃ§Ã£o de um risco especÃ­fico. |

---

## âš™ï¸ VariÃ¡veis de Ambiente

| VariÃ¡vel | PadrÃ£o | DescriÃ§Ã£o |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | `""` | Chave de API do Google Gemini (Google AI Studio). |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Modelo do Gemini para geraÃ§Ã£o de Root Cause Analysis e Post-Mortem. |
| `ANALYSIS_INTERVAL_SECONDS` | `30` | Intervalo em segundos entre ciclos de anÃ¡lise em background. |
| `AUTO_HEALING_ENABLED` | `false` | Habilita aÃ§Ãµes automÃ¡ticas de auto-cura no Kubernetes. |
| `PROMETHEUS_URL` | `http://monitoring-kube-prometheus-prometheus.monitoring-ns:9090` | Endpoint do Prometheus no cluster. |
| `LOKI_URL` | `http://loki.monitoring-ns:3100` | Endpoint do Loki no cluster. |
| `TARGET_NAMESPACES` | `donation-ns,ngo-ns,volunteer-ns,monitoring-ns,kubecost` | Namespaces monitorados pelo motor. |
| `SLACK_WEBHOOK_URL` | `""` | Webhook do Slack para alertas de incidentes e Post-Mortem. |
