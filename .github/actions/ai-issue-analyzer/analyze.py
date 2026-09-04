#!/usr/bin/env python3
"""
AI Issue Analyzer for GitHub Actions
Analisa relatórios de segurança (SCA, SAST, Container) e Lint utilizando
Google AI Studio (Gemini) para decidir com inteligência se uma Issue é necessária,
sintetizando CVEs e fornecendo remediação direta.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def set_github_output(name: str, value: str):
    """Registra saída no formato aceito pelo GitHub Actions."""
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    print(f"[ai-issue-analyzer] Output: {name}={value}")


def auto_close_existing_issue(service_name: str, scan_type: str, tool_name: str, token: str):
    """Fecha automaticamente issues abertas que foram resolvidas nesta execução."""
    if not token:
        return
    try:
        query = f"is:open is:issue repo:{os.getenv('GITHUB_REPOSITORY', '')} [{scan_type.upper()}][{tool_name}] {service_name}"
        res = subprocess.run(
            ["gh", "issue", "list", "--search", query, "--json", "number,title"],
            env={**os.environ, "GH_TOKEN": token},
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            issues = json.loads(res.stdout)
            for issue in issues:
                num = issue.get("number")
                title = issue.get("title", "")
                commit_sha = os.getenv("GITHUB_SHA", "latest")
                comment = (
                    f"✅ **Problema Resolvido**\n\n"
                    f"A verificação `{tool_name}` (`{scan_type.upper()}`) para `{service_name}` "
                    f"não encontrou nenhum achado no commit `{commit_sha}`.\n"
                    f"Fechando issue automaticamente."
                )
                print(f"[ai-issue-analyzer] Fechando issue resolvida #{num} ('{title}')")
                subprocess.run(
                    ["gh", "issue", "close", str(num), "--comment", comment],
                    env={**os.environ, "GH_TOKEN": token},
                    capture_output=True,
                    check=False
                )
    except Exception as e:
        print(f"[ai-issue-analyzer] Aviso ao verificar issues existentes: {e}")


def parse_findings(scan_type: str, tool_name: str, report_file: str, diff_file: str = None) -> list:
    """
    Faz o parse do arquivo de scan e retorna uma lista padronizada de achados.
    """
    findings = []

    # 1. Lint
    if scan_type.lower() == "lint":
        error_content = ""
        diff_content = ""
        if report_file and os.path.isfile(report_file):
            with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
                error_content = f.read().strip()
        if diff_file and os.path.isfile(diff_file):
            with open(diff_file, "r", encoding="utf-8", errors="ignore") as f:
                diff_content = f.read().strip()

        if not error_content and not diff_content:
            return []

        # Se existirem erros residuais no linter, registramos
        if error_content:
            lines = [l.strip() for l in error_content.splitlines() if l.strip()]
            for line in lines[:25]:
                findings.append({
                    "id": "LINT-ERROR",
                    "component": line.split(":")[0] if ":" in line else "código",
                    "severity": "MEDIUM",
                    "title": line[:100],
                    "description": line,
                    "remediation": "Corrija a violação de estilo ou sintaxe indicada."
                })
        return findings

    if not report_file or not os.path.isfile(report_file):
        print(f"[ai-issue-analyzer] Aviso: Arquivo de relatório '{report_file}' não encontrado.")
        return []

    try:
        with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read().strip()
        if not raw_text:
            return []
        data = json.loads(raw_text)
    except Exception as e:
        # Se for texto puro (ex: log de saída de linter ou diff)
        if raw_text:
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            for line in lines[:25]:
                findings.append({
                    "id": f"{tool_name.upper()}-ITEM",
                    "component": line.split(":")[0] if ":" in line else "arquivo",
                    "severity": "MEDIUM",
                    "title": line[:100],
                    "description": line,
                    "remediation": "Revisar código ou configuração."
                })
        return findings

    # Lista direta de itens (ex: Hadolint JSON)
    if isinstance(data, list):
        for item in data:
            findings.append({
                "id": item.get("code", "RULE"),
                "component": f"{item.get('file', 'Dockerfile')}:{item.get('line', '')}",
                "severity": item.get("level", "info").upper(),
                "title": item.get("message", "Lint finding"),
                "description": item.get("message", ""),
                "remediation": "Ajuste a diretiva conforme recomendação da regra."
            })
        return findings

    # 2. SCA (Trivy, OWASP)
    if scan_type.lower() == "sca":
        # Trivy
        if "Results" in data:
            for res in data.get("Results", []):
                target = res.get("Target", "unknown")
                for vuln in res.get("Vulnerabilities", []) or []:
                    findings.append({
                        "id": vuln.get("VulnerabilityID", "N/A"),
                        "component": f"{vuln.get('PkgName', 'unknown')} ({target})",
                        "severity": vuln.get("Severity", "UNKNOWN").upper(),
                        "title": vuln.get("Title") or vuln.get("VulnerabilityID", "Vulnerabilidade"),
                        "description": vuln.get("Description", "Sem descrição."),
                        "installed_version": vuln.get("InstalledVersion", "N/A"),
                        "fixed_version": vuln.get("FixedVersion", "N/A"),
                        "remediation": f"Atualizar pacote {vuln.get('PkgName')} para versão {vuln.get('FixedVersion', 'mais recente')}."
                    })
        # OWASP Dependency-Check
        if "dependencies" in data:
            for dep in data.get("dependencies", []):
                pkg_name = dep.get("fileName", "unknown")
                for vuln in dep.get("vulnerabilities", []) or []:
                    findings.append({
                        "id": vuln.get("name", "N/A"),
                        "component": pkg_name,
                        "severity": vuln.get("severity", "UNKNOWN").upper(),
                        "title": vuln.get("name", "Vulnerabilidade"),
                        "description": vuln.get("description", "Sem descrição."),
                        "remediation": f"Atualizar dependência {pkg_name} para sanar {vuln.get('name')}."
                    })

    # 3. SAST (Gosec, Bandit, Semgrep, Trivy Secrets)
    elif scan_type.lower() == "sast":
        # Gosec
        if "Issues" in data:
            for issue in data.get("Issues", []):
                findings.append({
                    "id": issue.get("rule_id", "GOSEC"),
                    "component": f"{issue.get('file', '')}:{issue.get('line', '')}",
                    "severity": issue.get("severity", "LOW").upper(),
                    "title": issue.get("details", "Problema de Segurança"),
                    "description": f"{issue.get('details', '')} (Trecho: {issue.get('code', '').strip()})",
                    "remediation": "Refatorar código para eliminar a vulnerabilidade identificada."
                })
        # Bandit
        if "results" in data:
            for res in data.get("results", []):
                findings.append({
                    "id": res.get("test_id", "BANDIT"),
                    "component": f"{res.get('filename', '')}:{res.get('line_number', '')}",
                    "severity": res.get("issue_severity", "LOW").upper(),
                    "title": res.get("issue_text", "Problema de Segurança"),
                    "description": f"{res.get('issue_text', '')} (Trecho: {res.get('code', '').strip()})",
                    "remediation": res.get("more_info", "Revisar trecho de código apontado pelo Bandit.")
                })
        # Trivy Secrets
        if "Results" in data:
            for res in data.get("Results", []):
                target = res.get("Target", "código")
                for sec in res.get("Secrets", []) or []:
                    findings.append({
                        "id": sec.get("RuleID", "SECRET-EXPOSED"),
                        "component": f"{target}:{sec.get('StartLine', '')}",
                        "severity": sec.get("Severity", "HIGH").upper(),
                        "title": sec.get("Title", "Credencial Exposta"),
                        "description": f"Credencial ou token detectado no código: {sec.get('Category', '')} - {sec.get('Title', '')}",
                        "remediation": "Remover imediatamente o secret do histórico git, rotacionar a chave e injetar via Secret Manager."
                    })

    # 4. Container (Trivy Dockerfile Misconfig, Trivy Image Vulns)
    elif scan_type.lower() == "container":
        if "Results" in data:
            for res in data.get("Results", []):
                target = res.get("Target", "container")
                for conf in res.get("Misconfigurations", []) or []:
                    findings.append({
                        "id": conf.get("ID", "MISCONFIG"),
                        "component": target,
                        "severity": conf.get("Severity", "LOW").upper(),
                        "title": conf.get("Title", "Configuração Insegura"),
                        "description": conf.get("Description", "Sem descrição."),
                        "remediation": conf.get("Resolution", "Ajustar diretiva do Dockerfile conforme boas práticas.")
                    })
                for vuln in res.get("Vulnerabilities", []) or []:
                    findings.append({
                        "id": vuln.get("VulnerabilityID", "N/A"),
                        "component": f"{vuln.get('PkgName', 'unknown')} ({target})",
                        "severity": vuln.get("Severity", "UNKNOWN").upper(),
                        "title": vuln.get("Title") or vuln.get("VulnerabilityID", "Vulnerabilidade"),
                        "description": vuln.get("Description", "Sem descrição."),
                        "installed_version": vuln.get("InstalledVersion", "N/A"),
                        "fixed_version": vuln.get("FixedVersion", "N/A"),
                        "remediation": f"Atualizar imagem base ou pacote {vuln.get('PkgName')}."
                    })

    return findings


def call_gemini_api(api_key: str, prompt: str, model: str = "gemini-3.6-flash-lite") -> dict:
    """Chama a API do Google AI Studio com Structured JSON Output e fallback automático."""
    models_to_try = [model, "gemini-3.6-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    seen = set()
    models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    last_error = None
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"}
        )
        try:
            print(f"[ai-issue-analyzer] Chamando Gemini API (modelo: {m})...")
            with urllib.request.urlopen(req, timeout=45) as resp:
                result_json = json.loads(resp.read().decode("utf-8"))
                candidates = result_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text_response = parts[0].get("text", "")
                        return json.loads(text_response)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"[ai-issue-analyzer] HTTPError com modelo {m} ({e.code}): {err_body}")
            last_error = e
        except Exception as e:
            print(f"[ai-issue-analyzer] Erro com modelo {m}: {e}")
            last_error = e

    print(f"[ai-issue-analyzer] Falha ao comunicar com a Gemini API: {last_error}")
    return None


def generate_fallback_issue(scan_type: str, tool_name: str, service_name: str, findings: list) -> dict:
    """Gera uma estrutura padronizada caso a API do Gemini não esteja disponível."""
    sev_counts = {}
    for f in findings:
        sev = f.get("severity", "LOW")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    max_sev = "LOW"
    for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev_counts.get(s, 0) > 0:
            max_sev = s
            break

    summary = f"Foram identificados {len(findings)} achados na verificação {tool_name} para o serviço {service_name}."
    action_plan = "Revise as dependências e o código listados abaixo para aplicar as correções recomendadas."

    return {
        "should_create_issue": True,
        "max_severity": max_sev,
        "title_summary": f"{len(findings)} achados detectados ({max_sev})",
        "executive_summary": summary,
        "findings": findings[:20],
        "action_plan": action_plan
    }


def main():
    parser = argparse.ArgumentParser(description="AI Issue Analyzer with Gemini")
    parser.add_argument("--scan-type", required=True, choices=["lint", "sca", "sast", "container"], help="Tipo de scan")
    parser.add_argument("--tool-name", required=True, help="Nome da ferramenta (ex: Trivy, Gosec, Lint Go)")
    parser.add_argument("--report-file", required=False, default="", help="Arquivo de resultado do scan")
    parser.add_argument("--diff-file", required=False, default="", help="Arquivo diff (para Lint)")
    parser.add_argument("--service-name", required=True, help="Nome do serviço (ex: donation-service)")
    parser.add_argument("--service-path", required=False, default="", help="Caminho do serviço (ex: apps/donation-service)")
    parser.add_argument("--gemini-api-key", required=False, default="", help="API Key do Google AI Studio")
    parser.add_argument("--github-token", required=False, default="", help="GitHub Token")
    parser.add_argument("--output-file", required=False, default="issue-ai.md", help="Arquivo markdown gerado")
    parser.add_argument("--model", required=False, default="gemini-3.6-flash-lite", help="Modelo Gemini")

    args = parser.parse_args()

    api_key = args.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    token = args.github_token or os.getenv("GITHUB_TOKEN", "") or os.getenv("GH_TOKEN", "")
    service_path = args.service_path or args.service_name

    print(f"[ai-issue-analyzer] Iniciando análise: scan_type={args.scan_type}, tool={args.tool_name}, service={args.service_name}")

    # 1. Parse findings
    findings = parse_findings(args.scan_type, args.tool_name, args.report_file, args.diff_file)
    print(f"[ai-issue-analyzer] Total de achados brutos identificados: {len(findings)}")

    # 2. Heurística Pré-Filtro (Custo Zero de API)
    if len(findings) == 0:
        print(f"[ai-issue-analyzer] ✅ Nenhum achado relevante encontrado. Nenhuma Issue será criada.")
        set_github_output("create_issue", "false")
        auto_close_existing_issue(args.service_name, args.scan_type, args.tool_name, token)
        sys.exit(0)

    # 3. Análise Inteligente com Gemini API
    ai_result = None
    if api_key:
        prompt = f"""
