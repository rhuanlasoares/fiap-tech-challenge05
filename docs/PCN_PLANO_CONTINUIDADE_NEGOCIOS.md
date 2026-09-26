# 🛡️ Plano de Continuidade de Negócios (PCN) & Disaster Recovery (DR)
### 🌍 Plataforma SolidaryTech — Resiliência Operacional, Zero-Downtime e Tolerância a Desastres
**Documento Executivo de Engenharia, SRE e Gestão de Continuidade de Negócios**

---

## 1. Sumário Executivo & Objetivos de Continuidade

A **SolidaryTech** é a espinha dorsal digital para captação de recursos, gestão de voluntários e assistência humanitária a milhares de ONGs no Brasil. Durante catástrofes humanitárias e campanhas de alta visibilidade, picos massivos de tráfego ocorrem simultaneamente à exigência inegociável de disponibilidade contínua.

Este **Plano de Continuidade de Negócios (PCN)** e **Estratégia de Disaster Recovery (DR)** estabelece os padrões de engenharia, arquitetura de dados e procedimentos operacionais necessários para cobrir **todas as possibilidades de indisponibilidade regional e zonal**:
1. **RPO = 0 (Zero Data Loss) no Hot Path**: Nenhuma doação financeira ou transação é perdida, mesmo em caso de falha isolada de serviço, congelamento de escrita, failover de banco ou blackout regional total.
2. **Isolamento Fino de Falhas (Failure Domain Isolation)**: Capacidade de responder a falhas parciais (ex: apenas o GKE caiu, ou apenas o Cloud SQL caiu) sem acionar migrações desnecessárias ou romper a topologia de banco de dados.
3. **Preservação Integral do Estado do Terraform**: Eliminação de drifts e conflitos de estado no Terraform através de diretivas de ciclo de vida (`ignore_changes`).
4. **Operação Self-Service Unificada**: Qualquer engenheiro ou operador On-Call pode disparar failovers granulares e switchbacks com 1 clique via GitHub Actions ou CLI padronizado.

---

## 2. Matriz Completa de Cenários e Granularidade de Falhas

A engenharia de SRE da SolidaryTech classifica e responde a 5 cenários distintos de falha na região `southamerica-east1` (São Paulo):

| Cenário de Incidente | Componente Afetado | Ação no GKE | Ação no Cloud SQL | Ação no Velero | RPO | RTO Estimado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Cenário 1: Falha Zonal (HA)** | 1 Zona de SP (ex: `southamerica-east1-a`) | Nós em `b`/`c` assumem pods via `TopologySpreadConstraints` | Failover Zonal automático (`gcloud sql instances failover`) mantendo storage e IP | Não acionado | **0s** | **< 60 segundos** |
| **Cenário 2: Falha Isolada de GKE em SP** | Apenas o Control Plane / Nós do GKE em SP (Cloud SQL 100% online em SP) | Ativar `gke-useast` no Terraform; ArgoCD reconcilia manifests | **NENHUMA ALTERAÇÃO!** Cloud SQL Master mantido em SP. `gke-useast` conecta via VPC Global | Restaura secrets de runtime e PVCs via bucket GCS | **0s** | **< 5 minutos** |
| **Cenário 3: Falha Isolada de Cloud SQL em SP** | Apenas o banco de dados em SP (`gke-samerica` 100% saudável em SP) | **NENHUMA ALTERAÇÃO!** `gke-samerica` permanece ativo em SP. Re-aponta proxy para `us-east1` | Promover réplica `sql-rhuan-*-replica` em `us-east1` | Não acionado | **< 5s** (ou 0s com buffer SQS) | **< 2 minutos** |
| **Cenário 4: Falha Isolada de Storage (GCS) em SP** | GCS temporariamente degradado em SP (GKE e DB operando normalmente) | Workloads continuam operando normalmente sem impacto | Nenhuma alteração | Backups usam bucket secundário / multi-region | **0s** | **0s (Sem impacto no usuário)** |
| **Cenário 5: Blackout Regional Total em SP** | Colapso total de SP (GKE, Cloud SQL, Rede e Storage inacessíveis) | Ativar `gke-useast` via Terraform + ArgoCD | Promover réplicas `sql-rhuan-*-replica` como novos Masters em `us-east1` | Restaura estado a partir de bucket Multi-Region | **0s** (com buffer SQS) | **< 8 minutos** |

