# 🛡️ Plano de Continuidade de Negócios (PCN) & Disaster Recovery (DR)
### 🌍 Plataforma SolidaryTech — Resiliência Operacional e Tolerância a Desastres
**Documento Executivo de Engenharia e Gestão de Riscos (SRE / FinOps / Segurança)**

---

## 1. Sumário Executivo & Objetivos

A **SolidaryTech** é uma plataforma crítica do terceiro setor responsável por conectar milhares de doadores, voluntários e organizações não-governamentais (ONGs) em todo o território nacional. Em momentos de grandes campanhas ou desastres humanitários, a plataforma experimenta picos imprevistos de tráfego.

Este **Plano de Continuidade de Negócios (PCN)** tem como objetivo principal garantir que:
1. **As doações financeiras não sofram interrupção**, mesmo sob falhas catastróficas em datacenters regionais.
2. **A perda de dados cadastrais e transacionais seja praticamente nula**.
3. **O tempo de recuperação de serviços (*Downtime*) seja estritamente controlado** e aderente aos SLAs contratuais acordados com as ONGs parceiras.

---

## 2. Análise de Impacto no Negócio (BIA - Business Impact Analysis)

A tabela abaixo classifica a criticidade dos serviços e o impacto direto de sua indisponibilidade:

| Nível de Criticidade | Microsserviço / Componente | Função de Negócio | Impacto de Indisponibilidade |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Crítico / Hot Path)** | `donation-service` | Ingestão e processamento de doações | **Crítico**: Perda financeira direta para ONGs e quebra de confiança dos doadores. |
| **Tier 1 (Crítico / Hot Path)** | `Cloud SQL (Master)` | Persistência transacional das doações | **Crítico**: Impossibilidade de registro e confirmação de pagamento. |
| **Tier 2 (Alto Impacto)** | `ngo-service` | Cadastro e validação de ONGs | **Alto**: Bloqueio de novas adesões e consultas cadastrais. |
| **Tier 2 (Alto Impacto)** | `volunteer-service` | Matching de vagas de voluntariado | **Médio/Alto**: Atraso no engajamento de voluntários. |
| **Tier 3 (Suporte / Ops)** | `gcp-status-checker` | Monitoramento proativo de saúde da nuvem | **Baixo**: Perda temporária de telemetria externa. |
| **Tier 3 (Suporte / Ops)** | `aiops-engine` | Predição de falhas e Auto-Healing | **Médio**: Retorno à operação reativa manual da equipe On-Call. |

---

## 3. Métricas Críticas de Continuidade (RPO e RTO)

