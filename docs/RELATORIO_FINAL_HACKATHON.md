# 🎓 Relatório Final de Entrega — Hackathon Tech Challenge (Fase 5)
### 🌍 Plataforma SolidaryTech: Resiliência, Self-Healing, SRE, FinOps & Disaster Recovery
**Pós-Graduação em Cloud & DevOps / SRE — FIAP**

---

## 👥 Identificação do Grupo & Links Oficiais

| Campo | Informação / Link |
| :--- | :--- |
| **Integrantes (Nome / RM)** | Rhuan (RM: 358485) |
| **Repositório de Código Fonte** | [https://github.com/rhuanlasoares/fiap-tech-challenge05](https://github.com/rhuanlasoares/fiap-tech-challenge05) |
| **Link do Vídeo de Apresentação** | *(Inserir link do YouTube / Loom de até 20 minutos)* |

---

## 1. 📊 Seção SRE: Definição Formal de SLI, SLO e SLA de Doações

A confiabilidade da plataforma SolidaryTech é estruturada na regra fundamental do Google SRE:

$$\mathbf{SLA} < \mathbf{SLO} \le \mathbf{SLI}_{\text{atual}}$$

### 1.1 SLIs e SLOs do Serviço de Doações (`donation-service` - Caminho Crítico)
1. **SLI de Disponibilidade (Success Rate)**:
   $$\text{SLI}_{\text{Disponibilidade}} = \frac{\text{Requisições HTTP } \neq 5xx}{\text{Total de Requisições HTTP}} \times 100\%$$
   - **SLO Alvo (Interno)**: **99.90%** em janela móvel de 30 dias.
   - **SLA Prometido (Contratual)**: **99.50%**.
   - **Error Budget**: **43,20 minutos de erro tolerados por mês** ($100\% - 99.90\% = 0.10\%$).

2. **SLI de Latência (Response Time)**:
   $$\text{SLI}_{\text{Latência}} = \frac{\text{Requisições com Latência } < 250\text{ms}}{\text{Total de Requisições}} \times 100\%$$
   - **SLO Alvo (Interno)**: **99.90%** das requisições atendidas abaixo de 250ms (p95).

### 1.2 Redução Ativa de MTTR com Observabilidade e Auto-Healing
O AIOps Engine coleta métricas a cada 30 segundos, detecta vazamentos lineares de memória e executa reinicializações preventivas antes do Pod sofrer `OOMKilled`. Isso reduz o **MTTR (Mean Time to Recovery) de ~15 minutos (tempo de intervenção humana) para $< 2$ minutos (automático)**.

---

## 2. 💰 Seção FinOps: Análise de Custos Mensais (Forecast) & Tagging

### 2.1 Política e Evidência de Tagging no Terraform
Todos os recursos de nuvem (GKE, Cloud SQL, Buckets GCS, Artifact Registry) contêm tags padronizadas:
- `Project`: `solidary-tech`
- `Environment`: `production`
- `CostCenter`: `ngo-core`
- `Terraform`: `true`

### 2.2 Projeção de Custos Mensais (Forecast)
* **Custo Estimado sem Otimização (On-Demand)**: \$139.26 / mês.
* **Custo Otimizado com Práticas FinOps (SolidaryTech)**: **\$60.93 / mês**.
* **Economia Gerada**: **56,2% de economia mensal**.
* **Recomendações Práticas Aplicadas**:
  1. Uso de **GKE Spot Node Pools** com PDB (~70% de economia em computação).
  2. Cloud SQL `db-f1-micro` ajustado para a demanda real.
  3. Desacoplamento assíncrono de doações com **AWS SQS Free Tier**.
  4. Detecção de ociosidade e monitoramento de custos com **Kubecost**.

---

## 3. 🛡️ Seção Segurança & Disaster Recovery: Resumo do PCN (RTO / RPO)

### 3.1 Métricas de Continuidade
* **RPO (Recovery Point Objective)**: **$< 5$ segundos** para o banco de dados de doações via réplica assíncrona cross-region em `us-east1`.
* **RTO (Recovery Time Objective)**: **$< 2$ minutos** para promoção de réplica do Cloud SQL e **$< 8$ minutos** para ativação do cluster secundário `gke-useast`.

### 3.2 Estratégia de DR Prática (Ativo-Passivo Warm Standby)
A infraestrutura está 100% modularizada no Terraform. Em caso de blackout regional em São Paulo, o cluster secundário em `us-east1` é ativado alterando uma única variável (`should_be_create = true`), o ArgoCD sincroniza todas as aplicações do Git e a réplica do Cloud SQL é promovida a Master com 1 comando.

---

## 4. 🤖 Seção ITSM & AIOps: Desenho do Ciclo de Vida de Incidentes

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               CICLO DE VIDA DO INCIDENTE NA SOLIDARYTECH                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│  1. DETECÇÃO ANTECIPADA (AIOps Engine)                                                           │
│     ├── Machine Learning identifica anomalia de latência ou Memory Leak                          │
│     └── Disparo de alerta com severidade no Slack via Webhook                                    │
│                                                                                                  │
│  2. DIAGNÓSTICO INTELIGENTE COM GENAI                                                            │
│     └── Google Gemini analisa [Métricas + Logs do Loki + Eventos K8s] e gera Causa Raiz (RCA)    │
│                                                                                                  │
│  3. AUTO-HEALING / REMEDIAÇÃO SEGURA                                                             │
│     └── Rollout Restart preventivo disparado no Kubernetes para normalizar a aplicação           │
│                                                                                                  │
│  4. ESTABILIZAÇÃO & POST-MORTEM NO SLACK                                                         │
│     ├── Cluster atinge Health Score >= 95                                                        │
│     └── Envio automatizado de relatório de Post-Mortem com MTTR, Causa Raiz e Action Items       │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```\n