---

## 3. Detalhamento dos Cenários Granulares

### 3.1. Cenário 2: Falha Isolada do Serviço do GKE em São Paulo
* **Diagnóstico**: O cluster `gke-samerica` está inacessível (ex: incidente na API do Kubernetes ou falha nos node pools de SP), porém o Cloud SQL (`sql-rhuan-donation` e `sql-rhuan-ngo`) e a rede VPC continuam 100% saudáveis em São Paulo.
* **Decisão Arquitetural Crucial**: **NÃO promover a réplica do Cloud SQL.**
  - A VPC `vpc-rhuan` é uma rede global do Google Cloud. As sub-redes `subnet-gke-sa` e `subnet-gke-us` comunicam-se nativamente através do backbone privado de fibra da Google.
  - O cluster `gke-useast` na Virgínia conecta-se diretamente ao Cloud SQL Master em São Paulo via Private Services Access (PSA) ou Cloud SQL Auth Proxy.
  - A latência interregional aumenta (~110ms), mas o sistema permanece online e **nenhuma migração de banco é exigida**, eliminando riscos de inconsistência de dados.
* **Restauração via Velero**: Como o Cloud Storage em São Paulo está operacional, o Velero instalado em `gke-useast` acessa o bucket `gcs-velero-bucket-solidary-tech-rh` e restaura namespaces e PVCs em menos de 3 minutos.
* **Comutação de Tráfego**: O Gateway API / Cloud DNS atualiza o apontamento para o IP do Load Balancer em `us-east1`.

### 3.2. Cenário 3: Falha Isolada do Cloud SQL em São Paulo
* **Diagnóstico**: O GKE `gke-samerica` está saudável, mas a instância primária do Cloud SQL sofreu corrupção de volume ou falha regional intransponível no serviço gerenciado.
* **Decisão Arquitetural**: **NÃO recriar o cluster GKE nos EUA.**
  - Promove-se a réplica de leitura `sql-rhuan-*-replica` em `us-east1` para master independente.
  - Os pods em execução em São Paulo atualizam o Secret `CLOUDSQL_CONNECTION_NAME` apontando para `naconfeitaria:us-east1:sql-rhuan-*-replica` e reiniciam graciosamente.
  - Os pods continuam atendendo usuários em São Paulo, gravando no banco promovido na Virgínia via VPC global.

### 3.3. Cenário 5: Blackout Regional Total (Desastre Completo)
* **Diagnóstico**: Desconexão total da região `southamerica-east1`.
* **Ação Coordenada**:
  1. Ativar `gke-useast` no Terraform (`should_be_create = true`).
  2. Promover as réplicas de Cloud SQL em `us-east1`.
  3. Velero restaura os namespaces a partir do backup replicado.
  4. ArgoCD reconcilia manifests de aplicação.
  5. Tráfego público é roteado para o Gateway API na Virgínia.
  6. Toda a SolidaryTech opera de forma 100% autocontida dentro de `us-east1`.

---

## 4. Solução do Dilema do Terraform State

### O Desafio
No Terraform tradicional, uma réplica de leitura possui `master_instance_name = google_sql_database_instance.master.name`. Ao promover a réplica (`promote-replica`), o GCP apaga essa referência. No próximo `terraform apply`, o Terraform tentaria **destruir o banco promovido** com todos os dados da produção!

