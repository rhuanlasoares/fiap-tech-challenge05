# 💳 donation-service (Golang)

Microsserviço de alta performance e resiliência responsável pelo processamento de doações financeiras da plataforma **SolidaryTech**.

---

## 🛠️ Tecnologias e Stack
* **Linguagem**: Go 1.22
* **Banco Primário**: PostgreSQL 15 (Google Cloud SQL)
* **Buffer de Contingência / Mensageria**: AWS SQS (Fila Durável Multi-AZ)
* **Observabilidade**: OpenTelemetry (Métricas, Logs e Tracing Distribuído) + Prometheus

---

## 🛡️ Arquitetura de Resiliência: O que acontece se o Cloud SQL parar?

Em cenários normais, o `donation-service` persiste as doações diretamente no Cloud SQL e publica um evento assíncrono para notificação.

### Cenário de Indisponibilidade do Banco de Dados
Se o Cloud SQL sofrer queda zonal, manutenção programada, failover primário/secundário ou lentidão:

```text
 ┌──────────────┐       POST /donations
 │  Doador /    │ ───────────────────────────┐
 │  Gateway API │ <────────────────────────┐ │
 └──────────────┘   HTTP 202 Accepted      │ │
                   (QUEUED_FOR_PROCESSING) │ │
                                           ▼ ▼
                            ┌─────────────────────────────────┐
                            │    donation-service (Golang)    │
                            └─────────────────────────────────┘
                                     │               │
                     1. INSERT Falha │               │ 2. Fallback de
                   (timeout/connpool)│               │    Emergência
                                     ▼               ▼
                          ┌─────────────────┐   ┌───────────────────────────┐
                          │    Cloud SQL    │   │          AWS SQS          │
                          │   (PostgreSQL)  │   │  (Fila Durável Multi-AZ)  │
                          │   [OFFLINE ⚠️]   │   │  Status: PENDING_BUFFERED │
                          └─────────────────┘   └───────────────────────────┘
                                     ▲                       │
                                     │                       │
                                     │ 3. Ping OK (10s loop) │
                                     └───────────────────────┘
                                     startSQSBufferDrainWorker
                                   (Drena fila -> INSERT -> SQS Delete)
```

1. **Fallback Automático (Zero HTTP 500)**:
   * O erro de conexão/escrita com o PostgreSQL é capturado em `apps/donation-service/main.go` (L251-280).
   * O status da doação é ajustado para `PENDING_BUFFERED`.
   * A doação é imediatamente enfileirada no **AWS SQS**.
   * A API responde ao doador com **`HTTP 202 Accepted`** (`QUEUED_FOR_PROCESSING`) contendo o ID gerado da doação.
   * **Nenhuma doação é rejeitada ou perdida.**

2. **Drenagem Automática com RPO = 0 (`startSQSBufferDrainWorker`)**:
   * Uma goroutine em background testa a conexão com o banco a cada 10 segundos (`DB.PingContext`).
   * Quando o banco volta à vida, o worker consome as doações represadas no SQS (`ReceiveMessageWithContext`).
   * Insere os registros no PostgreSQL (`INSERT INTO donations ... STATUS = 'APPROVED'`).
   * **Atomicidade**: O `DeleteMessageWithContext` no SQS só ocorre **após** o commit bem-sucedido no PostgreSQL. Se o banco cair no meio do processamento, a mensagem reaparece no SQS após o timeout de visibilidade.
   * **Garantia**: **RPO = 0** (Zero Data Loss).

---

## 🚀 Endpoints Principais

| Método | Rota | Descrição | Status de Sucesso |
| :--- | :--- | :--- | :--- |
| `POST` | `/donations` | Registra uma nova doação (com fallback para SQS se DB estiver off) | `201 Created` (se DB OK) ou `202 Accepted` (se em Buffer SQS) |
| `GET` | `/donations` | Lista as últimas doações registradas | `200 OK` |
| `GET` | `/health` | Checagem de integridade (Liveness/Readiness probe) | `200 OK` |
| `GET` | `/metrics` | Métricas Prometheus (latência, contadores de doações) | `200 OK` |
