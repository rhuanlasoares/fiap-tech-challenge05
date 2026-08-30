# Rule: Modo Consultivo de Sugestões de Código (Advisory Mode)

## Contexto e Comportamento Esperado
Quando o usuário solicitar auxílio para refatoração, criação, otimização ou debugging de códigos:

1. **Não aplicar alterações cegas**: Apresente a sugestão formatada em blocos de código com a respectiva linguagem ou em formato diff quando se tratar de refatoração.
2. **Explicar o Racional**: Indique o porquê de cada mudança (por exemplo: por que adicionou um eadinessProbe, por que usou context.WithTimeout, por que utilizou multi-stage build, por que usou sync.Mutex).
3. **Oferecer Opções / Trade-offs**: Sempre que houver mais de uma abordagem válida (ex: Kustomize vs Helm, Distroless vs Alpine, Poetry vs UV), apresente a opção recomendada e o motivo da escolha.
4. **Comandos de Validação**: Forneça os comandos exatos que o desenvolvedor pode rodar no terminal para testar a sugestão (ex: 	erraform plan, golangci-lint run, pytest -v, hadolint Dockerfile, kubeval manifest.yaml).
