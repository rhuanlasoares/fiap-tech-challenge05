# 🎬 Roteiro de Demonstração ao Vivo: Resiliência, Self-Healing e Disaster Recovery (Tech Challenge 5)

Este roteiro foi estruturado como uma **narrativa de apresentação executiva e técnica (Storyline de SRE)**, dividida em **6 Atos práticos**. Cada ato possui os comandos exatos, o que falar e o que mostrar na tela (Grafana, Argo CD, GCP Console, New Relic e Slack).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MAPA DA SUA APRESENTAÇÃO AO VIVO                                │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ 1. Linha de Base         │ 📊 Health Check, Grafana (4 Golden Signals), New Relic AIM  │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 2. Caos no Kubernetes    │ 💥 Queda de Node (Drenagem) ➔ PDB & Zero Downtime           │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 3. Self-Healing Release  │ 🚨 Deploy Quebrado ➔ Argo Rollouts + Auto-Rollback          │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 4. Detecção de Desastre  │ 📡 GCP Status Checker ➔ Simulação de Incidente ➔ Alerta     │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 5. DR de Banco de Dados  │ 🗄️ Queda do Cloud SQL Master ➔ Promoção da Réplica          │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 6. DR de Cluster         │ 💾 Velero ➔ Deleção de Namespace ➔ Restauração via GCS      │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 🎭 ATO 1: O Estado Saudável (Baseline & Observabilidade)

> **🎯 Objetivo:** Mostrar aos avaliadores que a plataforma está operando normalmente com telemetria ativa, Golden Signals no Grafana e rastreamento no New Relic.

### 🖥️ O que mostrar na tela:
1. Dashboard do **Grafana** (as 4 Golden Metrics com tráfego, latência baixa, 0 erros e saturação estável).
2. Painel do **Argo CD** mostrando todas as aplicações `Synced` e `Healthy`.

### ⌨️ Comandos no Terminal:
```bash
# 1. Verificar Pods em execução
kubectl get pods -A -l "app in (ngo-service,donation-service,volunteer-service)"

# 2. Fazer requisição de teste provando que a API responde 200 OK
export GATEWAY_IP=$(gcloud compute addresses describe gke-ip-lb --global --format='value(address)' --project $PROJECT_ID)
export SERVICE_NAME=ngo-service
curl -i http://solidary-tech.$GATEWAY_IP.nip.io/$SERVICE_NAME/health
```

> **🗣️ O que falar:** *"Iniciamos com nosso ecossistema 100% operacional. Nossos 3 microsserviços estão distribuídos no GKE com métricas dos 4 Golden Signals coletadas via OpenTelemetry e enviadas para o Prometheus/Loki e New Relic com AI Monitoring."*

---

## 🎭 ATO 2: Resiliência de Infraestrutura (Queda de Node no Kubernetes)

> **🎯 Objetivo:** Provar que a perda física de uma máquina (Node do GKE) não derruba a aplicação, demonstrando o funcionamento de **TopologySpreadConstraints** e **PodDisruptionBudget (PDB)**.

### ⌨️ Comandos no Terminal:
```bash
# 1. Listar os nós do cluster
kubectl get nodes

# 2. Simular a morte de um nó (Drain forçado)
NODE_ALVO=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
kubectl drain $NODE_ALVO --ignore-daemonsets --delete-emptydir-data --force

# 3. Em outro terminal, rodar um loop de requisições contínuas:
while true; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8081/health; sleep 0.5; done
```

### 🖥️ O que mostrar na tela:
* Mostre que o loop continua retornando `200` sem nenhuma interrupção, pois o PDB e o ReplicaSet garantiram que os Pods nos outros nós mantivessem o serviço ativo.

```bash
# 4. Reabilitar o nó de volta
kubectl uncordon $NODE_ALVO
```

> **🗣️ O que falar:** *"Mesmo drenando abruptamente um nó inteiro do cluster, o serviço permaneceu 100% online com zero perda de pacotes, graças aos nossos PodDisruptionBudgets e distribuição multi-zona."*

---

## 🎭 ATO 3: Progressive Delivery & Self-Healing de Release (Argo Rollouts)

> **🎯 Objetivo:** Fazer o deploy de uma versão com erro (ou induzir erro 500) e mostrar o **Argo Rollouts** cancelando a atualização e realizando **Auto-Rollback instantâneo** com base no `AnalysisTemplate` e Prometheus.

### ⌨️ Comandos no Terminal:
```bash
# 1. Abrir a visualização do Argo Rollouts em tempo real
kubectl argo rollouts get rollout ngo-service -n ngo-ns --watch
```

```bash
# 2. Em outra janela, disparar o deploy de uma imagem com falha (ou simular erro no Canary)
kubectl argo rollouts set image ngo-service ngo-service=southamerica-east1-docker.pkg.dev/ces-igniteprogram/artreg-ngo-sa/ngo-service:v2-broken -n ngo-ns
```

### 🖥️ O que mostrar na tela:
1. O Argo Rollouts sobe **20%** da nova versão (Canary) e entra em estado de análise de 2 minutos.
2. O `AnalysisTemplate` (`ngo-golden-signals-analysis`) detecta falha nos Golden Signals (taxa de erro > 5% ou latência alta isolada na nova revisão).
3. O status muda para `Degraded` / `Aborted`.
4. O Argo Rollouts mata os pods da versão nova e **restaura 100% do tráfego para a versão estável automaticamente**.

