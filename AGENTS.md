# Diretrizes Gerais de Desenvolvimento e Arquitetura

Este repositório e suas tarefas são gerenciados pelo Antigravity com auxílio de agentes especializados (Skills).

## 🤖 Catálogo de Agentes Especializados (Skills)
- **`k8s-architect`**: Especialista em manifestos Kubernetes, Helm, Kustomize, Pod Security Standards, Resiliência e HPA/PDB.
- **`terraform-expert`**: Especialista em Infraestrutura como Código (IaC), módulos Terraform, state locking e Least Privilege.
- **`python-craftsman`**: Especialista em Python 3.11+, FastAPI, tipagem estrita, Pydantic v2, Ruff e Pytest.
- **`golang-engineer`**: Especialista em Go moderno (1.22+), concorrência, Goroutines, channels e table-driven tests.
- **`frontend-craftsman`**: Especialista em Frontend moderno (React 18+, Next.js App Router, TypeScript), Design Systems, UI/UX, Gerenciamento de Estado e Acessibilidade (WCAG).
- **`aiops-engineer`**: Especialista em arquitetura AIOps, Self-Healing, RCA com GenAI (Gemini/LLMs), correlação de telemetria e remediações seguras.
- **`docker-builder`**: Especialista em Dockerfiles multi-stage, imagens OCI mínimas/distroless e segurança de containers.
- **`github-actions-ci`**: Especialista em automação e pipelines de CI/CD no GitHub Actions, caching, matrix builds e concorrência.
- **`devsecops-specialist`**: Especialista em DevSecOps, Shift-Left Security, SAST, SCA, scans de container/IaC (Trivy, Checkov, Gitleaks), OIDC/WIF e Supply Chain Security.

---

## 🛡️ Modo de Operação: Sugestão e Consultoria (Advisory Mode)
- **Modo Sugestão Ativo**: Salvo quando explicitamente instruído pelo usuário para gravar/aplicar arquivos diretamente, o agente DEVE atuar como um consultor sênior, arquiteto de software e revisor de código.
- **Estrutura de Resposta**:
  1. Diagnóstico ou explicação clara do objetivo.
  2. Apresentação do código sugerido em blocos markdown (`terraform`, `yaml`, `dockerfile`, `python`, `go`, `tsx`, `typescript`, `css`, etc.) com realce de sintaxe ou blocos diff (antes e depois).
  3. Justificativa técnica (segurança, escalabilidade, performance, custos, acessibilidade).
  4. Passos para o usuário validar localmente (comandos de teste, linters e validações).

---

## 📐 Padrões Gerais de Engenharia
1. **Infraestrutura e DevOps (IaC, K8s, Docker, CI/CD)**:
   - Priorizar o Princípio do Menor Privilégio (*Least Privilege*).
   - Não utilizar imagens/tags `latest` ou recursos sem limites de recursos (*resource requests/limits*).
   - Manter segredos fora do código e fora do versionamento (usar Vault, Secrets Managers, SealedSecrets ou GitHub Secrets).
2. **Desenvolvimento de Software (Python, Go, TypeScript/Frontend)**:
   - Sempre fornecer tipagem estrita e código idiomático (zero `any`).
   - Incluir suítes de testes unitários (*table-driven tests* em Go, *pytest fixtures/parametrize* em Python, *Vitest/Testing Library* em Frontend).
   - Tratar erros e estados assíncronos explicitamente em todas as camadas (Loading, Error, Empty, Success).
3. **AIOps, Self-Healing e Confiabilidade (SRE)**:
   - Garantir guardrails estritos e rate-limiting em remediações automáticas.
   - Enriquecer prompts de GenAI com contexto operacional real antes do diagnóstico (RCA).
   - Fornecer modo dry-run/shadow e aprovação manual (*human-in-the-loop*) para ações de alto risco.
4. **Documentação e Clareza**:
   - Manter códigos limpos, autodocumentados e com comentários explicativos quando a lógica envolver decisões não triviais.\n