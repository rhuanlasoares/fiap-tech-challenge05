#!/usr/bin/env python3
"""
AI Issue Analyzer for GitHub Actions
Analisa relatórios de segurança (SCA, SAST, Container, DAST) e Lint utilizando
Google AI Studio (Gemini) para decidir com inteligência se uma Issue é necessária.
Garante suporte a múltiplos idiomas, com Português do Brasil (pt-BR) como padrão.
"""

import argparse
import datetime
import json
import os
import re
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


def auto_close_existing_issue(service_name: str, scan_type: str, tool_name: str, token: str, language: str = "pt-BR"):
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
                
                is_pt = language.lower() in ["pt-br", "pt", "portugues", "português"]
                if is_pt:
                    comment = (
                        f"✅ **Problema Resolvido**\n\n"
                        f"A verificação de pipeline `{tool_name}` (`{scan_type.upper()}`) para `{service_name}` "
                        f"não encontrou nenhuma vulnerabilidade no commit `{commit_sha}`.\n"
                        f"Fechando issue automaticamente via integração contínua."
                    )
                else:
                    comment = (
                        f"✅ **Issue Resolved**\n\n"
                        f"Pipeline scan `{tool_name}` (`{scan_type.upper()}`) for `{service_name}` "
                        f"found no remaining vulnerabilities in commit `{commit_sha}`.\n"
                        f"Closing issue automatically via continuous integration."
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
    """Faz o parse do arquivo de scan e retorna uma lista padronizada de achados."""
    findings = []
    
    # 1. Lint
    if scan_type.lower() == "lint":
        error_content, diff_content = "", ""
        if report_file and os.path.isfile(report_file):
            with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
                error_content = f.read().strip()
        if diff_file and os.path.isfile(diff_file):
            with open(diff_file, "r", encoding="utf-8", errors="ignore") as f:
                diff_content = f.read().strip()

        if not error_content and not diff_content:
            return []

        if error_content:
            for line in [l.strip() for l in error_content.splitlines() if l.strip()][:25]:
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
        return []

    try:
        with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read().strip()
        if not raw_text:
            return []
        data = json.loads(raw_text)
    except Exception:
        if raw_text:
            for line in [l.strip() for l in raw_text.splitlines() if l.strip()][:25]:
                findings.append({
                    "id": f"{tool_name.upper()}-ITEM",
                    "component": line.split(":")[0] if ":" in line else "arquivo",
                    "severity": "MEDIUM",
                    "title": line[:100],
                    "description": line,
                    "remediation": "Revisar código ou configuração."
                })
        return findings

    if isinstance(data, list) and scan_type.lower() != "dast":
        for item in data:
            findings.append({
                "id": item.get("code", "RULE"),
                "component": f"{item.get('file', 'Dockerfile')}:{item.get('line', '')}",
                "severity": str(item.get("level", "info")).upper(),
                "title": item.get("message", "Lint finding"),
                "description": item.get("message", ""),
                "remediation": "Ajuste a diretiva conforme recomendação da regra."
            })
        return findings

    # 2. SCA
    if scan_type.lower() == "sca":
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
                        "remediation": f"Atualizar {vuln.get('PkgName')} para a versão {vuln.get('FixedVersion', 'mais recente')}."
                    })

    # 3. SAST
    elif scan_type.lower() == "sast":
        if "Issues" in data: # Gosec
            for issue in data.get("Issues", []):
                findings.append({
                    "id": issue.get("rule_id", "GOSEC"),
                    "component": f"{issue.get('file', '')}:{issue.get('line', '')}",
                    "severity": issue.get("severity", "LOW").upper(),
                    "title": issue.get("details", "Problema de Segurança"),
                    "description": f"{issue.get('details', '')} (Trecho: {issue.get('code', '').strip()})",
                    "remediation": "Refatorar código para eliminar a vulnerabilidade identificada."
                })
        if "Results" in data: # Trivy Secrets
            for res in data.get("Results", []):
                target = res.get("Target", "código")
                for sec in res.get("Secrets", []) or []:
                    findings.append({
                        "id": sec.get("RuleID", "SECRET-EXPOSED"),
                        "component": f"{target}:{sec.get('StartLine', '')}",
                        "severity": sec.get("Severity", "CRITICAL").upper(),
                        "title": sec.get("Title", "Credencial Exposta"),
                        "description": f"Token detectado: {sec.get('Category', '')} - {sec.get('Title', '')}",
                        "remediation": "Remover do histórico git, rotacionar a chave e injetar via gerenciador de secrets."
                    })

    # 4. Container
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
                        "remediation": conf.get("Resolution", "Ajustar diretiva do Dockerfile.")
                    })
                for vuln in res.get("Vulnerabilities", []) or []:
                    findings.append({
                        "id": vuln.get("VulnerabilityID", "N/A"),
                        "component": f"{vuln.get('PkgName', 'unknown')} ({target})",
                        "severity": vuln.get("Severity", "UNKNOWN").upper(),
                        "title": vuln.get("Title") or vuln.get("VulnerabilityID", "Vulnerabilidade"),
                        "description": vuln.get("Description", "Sem descrição."),
                        "remediation": f"Atualizar imagem base ou pacote {vuln.get('PkgName')}."
                    })

    # 5. DAST (Ex: OWASP ZAP)
    elif scan_type.lower() == "dast":
        site_raw = data.get("site", []) if isinstance(data, dict) else []
        site_list = [site_raw] if isinstance(site_raw, dict) else (site_raw or [])
        for site in site_list:
            if not isinstance(site, dict):
                continue
            alerts_raw = site.get("alerts", [])
            alerts_list = [alerts_raw] if isinstance(alerts_raw, dict) else (alerts_raw or [])
            for alert in alerts_list:
                if not isinstance(alert, dict):
                    continue
                instances = alert.get("instances", [])
                first_uri = instances[0].get("uri") if instances and isinstance(instances[0], dict) else None
                endpoint = alert.get("url") or first_uri or site.get("@name", "Endpoint Desconhecido")
                
                # ZAP severities: High, Medium, Low, Informational
                raw_sev = alert.get("riskdesc", "LOW").split(" ")[0].upper()
                sev = "INFO" if raw_sev in ["INFORMATIONAL", "INFO"] else raw_sev

                findings.append({
                    "id": str(alert.get("pluginid", "DAST-ALERT")),
                    "component": endpoint,
                    "severity": sev,
                    "title": alert.get("name") or alert.get("alert", "Vulnerabilidade DAST"),
                    "description": alert.get("desc", "Sem descrição.").replace("<p>", "").replace("</p>", ""),
                    "remediation": alert.get("solution", "Verificar documentação de segurança para o endpoint.")
                })


    # 6. IaC (Terraform, CloudFormation, etc. — Trivy IaC, TFSec, Checkov)
    elif scan_type.lower() == "iac":
        # A. Trivy Misconfigurations (trivy config / trivy fs para IaC)
        if "Results" in data:
            for res in data.get("Results", []):
                target = res.get("Target", "terraform")
                for conf in res.get("Misconfigurations", []) or []:
                    cause = conf.get("CauseMetadata", {})
                    start_line = cause.get("StartLine", "")
                    loc = f"{target}:{start_line}" if start_line else target
                    code_lines = cause.get("Code", {}).get("Lines", [])
                    code_snippet = ""
                    if code_lines:
                        code_snippet = "\n".join([f"{l.get('Number')}: {l.get('Content', '').rstrip()}" for l in code_lines if l.get("Content")])

                    desc = conf.get("Description", "Sem descrição.")
                    msg = conf.get("Message", "")
                    full_desc = f"{msg}\n{desc}" if msg and msg != desc else desc
                    if code_snippet:
                        full_desc += f"\n\nCódigo afetado:\n```hcl\n{code_snippet}\n```"

                    findings.append({
                        "id": conf.get("ID", "IAC-MISCONFIG"),
                        "component": loc,
                        "severity": conf.get("Severity", "LOW").upper(),
                        "title": conf.get("Title", "Configuração Insegura de Infraestrutura"),
                        "description": full_desc.strip(),
                        "remediation": conf.get("Resolution", "Ajustar configuração nos arquivos HCL do Terraform.")
                    })
        # B. Formato nativo TFSec (JSON com chave 'results')
        elif "results" in data and isinstance(data.get("results"), list):
            for r in data.get("results", []):
                loc_data = r.get("location", {})
                fn = loc_data.get("filename", "terraform")
                ln = loc_data.get("start_line", "")
                comp = f"{fn}:{ln}" if ln else fn
                findings.append({
                    "id": r.get("rule_id") or r.get("long_id", "TFSEC-RULE"),
                    "component": comp,
                    "severity": r.get("severity", "LOW").upper(),
                    "title": r.get("rule_description") or r.get("description", "Vulnerabilidade IaC"),
                    "description": f"{r.get('explanation', '')} {r.get('description', '')}".strip(),
                    "remediation": r.get("resolution", "Ajustar os parâmetros inseguros do recurso Terraform.")
                })
        # C. Formato Checkov (JSON com chave 'results.failed_checks')
        elif "results" in data and isinstance(data.get("results"), dict):
            failed = data.get("results", {}).get("failed_checks", []) or []
            for fc in failed:
                fp = fc.get("file_path", "terraform")
                lines = fc.get("file_line_range", [])
                comp = f"{fp}:{lines[0]}" if lines else fp
                findings.append({
                    "id": fc.get("check_id", "CKV-RULE"),
                    "component": comp,
                    "severity": (fc.get("severity") or "HIGH").upper(),
                    "title": fc.get("check_name", "Violação de Política IaC"),
                    "description": f"{fc.get('check_name', '')} no arquivo {fp}.",
                    "remediation": fc.get("guideline") or "Revisar diretrizes do Checkov e corrigir a configuração."
                })

    return findings