> **🗣️ O que falar:** *"Aqui vemos o Self-Healing de Release em ação. Uma versão com defeito foi isolada em 20% do tráfego. O Prometheus detectou a violação de SLO e o Argo Rollouts abortou o deploy sozinho, protegendo nossos usuários de qualquer indisponibilidade."*

---

## 🎭 ATO 4: Detecção Proativa de Desastre na GCP (Status Checker)

> **🎯 Objetivo:** Mostrar a inteligência proativa da plataforma detectando uma indisponibilidade na nuvem antes que ela afete o negócio.

### ⌨️ Comandos no Terminal:
```bash
# 1. Ativar o Modo de Simulação de Desastre no CronJob
kubectl set env cronjob/gcp-status-checker-cron SIMULATION_MODE="true" SIMULATED_OUTAGE_SERVICES="Cloud SQL" -n monitoring-ns

# 2. Forçar a execução imediata do Job
kubectl create job --from=cronjob/gcp-status-checker-cron gcp-checker-demo -n monitoring-ns

# 3. Ver os logs do Job detectando o incidente
kubectl logs -l job-name=gcp-checker-demo -n monitoring-ns
```

### 🖥️ O que mostrar na tela:
1. Os logs no terminal acusando: `[ALERTA] ⚠️ Instabilidade detectada em 'Cloud SQL' - SIMULATED-DR-CLOUD-SQL`.
2. A notificação no canal do **Slack / New Relic** alertando a equipe de SRE sobre o incidente na região `southamerica-east1`.

> **🗣️ O que falar:** *"Nosso GCP Status Checker varre a telemetria oficial da Google Cloud a cada minuto. Ao identificar um desastre no Cloud SQL na nossa região primária, ele imediatamente aciona os alertas no New Relic e Slack para iniciarmos o procedimento de Failover."*

---

## 🎭 ATO 5: Disaster Recovery de Banco de Dados (Failover do Cloud SQL)

> **🎯 Objetivo:** Simular a perda da instância Master do Cloud SQL e promover a réplica cross-region (`us-east1`) para se tornar a nova Primary de escrita, mantendo a integridade dos dados.

### ⌨️ Comandos no Terminal:
```bash
# 1. Inserir um dado antes do desastre
curl -X POST http://localhost:8081/ngos \
  -H "Content-Type: application/json" \
  -d '{"name": "ONG Salva Vidas", "email": "contato@salvavidas.org", "cause": "Saúde", "city": "São Paulo"}'

# 2. Simular queda do Master (Pausar/Deletar ou Bloquear tráfego do master)
# Promover a Réplica Cross-Region de us-east1 a Primária:
gcloud sql instances promote-replica sql-rhuan-ngo-replica --project=ces-igniteprogram

# 3. Verificar que a réplica agora é o banco principal independente
gcloud sql instances describe sql-rhuan-ngo-replica --project=ces-igniteprogram --format="value(state,region)"
```

> **🗣️ O que falar:** *"Com o banco primário indisponível, promovemos a nossa réplica Cross-Region na região secundária. Os dados previamente sincronizados de forma assíncrona foram 100% preservados (RPO < 5s) e a aplicação continuou operando."*

---

## 🎭 ATO 6: Disaster Recovery Completo de Cluster com Velero

> **🎯 Objetivo:** Simular a perda catastrófica de um namespace e restaurar tudo a partir dos backups automáticos salvos no Google Cloud Storage (GCS).

### ⌨️ Comandos no Terminal:
```bash
# 1. Simular o Desastre total deletando o namespace da ONG
kubectl delete namespace ngo-ns

# 2. Confirmar que o serviço foi destruído
kubectl get pods -n ngo-ns
# (Retorna: No resources found in ngo-ns)

# 3. Listar os backups disponíveis no Bucket GCS
velero backup get

# 4. Disparar a Restauração de Disaster Recovery
velero restore create restore-live-demo --from-schedule daily-full-cluster --wait
# (Ou a partir do backup manual: --from-backup backup-demo-ngo)

# 5. Confirmar a restauração completa dos Pods, Secrets, ConfigMaps e Services
kubectl get pods,svc,secrets -n ngo-ns

# 6. Testar o retorno da aplicação
curl http://localhost:8081/health
```

### 🖥️ O que mostrar na tela:
1. Console do **Google Cloud Storage** com o arquivo `.tar.gz` do backup no bucket `gcs-velero-bucket-solidary-tech-rh`.
2. Todos os Pods voltando ao status `Running` no Kubernetes.

> **🗣️ O que falar:** *"Em menos de 60 segundos, restauramos todo o estado da aplicação a partir do nosso armazenamento imutável no Google Cloud Storage com o Velero, atingindo um RTO de tempo recorde."*

---

## 🏆 Fechamento da Apresentação (Métricas e Conclusão)

Finalize mostrando a tabela de conformidade SRE do projeto:

| Requisito SRE | Como Foi Implementado | Resultado na Demo |
| :--- | :--- | :--- |
| **4 Golden Signals** | PrometheusRule + Grafana + OpenTelemetry | Monitoramento contínuo em tempo real |
| **Self-Healing de Release** | Argo Rollouts + AnalysisTemplate (Canary) | Rollback automático sem impacto no usuário |
| **Resiliência de Nós** | PDB + TopologySpreadConstraints | Zero downtime na queda de infraestrutura |
| **Detecção de Desastre** | GCP Status Checker (CronJob) | Alerta proativo no Slack / New Relic |
| **DR de Dados** | Cloud SQL Cross-Region Replica | Failover com RPO quase zero |
| **DR de Cluster** | Velero Helm + Google Cloud Storage (GCS) | Restauração completa com RTO < 2 minutos |
