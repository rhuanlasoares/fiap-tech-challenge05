# 💰 Relatório Executivo de FinOps & Forecast de Custos
### 🌍 Plataforma SolidaryTech — Otimização Financeira e Eficiência em Nuvem
**Documento Executivo de Gestão Orçamentária e Governança em Nuvem**

---

## 1. Visão Geral e Princípios FinOps

Para uma organização sem fins lucrativos como a **SolidaryTech**, a sustentabilidade financeira e a eficiência no uso de cada recurso de nuvem são fundamentais. A arquitetura foi projetada para equilibrar **alta disponibilidade e resiliência** com o **menor custo total de propriedade (TCO)**.

### Pilares FinOps Adotados:
1. **Tagueamento Abrangente**: 100% dos recursos de nuvem rastreados por centro de custo e projeto.
2. **Dimensionamento Consciente (*Rightsizing*)**: CPU e memória configurados conforme o perfil real de consumo.
3. **Uso Estratégico de Computação Spot**: Redução drástica de custo nos nós do Kubernetes.
4. **Desacoplamento Assíncrono (*Scale-to-Zero*)**: Processamento de filas SQS escalonado sob demanda via KEDA.

---

## 2. Política e Evidências de Tagging IaC (Terraform)

Todos os recursos provisionados na GCP e AWS possuem políticas estritas de metadados declaradas no Terraform (`iac/terraform/terraform.tfvars`):

```hcl
instance_labels = {
  "created_by"  = "rhuan"
  "terraform"   = "true"
  "app"         = "fiap-tech-challenge"
  "service"     = "ngo-service"
  "project"     = "solidary-tech"
  "environment" = "production"
  "cost_center" = "ngo-core"
}
```

### 🏷️ Matriz de Tags Obrigatórias:
* `Project`: `solidary-tech` (Identificação global do projeto).
* `Environment`: `production` (Segregação de ambiente produtivo).
* `CostCenter`: `ngo-core` (Alocação orçamentária para prestação de contas à diretoria).
* `Terraform`: `true` (Garantia de que nenhum recurso foi criado manualmente no console).

---

## 3. Rightsizing e Governança de Recursos no Kubernetes

A análise de telemetria dos microsserviços resultou nos seguintes ajustes nos arquivos `rollout.yaml`:

| Microsserviço | CPU Request | CPU Limit | RAM Request | RAM Limit | Racional de Engenharia |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`donation-service`** | `16m` | `250m` | `32Mi` | `256Mi` | Escrita ultrarrápida em Go; baixo uso basal de memória e escalabilidade vertical sob rajadas. |
| **`ngo-service`** | `50m` | `512m` | `64Mi` | `256Mi` | Aplicação Python REST; requests baixos para maximizar densidade de pods por nó. |
| **`volunteer-service`** | `78m` | `512m` | `64Mi` | `512Mi` | Mapeamento de vagas e filtros de busca com buffer para consultas simultâneas. |
| **`aiops-engine`** | `100m` | `500m` | `128Mi` | `512Mi` | Processamento assíncrono de telemetria com baixo footprint de execução. |

> 💡 **Monitoramento Contínuo com Kubecost**: O Kubecost instalado no namespace `kubecost` calcula o custo por namespace, pod e requisição HTTP em tempo real, permitindo identificar capacidade ociosa (*Idle Waste*).

---

## 4. Projeção de Custos Mensais (Forecast de Custos)

Abaixo está o comparativo de custos entre o modelo On-Demand tradicional e a arquitetura otimizada da SolidaryTech:

| Componente de Infraestrutura | Especificação Técnica | Custo Mensal (On-Demand) | Custo Mensal Otimizado (SolidaryTech) | Estratégia de Redução Aplicada |
| :--- | :--- | :---: | :---: | :--- |
| **GKE Worker Nodes** | 2 nós `e2-standard-2` | \$97.44 | **\$29.23** | **Uso de Spot Instances (Desconto de ~70%)** com PDB para resiliência. |
| **GKE Control Plane** | Gerenciado pelo Google Cloud | \$0.00 | **\$0.00** | 1 cluster zonal gratuito no Free Tier mensal da GCP. |
| **Cloud SQL PostgreSQL (Master)** | 2 instâncias `db-f1-micro` (Shared Core) | \$15.20 | **\$15.20** | Tier econômico adequado à volumetria de dados da ONG. |
| **Cloud SQL DR Replica (US)** | Réplica de leitura em `us-east1` | \$7.60 | **\$7.60** | Instância réplica de baixo custo para garantir RPO < 5s. |
| **Rede & Cloud NAT** | 1 Gateway NAT + Egress Traffic | \$8.50 | **\$8.50** | Tráfego interno de pods roteado dentro da VPC sem custo de IP público. |
| **AWS SQS Queue** | Fila gerenciada de doações | \$0.00 | **\$0.00** | Abrangido pelo Free Tier perpétuo da AWS (1M req/mês). |
| **Storage GCS (Velero + Loki)** | 2 Buckets Standard (~20 GB) | \$0.52 | **\$0.40** | Políticas de expiração automática de logs após 15 dias. |
| **Google Gemini GenAI** | Modelo `gemini-3.6-flash` | \$10.00 | **\$0.00** | **Free Tier do Google AI Studio (15 RPM gratuitas)** com filtro preditivo de custo zero em cluster saudável. |
| **TOTAL MENSAL ESTIMADO** | — | **\$139.26** | **\$60.93** | **Economia Global de 56,2% (\$78.33 economizados/mês)** |

---

## 5. Recomendações Nativas de Otimização Adicional (Próximos Passos)

1. **Committed Use Discounts (CUDs)**:
   - Para os recursos de banco de dados e computação base que rodam 24/7, um contrato de CUD de 1 ano com o Google Cloud proporciona **37% a 57% de desconto adicional**.
2. **KEDA Scale-to-Zero**:
   - Os workers que processam mensagens assíncronas no SQS escalam para zero pods quando não há mensagens pendentes, eliminando consumo desnecessário de CPU.
3. **GCS Bucket Lifecycle Policies**:
   - Mover backups do Velero com mais de 30 dias para a classe **Coldline Storage** reduz o custo de armazenamento em **75%**.\n