Os alvos de recuperação foram dimensionados com base no impacto financeiro e na viabilidade técnica:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ALVOS DE RECUPERAÇÃO DA SOLIDARYTECH                          │
├───────────────────────────────────────────────────┬─────────────────────────────────────────────┤
│ RPO (Recovery Point Objective)                    │ RTO (Recovery Time Objective)               │
│ Tolerância Máxima de Perda de Dados               │ Tempo Máximo para Restabelecimento do Ar    │
├───────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ • Dados de Doações (Hot Path): < 5 segundos       │ • Failover de Banco de Dados: < 2 minutos   │
│ • Dados Cadastrais de ONGs/Voluntários: < 1 hora  │ • Failover de Cluster GKE (DR): < 8 minutos │
│ • Manifestos K8s & Configurações: 0 segundos      │ • Restauração de Namespace (Velero): < 5 min│
│   (Versionados via GitOps no repositório)         │                                             │
└───────────────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 4. Matriz de Cenários de Desastre & Estratégia de Resposta

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             TOPOLOGIA DE DISASTER RECOVERY MULTI-REGIÃO                          │
├───────────────────────────────────────────────────┬──────────────────────────────────────────────┤
│ REGIÃO PRIMÁRIA (southamerica-east1)              │ REGIÃO SECUNDÁRIA / DR (us-east1)            │
├───────────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ • GKE Primário: gke-samerica (should_be_create=T) │ • GKE Standby: gke-useast (should_be_create=F│
│ • Cloud SQL Master: sql-rhuan-ngo / donation      │ • Cloud SQL Replica: Cross-Region (RPO < 5s) │
│ • Ingress / Gateway API: solidary-tech.nip.io     │ • Backup Bucket GCS: gcs-velero-bucket       │
└───────────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

### Cenário 1: Falha Física de Pods ou Nós do Kubernetes (GKE)
* **Causa Provável**: Esgotamento de memória do nó, falha de hardware na zona de disponibilidade do GCP.
* **Estratégia de Mitigação**:
  - `PodDisruptionBudget (PDB)` configurado com `minAvailable: 1` para garantir disponibilidade ininterrupta durante drenagem de nós.
  - `TopologySpreadConstraints` distribuindo réplicas entre diferentes zonas (`southamerica-east1-a`, `b`, `c`).
  - `HorizontalPodAutoscaler (HPA)` e `KEDA` escalonando réplicas automaticamente com base em CPU e tamanho da fila SQS.
* **RTO**: **0 segundos** (Zero Downtime para o usuário final).
* **RPO**: **0 segundos**.

### Cenário 2: Corrupção Lógica de Aplicação ou Namespace Deletado por Engano
* **Causa Provável**: Erro humano na exclusão de um namespace ou falha de migração de banco de dados.
* **Estratégia de Mitigação**:
  - Restauração pontual de manifests e Persistent Volumes através do **Velero**:
    ```bash
    velero backup create backup-solidary-daily --include-namespaces donation-ns,ngo-ns,volunteer-ns
    velero restore create --from-backup backup-solidary-daily
    ```
* **RTO**: **$< 5$ minutos**.
* **RPO**: **$< 1$ hora** (frequência do agendamento de snapshots do Velero).

### Cenário 3: Queda da Instância Primária do Cloud SQL Master
* **Causa Provável**: Falha de infraestrutura no datacenter regional do Cloud SQL em São Paulo.
* **Estratégia de Mitigação**:
  - O banco de dados possui réplica de leitura cross-region provisionada em `us-east1` (`enable_cross_region_replica = true`).
  - Execução do comando de promoção imediata da réplica para Master:
    ```bash
    gcloud sql instances promote-replica sql-rhuan-donation-replica --project=ces-igniteprogram
    ```
* **RTO**: **$< 2$ minutos**.
* **RPO**: **$< 5$ segundos** (tempo de sincronização assíncrona contínua do WAL do PostgreSQL).

### Cenário 4: Desastre Regional Completo (Blackout na América do Sul)
* **Causa Provável**: Indisponibilidade total de conectividade ou falha sistêmica na região `southamerica-east1`.
* **Estratégia de Mitigação (Infraestrutura Ativo-Passivo Warm Standby)**:
  1. Alterar a variável de controle no Terraform (`iac/terraform/terraform.tfvars`):
     ```hcl
     gke = {
       southamerica = { cluster_name = "gke-samerica", should_be_create = false }
       useast       = { cluster_name = "gke-useast",   should_be_create = true } # Ativação sob demanda
     }
     ```
  2. Executar `terraform apply` para subir o cluster `gke-useast` na sub-rede `subnet-gke-us`.
  3. O **ArgoCD** reconcilia automaticamente todo o ecossistema de microsserviços a partir do repositório Git.
  4. Promover a réplica do Cloud SQL em `us-east1`.
* **RTO**: **$< 8$ minutos**.
* **RPO**: **$< 5$ segundos**.

---

## 5. Estrutura de Gestão de Crise & Comunicação (ITSM)

1. **Detecção e Alerta**: O AIOps Engine identifica a anomalia via telemetria e dispara notificação no canal `#incidentes-sre` do Slack.
2. **Declaração de Incidente Maior**: O Tech Lead On-Call avalia o impacto e, se a indisponibilidade ultrapassar 5 minutos, convoca a sala de crise.
3. **Comunicação aos Stakeholders**:
   - Status Page atualizada a cada 15 minutos.
   - Mensagem direcionada às diretorias das ONGs afetadas.
4. **Resolução e Post-Mortem**:
   - Assim que o Health Score retornar a 100/100, o AIOps Engine gera o relatório de Post-Mortem automaticamente no Slack com o MTTR consolidado e as ações corretivas.

---

## 6. Procedimento de Teste Periódico de DR

Para validar a prontidão do PCN, executa-se semestralmente o script de teste de caos e Disaster Recovery:
```bash
./scripts/test-disaster-recovery.sh
```
O teste valida a replicação de banco de dados, o estado dos backups no bucket `gcs-velero-bucket-solidary-tech-rh` e a saúde dos nós do GKE.\n