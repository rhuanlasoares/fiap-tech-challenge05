# 📜 Scripts de Automação, Validação & Engenharia de Caos

Esta pasta reúne todos os scripts utilitários em Shell utilizados para inicialização de ambiente, compilação de contêineres, testes end-to-end (E2E), simulações de carga sintética e **testes práticos de Disaster Recovery**.

---

## 📋 Catálogo de Scripts

| Script | Finalidade | Como Executar |
| :--- | :--- | :--- |
| **`ansible.sh`** | Inicializa o cluster GKE com todos os namespaces, controllers (Argo CD, Rollouts, KEDA), monitoramento e aplicações. | `bash scripts/ansible.sh` |
| **`build-push-images.sh`** | Constrói localmente todas as imagens Docker e envia para os repositórios do GCP Artifact Registry. | `bash scripts/build-push-images.sh` |
| **`test-disaster-recovery.sh`** | Executa cenários automatizados de Disaster Recovery (promoção de réplica do Cloud SQL, drenagem forçada de nós e restore do Velero). | `bash scripts/test-disaster-recovery.sh` |
| **`test-all-routes.sh`** | Dispara chamadas de validação e testes de latência contra todas as rotas públicas do Gateway API. | `bash scripts/test-all-routes.sh` |
| **`test-health.sh`** | Realiza health check contínuo em loop contra os endpoints de saúde dos microsserviços. | `bash scripts/test-health.sh` |
| **`test-aiops-prediction.sh`** | Gera carga sintética anômala para acionar os alertas preditivos de ML e o diagnóstico GenAI do AIOps Engine. | `bash scripts/test-aiops-prediction.sh` |
| **`run-ab-test.sh`** | Simula tráfego concorrente para validar a distribuição de tráfego Canary do Argo Rollouts e medição de Golden Signals. | `bash scripts/run-ab-test.sh` |
| **`cleanup-gcp-resources.sh`** | Destrói de forma controlada e segura os recursos do GCP ao finalizar simulações e testes. | `bash scripts/cleanup-gcp-resources.sh` |

---

## 🧪 Roteiro dos Testes de Resiliência

Para executar a bateria de testes de resiliência e simulação de desastres:

```bash
# 1. Testar todas as rotas da aplicação
bash scripts/test-all-routes.sh

# 2. Testar comportamento preditivo do AIOps
bash scripts/test-aiops-prediction.sh

# 3. Executar o fluxo completo de Disaster Recovery
bash scripts/test-disaster-recovery.sh
```