def call_gemini_api(api_key: str, prompt: str, model: str = "gemini-1.5-flash") -> dict:
    """Chama a API do Google AI Studio com Structured JSON Output."""
    models_to_try = [model, "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    seen = set()
    models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                result_json = json.loads(resp.read().decode("utf-8"))
                text_response = result_json.get("candidates", [])[0].get("content", {}).get("parts", [])[0].get("text", "")
                return json.loads(text_response)
        except Exception as e:
            print(f"[ai-issue-analyzer] Falha com modelo {m}: {e}")
    return None


def generate_fallback_issue(scan_type: str, tool_name: str, service_name: str, findings: list, language: str = "pt-BR") -> dict:
    """Gera estrutura padrão caso a API do Gemini falhe ou não possua chave."""
    sev_counts = {f.get("severity", "LOW"): True for f in findings}
    max_sev = "CRITICAL" if "CRITICAL" in sev_counts else "HIGH" if "HIGH" in sev_counts else "MEDIUM" if "MEDIUM" in sev_counts else "LOW"

    is_pt = language.lower() in ["pt-br", "pt", "portugues", "português"]
    if is_pt:
        return {
            "should_create_issue": True,
            "max_severity": max_sev,
            "title_summary": f"{len(findings)} achados detectados ({max_sev})",
            "executive_summary": f"Identificados {len(findings)} achados de segurança/qualidade na ferramenta {tool_name} para o microsserviço {service_name}.",
            "findings": findings[:20],
            "action_checklist": ["Revisar vulnerabilidades e cabeçalhos de segurança apontados", "Aplicar correções recomendadas no código ou configuração"]
        }
    else:
        return {
            "should_create_issue": True,
            "max_severity": max_sev,
            "title_summary": f"{len(findings)} findings detected ({max_sev})",
            "executive_summary": f"Identified {len(findings)} findings in tool {tool_name} for microservice {service_name}.",
            "findings": findings[:20],
            "action_checklist": ["Review reported vulnerabilities and security headers", "Apply recommended fixes in service code or configuration"]
        }


def main():
    parser = argparse.ArgumentParser(description="AI Issue Analyzer with Gemini")
    parser.add_argument("--scan-type", required=True, choices=["lint", "sca", "sast", "container", "dast", "iac"])
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--report-file", default="")
    parser.add_argument("--diff-file", default="")
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--service-path", default="")
    parser.add_argument("--gemini-api-key", default=os.getenv("GEMINI_API_KEY", ""))
    parser.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN", os.getenv("GH_TOKEN", "")))
    parser.add_argument("--output-file", default="issue-ai.md")
    parser.add_argument("--model", default="gemini-1.5-flash")
    parser.add_argument("--language", default="pt-BR", help="Idioma para os relatórios e issues (ex: pt-BR, en-US)")

    args = parser.parse_args()
    service_path = args.service_path or args.service_name
    token = args.github_token
    lang = args.language or "pt-BR"
    is_pt = lang.lower() in ["pt-br", "pt", "portugues", "português"]
    lang_name = "Português do Brasil (pt-BR)" if is_pt else lang

    findings = parse_findings(args.scan_type, args.tool_name, args.report_file, args.diff_file)
    
    if not findings:
        print("[ai-issue-analyzer] ✅ Nenhum achado relevante. Nenhuma Issue será criada.")
        set_github_output("create_issue", "false")
        auto_close_existing_issue(args.service_name, args.scan_type, args.tool_name, token, lang)
        sys.exit(0)

    ai_result = None
    if args.gemini_api_key:
        prompt = f"""
Você é um especialista sênior em DevSecOps e AppSec. Analise os achados da ferramenta '{args.tool_name}' ({args.scan_type.upper()}) para o microsserviço '{args.service_name}'.
Achados brutos ({len(findings)} itens): {json.dumps(findings[:25], ensure_ascii=False)}

DIRETRIZES DE RESPOSTA E IDIOMA:
1. IDIOMA OBRIGATÓRIO: Você DEVE responder ESTRITAMENTE em {lang_name}. Todos os campos de texto no JSON ('title_summary', 'executive_summary', 'description', 'remediation', 'action_checklist') DEVEM estar em {lang_name}. Mesmo que as descrições brutas da ferramenta estejam em inglês, TRADUZA E EXPLIQUE em {lang_name}.
2. Avalie com precisão técnica se os achados justificam a abertura de uma Issue ('should_create_issue').
3. Defina a severidade máxima consolidada ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO').
4. 'executive_summary': Crie um resumo executivo direto e técnico em {lang_name} (1 parágrafo claro explicando o impacto real).
5. 'action_checklist': Forneça um array com ações diretas e imperativas em {lang_name} (ex: "Configurar cabeçalho X-Content-Type-Options: nosniff", "Definir Content-Security-Policy", "Atualizar dependência vulnerável").
6. DIRETRIZ IAC / TERRAFORM: Se o scan-type for 'IAC', explique os riscos de arquitetura em nuvem (exposição pública, dados sem criptografia, falha de IAM/least privilege) e no campo 'remediation' detalhe como solucionar fornecendo exemplos práticos em HCL (Terraform).

Responda ESTRITAMENTE neste formato JSON schema:
{{
  "should_create_issue": true,
  "max_severity": "CRITICAL",
  "title_summary": "resumo conciso para o título da issue em {lang_name}",
  "executive_summary": "resumo executivo do impacto em {lang_name}",
  "findings": [
    {{ "id": "ID-REGRA", "component": "endpoint_ou_arquivo", "severity": "HIGH", "description": "explicação do problema em {lang_name}", "remediation": "como corrigir em {lang_name}" }}
  ],
  "action_checklist": ["Ação corretiva 1 em {lang_name}", "Ação corretiva 2 em {lang_name}"]
}}
"""
        ai_result = call_gemini_api(args.gemini_api_key, prompt, args.model)

    if not ai_result:
        ai_result = generate_fallback_issue(args.scan_type, args.tool_name, args.service_name, findings, lang)

    if not ai_result.get("should_create_issue", True):
        print("[ai-issue-analyzer] ℹ️ Achados ignorados pela IA. Nenhuma issue será criada.")
        set_github_output("create_issue", "false")
        sys.exit(0)

    # Definição de Cores/Alertas baseada na Severidade
    max_sev = ai_result.get("max_severity", "HIGH").upper()
    alert_type = "[!CAUTION]" if max_sev == "CRITICAL" else "[!IMPORTANT]" if max_sev == "HIGH" else "[!WARNING]"
    
    default_title = "Vulnerabilidades Identificadas" if is_pt else "Identified Vulnerabilities"
    title_summary = ai_result.get("title_summary", default_title)
    is_iac = args.scan_type.lower() == "iac"
    clean_tool_label = re.sub(r'[^a-zA-Z0-9_-]', '', args.tool_name.lower().replace(" ", "-"))
    labels = ["security", args.scan_type.lower(), clean_tool_label, max_sev.lower()]
    if is_iac and "terraform" not in labels:
        labels.append("terraform")
    labels = [l for l in dict.fromkeys(labels) if l]
    
    # Metadata do GitHub
    run_url = f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/{os.getenv('GITHUB_REPOSITORY', 'repo')}/actions/runs/{os.getenv('GITHUB_RUN_ID', 'local')}"
    commit_sha = os.getenv("GITHUB_SHA", "main")
    
    # Geração do Markdown (Localizado para o idioma definido)
    if is_pt:
        header_title = f"# 🛡️ Triagem de Segurança: {args.tool_name}"
        target_label_txt = "Componente IaC" if is_iac else "Microsserviço"
        meta_service = f"> **{target_label_txt}:** `{args.service_name}` | **Severidade Máxima:** `{max_sev}`"
        meta_origin = f"> **Origem:** [Execução da Pipeline]({run_url}) | **Commit:** `{commit_sha[:7]}`"
        sec_summary = "## 📝 Resumo Executivo"
        sec_checklist = "## 🛠️ Plano de Ação (Checklist)"
        checklist_intro = "Marque as caixas abaixo conforme as correções forem aplicadas no código:"
        sec_details = "## 🔍 Detalhamento das Vulnerabilidades"
        table_headers = "| ID / Regra | Componente | Severidade | Ação Necessária |"
        expand_text = "<summary><strong>📦 Expandir Descrições Técnicas Completas</strong></summary>"
        target_label = "- **Alvo:**"
        context_label = "- **Contexto Técnico:**"
        footer_text = f"🤖 *Análise gerada via Google Gemini em {lang_name}. Avalie o contexto antes de aplicar mudanças estruturais.*"
    else:
        header_title = f"# 🛡️ Security Triage: {args.tool_name}"
        meta_service = f"> **Microservice:** `{args.service_name}` | **Max Severity:** `{max_sev}`"
        meta_origin = f"> **Origin:** [Pipeline Run]({run_url}) | **Commit:** `{commit_sha[:7]}`"
        sec_summary = "## 📝 Executive Summary"
        sec_checklist = "## 🛠️ Action Plan (Checklist)"
        checklist_intro = "Check the boxes below as fixes are applied to the codebase:"
        sec_details = "## 🔍 Vulnerability Breakdown"
        table_headers = "| Rule / ID | Component | Severity | Recommended Action |"
        expand_text = "<summary><strong>📦 Expand Detailed Descriptions</strong></summary>"
        target_label = "- **Target:**"
        context_label = "- **Technical Context:**"
        footer_text = f"🤖 *Analysis generated via Google Gemini ({lang}). Review context before applying structural changes.*"

    md = [
        "---",
        f"title: '[{args.scan_type.upper()}][{args.service_name}] {max_sev}: {title_summary}'",
        f"labels: [{', '.join([f'\"{l}\"' for l in labels])}]",
        "---",
        "",
        header_title,
        "",
        f"> {alert_type}",
        meta_service,
        meta_origin,
        "",
        sec_summary,
        ai_result.get("executive_summary", "Problemas identificados durante a esteira de CI/CD."),
        "",
        sec_checklist,
        checklist_intro
    ]

    for task in ai_result.get("action_checklist", []):
        md.append(f"- [ ] {task}")

    md.extend([
        "",
        sec_details,
        "",
        table_headers,
        "|---|---|---|---|"
    ])

    for f in ai_result.get("findings", []):
        f_id = f.get("id", "N/A")
        comp = f.get("component", "N/A")
        sev = f.get("severity", "UNKNOWN")
        remed = f.get("remediation", "").replace("\n", " ")
        md.append(f"| `{f_id}` | `{comp}` | **{sev}** | {remed} |")

    md.extend([
        "",
        "<details>",
        expand_text,
        ""
    ])

    for f in ai_result.get("findings", []):
        md.extend([
            f"### 🔸 {f.get('id')} ({f.get('severity')})",
            f"{target_label} `{f.get('component')}`",
            f"{context_label} {f.get('description')}",
            ""
        ])

    md.extend([
        "</details>",
        "",
        "---",
        footer_text
    ])

    with open(args.output_file, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(md))

    set_github_output("create_issue", "true")
    set_github_output("issue_file", args.output_file)
    set_github_output("max_severity", max_sev)

if __name__ == "__main__":
    main()
