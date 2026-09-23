"""
Templates de Engenharia de Prompt para o AI Code Remediator.
Garante respostas em JSON estruturado, contextualização técnica,
zero quebras de tipagem ou assinaturas públicas e auto-reflexão pós-falha de teste.
"""

def build_remediation_prompt(
    finding: dict,
    tool_name: str,
    scan_type: str,
    service_name: str,
    file_rel_path: str,
    file_content: str,
    language: str = "pt-BR"
) -> str:
    """Gera o prompt para a IA propor o código corrigido e seguro."""
    return f"""Você é um arquiteto especialista sênior em DevSecOps, AppSec e Engenharia de Software.
Sua missão é corrigir a vulnerabilidade de segurança identificada pela ferramenta '{tool_name}' ({scan_type.upper()}) no arquivo '{file_rel_path}' do serviço '{service_name}'.

DETALHES DO ACHADO DE SEGURANÇA:
- ID / Regra: {finding.get('id', 'N/A')}
- Título: {finding.get('title', '')}
- Severidade: {finding.get('severity', 'HIGH')}
- Componente / Linha: {finding.get('component', '')}
- Descrição: {finding.get('description', '')}
- Sugestão da Ferramenta: {finding.get('remediation', '')}

CONTEÚDO ATUAL DO ARQUIVO ({file_rel_path}):
```
{file_content}
```

DIRETRIZES TÉCNICAS ESTRITAS:
1. PRESERVAÇÃO DE COMPORTAMENTO:
   - Corrija estritamente a vulnerabilidade de segurança.
   - NUNCA altere assinaturas de funções públicas ou interfaces já existentes.
   - Mantenha a sintaxe, formatação e convenções de estilo do código original.
   - Não adicione novas dependências externas pesadas a menos que seja a prática padrão e recomendada da linguagem para segurança (ex: crypto nativo).
2. CONFIANÇA E ELEGIBILIDADE:
   - Se a vulnerabilidade exigir uma refatoração arquitetural profunda de múltiplos arquivos ou decisões de negócio ambíguas, defina "is_fixable": false.
   - Se for uma vulnerabilidade que pode ser remediada localmente com alta precisão e segurança no arquivo fornecido, defina "is_fixable": true e confidence_score >= 0.85.
3. CONTEÚDO CORRIGIDO:
   - O campo "patched_file_content" DEVE conter o arquivo COMPLETO corrigido de ponta a ponta, pronto para substituir o arquivo original, mantendo imports, comentários e toda lógica funcional não afetada.
4. IDIOMA:
   - Todos os textos explicativos ("explanation", "summary", "risk_assessment", "pr_title", "pr_body") DEVEM estar estritamente em {language}.

Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{{
  "is_fixable": true,
  "confidence_score": 0.95,
  "summary": "Resumo em uma linha da correção aplicada",
  "explanation": "Explicação detalhada em {language} do motivo da falha e como a correção resolve o problema sem causar efeitos colaterais.",
  "risk_assessment": "Avaliação de riscos ou potenciais impactos da mudança para revisão humana.",
  "pr_title": "fix(security): título conciso para o Pull Request em {language}",
  "pr_body": "Descrição estruturada em Markdown para o Pull Request em {language}",
  "patched_file_content": "CONTEUDO_INTEGRAL_DO_ARQUIVO_CORRIGIDO_AQUI"
}}
"""


def build_reflection_prompt(
    finding: dict,
    file_rel_path: str,
    original_content: str,
    attempted_content: str,
    test_command: str,
    test_output: str,
    language: str = "pt-BR"
) -> str:
    """Gera o prompt de auto-reflexão quando os testes unitários ou linter falham após o patch."""
    return f"""Você é um engenheiro de software sênior realizando auto-reflexão e correção de falha.
Você aplicou uma correção de segurança no arquivo '{file_rel_path}', porém a suíte de validação executou o comando:
`{test_command}`
e FALHOU com o seguinte erro:

```
{test_output}
```

ACHADO DE SEGURANÇA ORIGINAL:
- Regra: {finding.get('id', 'N/A')} - {finding.get('title', '')}

CÓDIGO QUE VOCÊ HAVIA TENTADO:
```
{attempted_content}
```

CÓDIGO ORIGINAL ANTES DO PATCH:
```
{original_content}
```

MISSÃO DE REFLEXÃO:
1. Analise exatamente por que o teste/compilador falhou (ex: erro de tipo, import faltando, sintaxe inválida, falha de asserção).
2. Ajuste o código para corrigir tanto o erro do teste quanto a vulnerabilidade de segurança original.
3. Se você perceber que a vulnerabilidade não pode ser corrigida sem quebrar requisitos fundamentais da aplicação, defina "is_fixable": false.

Responda ESTRITAMENTE em formato JSON com o schema:
{{
  "is_fixable": true,
  "confidence_score": 0.90,
  "summary": "Resumo do ajuste após a falha do teste",
  "explanation": "Explicação em {language} de como o erro foi corrigido mantendo a segurança.",
  "risk_assessment": "Avaliação de risco atualizada.",
  "pr_title": "fix(security): correção de segurança com validação de testes",
  "pr_body": "Descrição detalhada para o PR incluindo as lições da falha do teste.",
  "patched_file_content": "CONTEUDO_INTEGRAL_DO_ARQUIVO_CORRIGIDO_AQUI"
}}
"""
