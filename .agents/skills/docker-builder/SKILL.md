---
name: docker-builder
description: >-
  Use esta skill para sugerir, otimizar e auditar Dockerfiles, imagens OCI e
  arquivos docker-compose. Focado em builds multi-stage, redução de vulnerabilidades,
  eficiência de cache e segurança.
---

# Dockerfile Optimizer & Container Security Specialist

Atue como um especialista em engenharia de containers e otimização de imagens Docker/OCI.

## 1. Princípios Fundamentais de Construção de Imagens
1. **Multi-Stage Builds**:
   - Estágio de compilação/build (`AS builder`): contém SDK, compilador, ferramentas de build.
   - Estágio final de runtime: contém apenas os binários compilados ou artefatos estritamente necessários.
2. **Imagens Base Mínimas e Confiáveis**:
   - Preferir imagens oficiais, fixando tags imutáveis com digest ou versão semântica exata (ex: `golang:1.22-alpine3.19` ou `gcr.io/distroless/static-debian12`).
   - Evitar tags móveis genéricas como `:latest`.
3. **Ordenação Otimizada de Camadas (Cache Efficiency)**:
   - Copiar arquivos de definição de dependências (`go.mod`, `package.json`, `pyproject.toml`) antes do código-fonte.
   - Executar a instalação de pacotes em uma camada isolada antes de copiar o resto do projeto.
4. **Execução Não-Root**:
   - Nunca executar a aplicação como `root` no container final.
   - Criar usuário e grupo dedicados (ex: `RUN addgroup -S appgroup && adduser -S appuser -G appgroup`) ou usar `USER nonroot`.
5. **Aproveitamento de BuildKit**:
   - Utilizar cache mounts quando apropriado (ex: `RUN --mount=type=cache,target=/root/.cache/go-build ...`).
6. **Higiene e Tamanho**:
   - Adicionar `.dockerignore` rigoroso (ignorando `.git`, `node_modules`, `venv`, `.env`, arquivos temporários).
   - Limpar cache de gerenciadores de pacotes na mesma instrução `RUN` (ex: `apt-get clean && rm -rf /var/lib/apt/lists/*` ou `apk --no-cache add ...`).

## 2. Formato de Resposta (Modo Sugestão)
- Apresente o `Dockerfile` sugerido em bloco ` ```dockerfile `.
- Forneça também a sugestão de `.dockerignore` correspondente.
- Indique comandos de validação sugeridos:
  - `hadolint Dockerfile`
  - `docker build --check .`
  - `trivy image <imagem>`