### A Blindagem Implementada
No arquivo [iac/terraform/modules/cloud_sql/main.tf](file:///iac/terraform/modules/cloud_sql/main.tf):
```hcl
resource "google_sql_database_instance" "replica" {
  count                = var.enable_cross_region_replica ? 1 : 0
  name                 = "${var.instance_name}-replica"
  master_instance_name = google_sql_database_instance.master.name
  region               = var.replica_region

  lifecycle {
    ignore_changes = [
      master_instance_name,
      settings[0].maintenance_window,
      settings[0].disk_size
    ]
  }
}
```
* **Resultado**: O Terraform ignora se a réplica perdeu o vínculo de replicação após a promoção. Nenhuma execução automatizada de CI/CD destruirá a base de dados de contingência.

---

## 5. Garantia de Zero Data Loss em In-Flight Writes (Aplicações)

Durante qualquer janela de corte (*cutover*), congelamento de banco para exportação ou chaveamento de proxy, novas requisições continuam chegando dos doadores e parceiros:

### 5.1. `donation-service` (Go) — Fallback para AWS SQS + Auto-Drain Worker

Quando o Cloud SQL Master sofre indisponibilidade (queda zonal, failover primário/réplica, throttling severo ou comutação para *read-only*), o microsserviço ativa proteção contra perda de dados sem interromper a jornada do doador:

```text
       POST /donations
Doador ───────────────> [donation-service (Go)] ──(Falha no SQL)──> [AWS SQS (Queue)]
       <── 202 Accepted ──────┘                                            │
                                                                           │ (Health Ping OK a cada 10s)
                                                                           ▼
                               [PostgreSQL / Cloud SQL] <── Auto-Drain Worker
                               (Commit com Sucesso) ────> Deleta mensagem SQS (RPO = 0)
```

* **Interceptação de Falhas e Read-Only (`apps/donation-service/main.go:L251-280`)**: O serviço intercepta falhas de rede, timeouts e códigos de erro de banco (ex: `57014`, `25006`).
* **Buffer Durável Multi-AZ em SQS**: Em vez de retornar HTTP 500, a doação é marcada como `PENDING_BUFFERED` e enviada à fila durável **AWS SQS** via `a.sendNotificationEvent()`. O doador recebe instantaneamente `HTTP 202 Accepted` com `status: QUEUED_FOR_PROCESSING` e o `donation.id`.
* **Worker de Drenagem Contínua (`apps/donation-service/main.go:L434-491`)**: A goroutine `startSQSBufferDrainWorker(ctx)` roda em loop infinito com ticker de 10s. Executa `a.DB.PingContext(ctx)`. Quando o PostgreSQL normaliza, consome mensagens (`ReceiveMessageWithContext`), persiste via SQL `INSERT` com status `APPROVED` e, **somente após a confirmação do commit**, executa `DeleteMessageWithContext` no SQS.
* **RPO Garantido**: **Rigorosamente 0 segundos (Zero Data Loss)**, pois nenhuma mensagem é removida do SQS até que a persistência relacional esteja concluída.

### 5.2. `ngo-service` (Python) — Exponential Backoff + Retries
* **Tratamento de Exceções**: O código captura `psycopg2.errors.ReadOnlySqlTransaction` e `psycopg2.OperationalError`.
* **Retry Loop**: Executa até 3 tentativas com backoff exponencial (1s, 2s, 4s), expurgando conexões quebradas do pool para restabelecer o handshake com o Cloud SQL Auth Proxy.
* **Fallback**: Durante janelas de freeze para export, responde com buffer em `HTTP 202 Accepted`.

---

## 6. Procedimentos Modulares de Retorno ao Padrão (Switchback)

O retorno à normalidade deve ser tão granular quanto o failover, evitando desperdício de tempo e movimentações desnecessárias de dados:

### 6.1. Switchback do Cenário 2 (Apenas GKE foi migrado)
Como o banco de dados **sempre permaneceu em São Paulo**:
1. Validar saúde e conectividade do cluster `gke-samerica`.
2. Comutar o DNS / Gateway API de volta para o IP do Load Balancer em São Paulo.
3. Desativar `gke-useast` no Terraform (`should_be_create = false`). Os nós nos EUA são destruídos, **zerando os custos de nós ociosos (FinOps)**.
4. **Vantagem**: Nenhuma exportação ou importação de banco de dados é necessária!

### 6.2. Switchback do Cenário 3 (Apenas Cloud SQL foi migrado)
1. Congelar escritas na réplica de DR: `ALTER DATABASE donation_db SET default_transaction_read_only = on;` (Aplicações ativam fallback de SQS automaticamente).
2. Exportar delta atualizado para Cloud Storage: `gcloud sql export sql sql-rhuan-*-replica gs://...`.
3. Importar delta no banco primário em São Paulo: `gcloud sql import sql sql-rhuan-* gs://...`.
4. Re-apontar o Secret do Cloud SQL Proxy no `gke-samerica` para São Paulo.
5. O Auto-Drain Worker descarrega as doações represadas no SQS para o banco primário.

### 6.3. Switchback do Cenário 5 (Desastre Total)
1. Executar o Switchback de Banco (Passo 6.2).
2. Executar o Switchback de GKE (Passo 6.1).
3. Recriar a réplica de contingência em `us-east1` via IaC para manter o PCN ativo.

---

## 7. Automação 1-Click via GitHub Actions & CLI

### 7.1. Workflow no GitHub Actions (`.github/workflows/disaster-recovery.yaml`)
Disparado via `workflow_dispatch` na aba Actions do repositório:
* **`action`**:
  * `status`: Diagnóstico completo de saúde dos clusters e bancos.
  * `ha-failover`: Failover zonal de banco em SP (< 60s).
  * `cross-region-sql-failover`: Promove banco nos EUA (mantém GKE em SP).
  * `gke-failover`: Ativa GKE nos EUA (mantém banco em SP).
  * `full-regional-failover`: Ativa GKE + Banco nos EUA (Blackout total).
  * `switchback-sql`: Retorna banco para SP com Zero Data Loss.
  * `switchback-gke`: Retorna tráfego para GKE em SP e desliga nós nos EUA.
  * `full-regional-switchback`: Retorno coordenado de tudo para SP.
* **`dry_run`**: `true` (padrão) para simulação segura sem alteração de recursos.
* **Segurança**: WIF (Workload Identity Federation) sem chaves estáticas e alertas automáticos no Slack (`#incidentes-sre`).

### 7.2. CLI Unificado (`scripts/disaster-recovery-manager.sh`)
```bash
# 1. Auditoria e status completo
bash scripts/disaster-recovery-manager.sh -a status

# 2. Simular failover de GKE (Dry-Run)
bash scripts/disaster-recovery-manager.sh -a gke-failover --dry-run

# 3. Executar failover isolado de GKE
bash scripts/disaster-recovery-manager.sh -a gke-failover

# 4. Executar failover isolado de Cloud SQL
bash scripts/disaster-recovery-manager.sh -a cross-region-sql-failover

# 5. Executar failover total de desastre
bash scripts/disaster-recovery-manager.sh -a full-regional-failover

# 6. Executar switchback total
bash scripts/disaster-recovery-manager.sh -a full-regional-switchback
```

---

---

## 8. Watchdog Autônomo & Auto-Trigger via GCP Status Checker

Para fechar o elo de automação e atingir **MTTD (Mean Time to Detect) e MTTR (Mean Time to Recovery) mínimos**, o **`gcp-status-checker`** foi desenhado como um **Watchdog Inteligente de Nuvem**:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│              FLUXO OPERACIONAL DO WATCHDOG AUTÔNOMO (GCP STATUS CHECKER)                         │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘

   1. EXECUÇÃO EXTERNA INDEPENDENTE (A cada 5 minutos no GitHub Actions)
      └──> Roda fora do cluster GKE de São Paulo, imune a apagões regionais do GCP.
      └──> Autentica no GCP via Workload Identity Federation (WIF).

   2. VARREDURA DO FEED OFICIAL DA GOOGLE CLOUD
      └──> Monitora 'Cloud SQL' e 'Google Kubernetes Engine' na região 'southamerica-east1'.

   3. GESTÃO DE ESTADO & HYSTERESIS NO GOOGLE CLOUD STORAGE (GCS)
      └──> Lê e grava o estado em 'gs://gcs-velero-bucket-solidary-tech-rh/gcp-status-checker-state.json'.
      └──> REGRA DE CONFIRMAÇÃO RÁPIDA (FAST-CONFIRMATION LOOP):
           • Em tempo de paz: checagem leve em < 5 segundos.
           • Se detectar instabilidade na 1ª checagem: NÃO espera 15 minutos!
             Entra em loop imediato de 2 re-verificações com intervalo de 30 segundos.
           • Em ~65 segundos confirma 3x consecutivas a falha e dispara o Failover!
           • No retorno ao padrão: confirma 3x a cada 30 segundos e dispara o Switchback!

   4. MATRIZ DE DECISÃO CIRÚRGICA
      ├──> Apenas Cloud SQL falhou 3x ──▶ Ação: cross-region-sql-failover
      ├──> Apenas GKE falhou 3x       ──▶ Ação: gke-failover
      └──> Ambos falharam 3x          ──▶ Ação: full-regional-failover

   5. SEGURANÇA SRE & DISPATCH DE AÇÃO
      ├──> Modo Automático (AUTO_TRIGGER_DR=true & REQUIRE_MANUAL_CONFIRMATION=false):
      │    Dispara a REST API do GitHub Actions (workflow_dispatch) e notifica o Slack.
      └──> Modo com Validação Manual (Padrão de Segurança):
           Dispara card de ALERTA CRÍTICO no Slack com link de 1-clique para aprovação do time On-Call.
```

### 8.1. Por que o Watchdog roda no GitHub Actions e não no Kubernetes?
* **O Risco Clássico de SRE**: Se o `gcp-status-checker` rodasse dentro do GKE em São Paulo e o próprio cluster sofresse um colapso, o container morreria junto com o cluster e nunca conseguiria avisar ninguém.
* **A Arquitetura Adotada**: O workflow `.github/workflows/gcp-status-checker.yaml` executa em runners geograficamente independentes do GitHub Actions. Mesmo que a América do Sul fique 100% inacessível, o watchdog detecta o status oficial da GCP e orquestra a contingência nos EUA.

### 8.2. Parâmetros de Configuração do Watchdog

| Variável de Ambiente | Descrição | Padrão |
| :--- | :--- | :--- |
| `FAST_CONFIRMATION_ENABLED` | Ativa re-verificações imediatas no mesmo job ao detectar anomalia | `true` |
| `FAST_CONFIRMATION_INTERVAL_SECONDS` | Intervalo de espera entre as 3 confirmações rápidas | `30` segundos |
| `CONSECUTIVE_OUTAGE_THRESHOLD` | Quantidade de verificações com falha antes de decidir por failover | `3` |
| `CONSECUTIVE_HEALTHY_THRESHOLD` | Quantidade de verificações estáveis antes de autorizar o switchback | `3` |
| `AUTO_TRIGGER_DR` | Se `true`, aciona a pipeline de DR sem esperar aprovação | `false` (Segurança) |
| `REQUIRE_MANUAL_CONFIRMATION` | Exige validação humana do operador via link no Slack | `true` |
| `GCS_STATE_BUCKET` | Bucket Cloud Storage para persistir o histórico de estados | `gcs-velero-bucket-solidary-tech-rh` |
| `GCS_STATE_FILE` | Nome do arquivo JSON de estado no GCS | `gcp-status-checker-state.json` |

---

## 9. Governança e Auditoria

1. **Game Days Regulares**: Simulações controladas semestrais utilizando o CLI com `--dry-run` e injeção de falhas em staging.
2. **Rastreabilidade**: Todos os eventos de failover e switchback são logados no Cloud Audit Logs e no histórico de execuções do GitHub Actions.
3. **Conformidade**: Aderente aos padrões de resiliência ISO 22301 e aos preceitos de disponibilidade contínua e integridade da LGPD.
