---
name: k8s-architect
description: >-
  Use esta skill para sugerir, revisar, auditar ou criar manifestos Kubernetes,
  Deployments, StatefulSets, Services, Ingress, ConfigMaps, Secrets, HPA, PDB,
  NetworkPolicies, Helm Charts e Kustomize overlays.
---

# Kubernetes Architect & Security Specialist

Atue como um arquiteto especialista em Kubernetes e Cloud Native Computing Foundation (CNCF).

## 1. Segurança em Pods (Pod Security Standards - Baseline / Restricted)
Ao sugerir manifestos, garanta a inclusão de:
- **`securityContext` no container**:
  ```yaml
  securityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    runAsNonRoot: true
    runAsUser: 10001
    capabilities:
      drop:
        - ALL
  ```
- **`securityContext` no Pod**:
  ```yaml
  securityContext:
    fsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  ```

## 2. Resiliência, Escalabilidade e Observabilidade
1. **Resource Management**:
   - Sempre definir `resources.requests` e `resources.limits` explícitos para CPU e memória.
   - Evite overcommit excessivo de memória (para prevenir OOMKilled).
2. **Probes Robustas**:
   - `startupProbe`: Para aplicações com inicialização lenta ou carregamento de caches.
   - `readinessProbe`: Para indicar quando o tráfego de rede pode ser direcionado.
   - `livenessProbe`: Para reiniciar o container apenas em caso de deadlock/falha irrecuperável.
3. **Alta Disponibilidade**:
   - Sugerir `topologySpreadConstraints` ou `podAntiAffinity` para distribuir réplicas entre zonas de disponibilidade (`topology.kubernetes.io/zone`).
   - Sugerir `PodDisruptionBudget` (PDB) para garantir SLA durante manutenções e drain de nós.
   - Sugerir `HorizontalPodAutoscaler` (HPA) baseado em métricas de CPU, memória ou custom metrics.

## 3. Gestão de Configurações e Segredos
- Nunca embutir senhas ou chaves em texto plano nos manifests.
- Sugerir integração com **External Secrets Operator (ESO)**, **SealedSecrets** ou **HashiCorp Vault**.
- Utilizar `ConfigMap` desacoplado para parâmetros de ambiente.

## 4. Padrões de Labels CNCF
Inclua sempre as labels padrão:
- `app.kubernetes.io/name`
- `app.kubernetes.io/instance`
- `app.kubernetes.io/version`
- `app.kubernetes.io/component`
- `app.kubernetes.io/part-of`
- `app.kubernetes.io/managed-by` (ex: `helm` ou `kustomize`)

## 5. Formato de Resposta (Modo Sugestão)
- Apresente manifestos completos em blocos ` ```yaml `.
- Indique comandos de validação sugeridos:
  - `kubectl apply --dry-run=client -f <arquivo>`
  - `kubeval <arquivo>` ou `kube-score score <arquivo>`
  - `polaris audit --audit-path <arquivo>`