Você é um especialista sênior em DevSecOps e Segurança de Aplicações.
Analise os seguintes achados gerados pela ferramenta '{args.tool_name}' ({args.scan_type.upper()}) para o microserviço '{args.service_name}' (caminho: '{service_path}').

Achados ({len(findings)} itens brutos):
{json.dumps(findings[:25], indent=2, ensure_ascii=False)}

Objetivos:
1. Avalie se esses achados justificam a abertura de uma Issue no GitHub ('should_create_issue'). Ignorar apenas se forem puramente informativos ou sem risco real.
2. Identifique a severidade máxima real ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW').
3. Crie um resumo executivo conciso em português do Brasil, explicando em 1 ou 2 parágrafos o risco desses achados para o serviço.
4. Para cada achado principal (máximo 15 principais), descreva o impacto de forma clara e a remediação exata (ex: comando `go get package@version`, comando `pip install`, diretiva no Dockerfile ou alteração no código).
5. Forneça um plano de ação ('action_plan') objetivo em Markdown com o passo a passo que o desenvolvedor deve executar para corrigir o problema.

Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{{
  "should_create_issue": true,
  "max_severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "title_summary": "resumo curto em português para o título (ex: 3 CVEs em dependências Go)",
  "executive_summary": "parágrafo explicativo em português",
  "findings": [
    {{
      "id": "CVE-XXXX ou ID",
      "component": "pacote ou arquivo",
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
      "description": "breve explicação do problema",
      "remediation": "como solucionar exatamente"
    }}
  ],
  "action_plan": "passo a passo com comandos de remediação em markdown"
}}
"""
        ai_result = call_gemini_api(api_key, prompt, args.model)

    if not ai_result:
        print("[ai-issue-analyzer] Utilizando gerador de contingência (fallback local)...")
        ai_result = generate_fallback_issue(args.scan_type, args.tool_name, args.service_name, findings)

    should_create = ai_result.get("should_create_issue", True)
    if not should_create:
        print("[ai-issue-analyzer] ℹ️ A IA avaliou que os achados não justificam a abertura de Issue. Nenhuma issue será criada.")
        set_github_output("create_issue", "false")
        sys.exit(0)

    # 4. Geração do Markdown com frontmatter para JasonEtco/create-an-issue
    max_sev = ai_result.get("max_severity", "HIGH").upper()
    title_summary = ai_result.get("title_summary", f"Achados em {args.service_name}")
    labels = ["security", args.scan_type.lower(), args.tool_name.lower().replace(" ", "-"), max_sev.lower()]
    labels_str = ", ".join([f'"{l}"' for l in labels])

    run_number = os.getenv("GITHUB_RUN_NUMBER", "local")
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    repository = os.getenv("GITHUB_REPOSITORY", "repo")
    commit_sha = os.getenv("GITHUB_SHA", "main")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}"
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = []
    md.append("---")
    md.append(f"title: '[{args.scan_type.upper()}][{args.service_name}] [{max_sev}] {args.tool_name} — {title_summary}'")
    md.append(f"labels: [{labels_str}]")
    md.append("---")
    md.append("")
    md.append(f"# 🛡️ Triagem de Segurança & Qualidade — {args.tool_name}")
    md.append("")
    md.append(f"> [!IMPORTANT]")
    md.append(f"> **Serviço:** `{args.service_name}` (`{service_path}`) | **Severidade Máxima:** `{max_sev}`")
    md.append(f"> **Workflow Run:** [#{run_number}]({run_url}) | **Branch:** `{branch}` | **Commit:** `{commit_sha[:8] if len(commit_sha)>=8 else commit_sha}`")
    md.append(f"> **Data/Hora:** `{now_utc}`")
    md.append("")
    md.append("## 📋 Resumo Executivo da IA")
    md.append(ai_result.get("executive_summary", "Problemas identificados durante o scan."))
    md.append("")
    md.append(f"## 🔍 Principais Problemas Identificados ({len(ai_result.get('findings', []))})")
    md.append("")
    md.append("| ID / CVE | Componente / Alvo | Severidade | Descrição & Impacto |")
    md.append("|---|---|---|---|")
    for f in ai_result.get("findings", []):
        f_id = f.get("id", "N/A")
        comp = f.get("component", "N/A")
        sev = f.get("severity", "UNKNOWN")
        desc = f.get("description", "").replace("\n", " ").replace("|", "\\|")
        md.append(f"| `{f_id}` | `{comp}` | **{sev}** | {desc} |")
    md.append("")
    md.append("## 💡 Como Solucionar (Plano de Remediação)")
    md.append(ai_result.get("action_plan", "Siga as orientações das ferramentas para corrigir os problemas."))
    md.append("")
    md.append("<details>")
    md.append("<summary>📦 Detalhes Técnicos e Remediações Individuais</summary>")
    md.append("")
    for f in ai_result.get("findings", []):
        md.append(f"### 🔸 {f.get('id')} — {f.get('component')}")
        md.append(f"- **Severidade:** {f.get('severity')}")
        md.append(f"- **Descrição:** {f.get('description')}")
        if f.get("remediation"):
            md.append(f"- **Remediação Sugerida:** {f.get('remediation')}")
        md.append("")
    md.append("</details>")
    md.append("")
    md.append("---")
    md.append("_Relatório analisado e sintetizado automaticamente via Google AI Studio (Gemini)._")

    output_content = "\n".join(md)
    with open(args.output_file, "w", encoding="utf-8") as out_f:
        out_f.write(output_content)

    print(f"[ai-issue-analyzer] Arquivo de Issue gerado com sucesso: {args.output_file}")
    set_github_output("create_issue", "true")
    set_github_output("issue_file", args.output_file)
    set_github_output("max_severity", max_sev)


if __name__ == "__main__":
    main()
