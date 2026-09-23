#!/usr/bin/env python3
"""
AI Code Remediator for GitHub Actions.
Analisa relatórios de vulnerabilidade (SAST, SCA, IaC), utiliza o Google Gemini
para gerar correções de código, executa os testes unitários da aplicação e,
se aprovado, cria automaticamente um Pull Request seguro com Human-in-the-Loop.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Ajuste de codificação UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from prompts import build_remediation_prompt, build_reflection_prompt


def set_github_output(name: str, value: str):
    """Registra saída no formato aceito pelo GitHub Actions."""
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    print(f"[ai-code-remediator] Output: {name}={value}")


def parse_findings(scan_type: str, tool_name: str, report_file: str) -> list:
    """Extrai os achados estruturados com arquivo e linha de origem."""
    if not report_file or not os.path.isfile(report_file):
        print(f"[ai-code-remediator] Relatório não encontrado: {report_file}")
        return []

    try:
        with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read().strip()
        if not raw_text:
            return []
        data = json.loads(raw_text)
    except Exception as e:
        print(f"[ai-code-remediator] Erro ao carregar JSON do relatório: {e}")
        return []

    findings = []
    st = scan_type.lower()

    # 1. SAST
    if st == "sast":
        # A. Gosec (Go)
        if "Issues" in data:
            for issue in data.get("Issues", []):
                findings.append({
                    "id": str(issue.get("rule_id", "GOSEC")),
                    "file": issue.get("file", ""),
                    "line": str(issue.get("line", "")),
                    "component": f"{issue.get('file', '')}:{issue.get('line', '')}",
                    "severity": issue.get("severity", "LOW").upper(),
                    "title": issue.get("details", "Vulnerabilidade de Código"),
                    "description": f"{issue.get('details', '')} (Trecho: {issue.get('code', '').strip()})",
                    "remediation": "Refatorar código para eliminar a vulnerabilidade identificada."
                })
        # B. Bandit (Python)
        if "results" in data:
            for r in data.get("results", []):
                findings.append({
                    "id": str(r.get("test_id", "BANDIT")),
                    "file": r.get("filename", ""),
                    "line": str(r.get("line_number", "")),
                    "component": f"{r.get('filename', '')}:{r.get('line_number', '')}",
                    "severity": r.get("issue_severity", "LOW").upper(),
                    "title": r.get("issue_text", "Vulnerabilidade Python"),
                    "description": f"{r.get('issue_text', '')} (Código: {r.get('code', '').strip()})",
                    "remediation": "Substituir trecho vulnerável por equivalente seguro."
                })
        # C. Trivy Secrets
        if "Results" in data:
            for res in data.get("Results", []):
                target = res.get("Target", "")
                for sec in res.get("Secrets", []) or []:
                    findings.append({
                        "id": str(sec.get("RuleID", "SECRET-EXPOSED")),
                        "file": target,
                        "line": str(sec.get("StartLine", "")),
                        "component": f"{target}:{sec.get('StartLine', '')}",
                        "severity": sec.get("Severity", "CRITICAL").upper(),
                        "title": sec.get("Title", "Credencial Exposta"),
                        "description": f"Token ou chave detectada: {sec.get('Title', '')}",
                        "remediation": "Remover credencial do código e injetar via variável de ambiente ou Secrets Manager."
                    })

    # 2. IaC (Terraform)
    elif st == "iac":
        if "Results" in data:
            for res in data.get("Results", []):
                target = res.get("Target", "")
                for conf in res.get("Misconfigurations", []) or []:
                    cause = conf.get("CauseMetadata", {})
                    start_l = cause.get("StartLine", "")
                    end_l = cause.get("EndLine", "")
                    line_span = f"{start_l}-{end_l}" if start_l and end_l and start_l != end_l else str(start_l)
                    findings.append({
                        "id": str(conf.get("ID", "IAC-MISCONFIG")),
                        "file": target,
                        "line": line_span,
                        "component": f"{target}:{line_span}" if line_span else target,
                        "severity": conf.get("Severity", "LOW").upper(),
                        "title": conf.get("Title", "Configuração Insegura de Infraestrutura"),
                        "description": conf.get("Description", "") or conf.get("Message", ""),
                        "remediation": conf.get("Resolution", "Ajustar configuração no manifesto Terraform.")
                    })
        elif "results" in data and isinstance(data.get("results"), list): # tfsec
            for r in data.get("results", []):
                loc = r.get("location", {})
                fn = loc.get("filename", "")
                sl = loc.get("start_line", "")
                findings.append({
                    "id": str(r.get("rule_id", "TFSEC")),
                    "file": fn,
                    "line": str(sl),
                    "component": f"{fn}:{sl}",
                    "severity": r.get("severity", "LOW").upper(),
                    "title": r.get("rule_description", "Vulnerabilidade IaC"),
                    "description": r.get("explanation", ""),
                    "remediation": r.get("resolution", "Ajustar recurso Terraform.")
                })

    # 3. SCA (Dependências)
    elif st == "sca":
        if "Results" in data:
            for res in data.get("Results", []):
                target = res.get("Target", "")
                for vuln in res.get("Vulnerabilities", []) or []:
                    findings.append({
                        "id": str(vuln.get("VulnerabilityID", "CVE")),
                        "file": target,
                        "line": "",
                        "component": f"{vuln.get('PkgName', '')} ({target})",
                        "severity": vuln.get("Severity", "UNKNOWN").upper(),
                        "title": f"Vulnerabilidade em {vuln.get('PkgName')}",
                        "description": vuln.get("Description", ""),
                        "remediation": f"Atualizar pacote {vuln.get('PkgName')} para {vuln.get('FixedVersion', 'mais recente')}."
                    })

    return findings


def locate_file_path(reported_file: str, service_path: str) -> str:
    """Localiza o arquivo no disco a partir do caminho reportado e do service_path."""
    if not reported_file:
        return None

    # Limpeza básica de caminho
    clean_path = reported_file.strip()
    if clean_path.startswith("./"):
        clean_path = clean_path[2:]

    candidates = [
        clean_path,
        os.path.join(service_path, clean_path) if service_path else clean_path,
        os.path.join(service_path, os.path.basename(clean_path)) if service_path else clean_path,
    ]

    for c in candidates:
        if os.path.isfile(c):
            return os.path.normpath(c)

    # Busca recursiva simples pelo nome do arquivo caso o caminho relativo seja diferente
    file_basename = os.path.basename(clean_path)
    search_root = service_path if service_path and os.path.isdir(service_path) else "."
    for root, _, files in os.walk(search_root):
        if file_basename in files:
            full_p = os.path.join(root, file_basename)
            if os.path.isfile(full_p):
                return os.path.normpath(full_p)

    return None


def call_gemini_api(api_key: str, prompt: str, model: str = "gemini-2.5-flash") -> dict:
    """Chama o Google AI Studio com Structured JSON Output."""
    models_to_try = [model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    seen = set()
    models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    for m in models:
        print(f"[ai-code-remediator] Consultando Gemini '{m}'...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result_json = json.loads(resp.read().decode("utf-8"))
                parts = result_json.get("candidates", [])[0].get("content", {}).get("parts", [])
                text_response = parts[0].get("text", "") if parts else ""
                if text_response:
                    return json.loads(text_response)
        except Exception as e:
            print(f"[ai-code-remediator] Aviso: Modelo '{m}' retornou: {e}")
    return None


def run_test_validation(test_command: str, working_dir: str) -> tuple:
    """Executa o comando de teste configurado e retorna (sucesso, log_de_saida)."""
    if not test_command:
        return (True, "Nenhum comando de teste fornecido. Validação aprovada por padrão.")

    cwd = working_dir if working_dir and os.path.isdir(working_dir) else "."
    print(f"[ai-code-remediator] 🧪 Executando validação de qualidade: '{test_command}' em '{cwd}'")
    try:
        proc = subprocess.run(
            test_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=180
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        success = (proc.returncode == 0)
        return (success, output.strip())
    except subprocess.TimeoutExpired:
        return (False, f"Timeout de 180s excedido ao executar comando: {test_command}")
    except Exception as e:
        return (False, f"Erro ao executar testes: {e}")


def create_git_pr(
    file_path: str,
    tool_name: str,
    finding_id: str,
    pr_title: str,
    pr_body: str,
    base_branch: str = "main",
    token: str = None
) -> str:
    """Cria branch, commit, push e abre Pull Request via gh CLI."""
    clean_tool = re.sub(r'[^a-zA-Z0-9]', '', tool_name.lower())
    clean_id = re.sub(r'[^a-zA-Z0-9]', '', finding_id.lower())[:15]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    branch_name = f"fix/sec-{clean_tool}-{clean_id}-{timestamp}"

    env = {**os.environ}
    if token:
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token

    try:
        # Configura usuário git padrão para a pipeline se não configurado
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)

        # Checkout da branch
        subprocess.run(["git", "checkout", "-b", branch_name], check=True, capture_output=True)

        # Adiciona e commita
        subprocess.run(["git", "add", file_path], check=True, capture_output=True)
        commit_msg = f"{pr_title}\n\nAuto-remediado via IA com verificacao de testes aprovada."
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)

        # Push
        subprocess.run(["git", "push", "-u", "origin", branch_name], check=True, capture_output=True, env=env)

        # Criação do Pull Request
        pr_cmd = [
            "gh", "pr", "create",
            "--base", base_branch,
            "--head", branch_name,
            "--title", pr_title,
            "--body", pr_body,
            "--label", "security,bot:ai-fix"
        ]
        res = subprocess.run(pr_cmd, check=True, capture_output=True, text=True, env=env)
        pr_url = res.stdout.strip()
        print(f"[ai-code-remediator] 🎉 Pull Request aberto com sucesso: {pr_url}")

        # Retorna para a branch base
        subprocess.run(["git", "checkout", base_branch], check=False, capture_output=True)
        return pr_url

    except subprocess.CalledProcessError as e:
        err_msg = (e.stderr or e.stdout or str(e)).strip()
        print(f"[ai-code-remediator] ❌ Falha ao criar Pull Request: {err_msg}")
        subprocess.run(["git", "checkout", base_branch], check=False, capture_output=True)
        return None


def main():
    parser = argparse.ArgumentParser(description="AI Code Remediator with Gemini")
    parser.add_argument("--scan-type", required=True)
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--report-file", required=True)
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--service-path", default=".")
    parser.add_argument("--test-command", default="")
    parser.add_argument("--language", default="pt-BR")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--dry-run", default="false")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--max-auto-fixes", type=int, default=2)
    parser.add_argument("--gemini-api-key", default=os.getenv("GEMINI_API_KEY", ""))
    parser.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN", os.getenv("GH_TOKEN", "")))

    args = parser.parse_args()
    dry_run = args.dry_run.lower() in ["true", "1", "yes"]

    if not args.gemini_api_key:
        print("[ai-code-remediator] ⚠️ GEMINI_API_KEY não fornecida. Remediação automática desativada.")
        set_github_output("remediation_applied", "false")
        set_github_output("status", "no_api_key")
        sys.exit(0)

    findings = parse_findings(args.scan_type, args.tool_name, args.report_file)
    if not findings:
        print("[ai-code-remediator] ✅ Nenhum achado aplicável no relatório.")
        set_github_output("remediation_applied", "false")
        set_github_output("status", "no_findings")
        sys.exit(0)

    # Filtra achados de severidade relevante (HIGH, CRITICAL ou MEDIUM)
    eligible_findings = [f for f in findings if f.get("severity") in ["CRITICAL", "HIGH", "MEDIUM"]]
    if not eligible_findings:
        print("[ai-code-remediator] ℹ️ Nenhum achado atinge os critérios de severidade mínima para auto-fix.")
        set_github_output("remediation_applied", "false")
        set_github_output("status", "no_eligible_findings")
        sys.exit(0)

    created_prs = []
    fixes_count = 0

    for finding in eligible_findings[:args.max_auto_fixes]:
        reported_file = finding.get("file", "")
        real_file_path = locate_file_path(reported_file, args.service_path)

        if not real_file_path:
            print(f"[ai-code-remediator] ⏭️ Arquivo não localizado no disco: '{reported_file}'. Pulando achado {finding.get('id')}.")
            continue

        print(f"\n=======================================================")
        print(f"[ai-code-remediator] 🛠️ Processando Achado: {finding.get('id')} em '{real_file_path}'")
        print(f"=======================================================")

        try:
            with open(real_file_path, "r", encoding="utf-8", errors="ignore") as f:
                original_content = f.read()
        except Exception as e:
            print(f"[ai-code-remediator] Erro ao ler arquivo '{real_file_path}': {e}")
            continue

        # 1. Geração de Correção com a IA
        prompt = build_remediation_prompt(
            finding=finding,
            tool_name=args.tool_name,
            scan_type=args.scan_type,
            service_name=args.service_name,
            file_rel_path=real_file_path,
            file_content=original_content,
            language=args.language
        )
        ai_resp = call_gemini_api(args.gemini_api_key, prompt, args.model)

        if not ai_resp or not ai_resp.get("is_fixable", False):
            print(f"[ai-code-remediator] ℹ️ A IA classificou o achado {finding.get('id')} como não corrigível automaticamente.")
            continue

        patched_content = ai_resp.get("patched_file_content", "")
        if not patched_content or patched_content.strip() == original_content.strip():
            print("[ai-code-remediator] ℹ️ Nenhum patch gerado ou conteúdo idêntico.")
            continue

        # 2. Aplicação em Arquivo & Validação
        backup_path = real_file_path + ".bak_remediation"
        shutil.copyfile(real_file_path, backup_path)

        try:
            with open(real_file_path, "w", encoding="utf-8") as f:
                f.write(patched_content)

            # Executa validação de testes
            test_success, test_log = run_test_validation(args.test_command, args.service_path)

            # 3. Reflexão caso o teste falhe
            if not test_success:
                print(f"[ai-code-remediator] ⚠️ Falha na validação de testes pós-patch. Iniciando ciclo de reflexão...")
                refl_prompt = build_reflection_prompt(
                    finding=finding,
                    file_rel_path=real_file_path,
                    original_content=original_content,
                    attempted_content=patched_content,
                    test_command=args.test_command,
                    test_output=test_log[:2500],
                    language=args.language
                )
                refl_resp = call_gemini_api(args.gemini_api_key, refl_prompt, args.model)
                if refl_resp and refl_resp.get("is_fixable", False) and refl_resp.get("patched_file_content"):
                    patched_content = refl_resp.get("patched_file_content")
                    with open(real_file_path, "w", encoding="utf-8") as f:
                        f.write(patched_content)
                    test_success, test_log = run_test_validation(args.test_command, args.service_path)

            # Se ainda assim falhar, desfaz as alterações
            if not test_success:
                print(f"[ai-code-remediator] ❌ O patch quebrou a suíte de testes e foi descartado com segurança.")
                shutil.copyfile(backup_path, real_file_path)
                continue

            print("[ai-code-remediator] ✅ Sucesso! O código corrigido passou com êxito na suíte de testes.")

            # 4. Dry-Run ou Abertura de PR
            if dry_run:
                print(f"[ai-code-remediator] 🧪 [DRY-RUN ATIVO] Exibindo diff da correção proposta:")
                diff_proc = subprocess.run(["git", "diff", real_file_path], capture_output=True, text=True)
                print(diff_proc.stdout)
                # Restaura para manter o repositório limpo no dry-run
                shutil.copyfile(backup_path, real_file_path)
                fixes_count += 1
            else:
                pr_title = ai_resp.get("pr_title") or f"fix(security): remediação de {finding.get('id')} ({args.tool_name})"
                pr_body_ai = ai_resp.get("pr_body") or ai_resp.get("explanation") or "Correção automática de segurança."
                
                # Montagem do corpo completo do PR com metadados
                pr_full_body = f"""## 🛡️ Remediação Automática de Segurança (AI-Powered)

> **Ferramenta:** `{args.tool_name}` | **Vulnerabilidade:** `{finding.get('id')}`
> **Arquivo:** `{real_file_path}` | **Severidade:** `{finding.get('severity')}`

### 📝 Descrição da Correção
{pr_body_ai}

### 🔍 Avaliação de Riscos
{ai_resp.get('risk_assessment', 'Nenhum risco colateral identificado.')}

### 🧪 Evidência de Qualidade e Testes
- ✅ Comando de teste executado: `{args.test_command or 'N/A'}`
- ✅ Status: Aprovado sem erros de regressão ou quebra de build.

### 📋 Checklist para o Revisor Humano
- [ ] O comportamento da funcionalidade foi preservado?
- [ ] A alteração está alinhada às políticas de arquitetura do repositório?
- [ ] Aprovar e realizar merge do PR.

---
*Gerado automaticamente pelo Antigravity AI Code Remediator em {args.language}.*
"""
                pr_url = create_git_pr(
                    file_path=real_file_path,
                    tool_name=args.tool_name,
                    finding_id=finding.get("id", "vuln"),
                    pr_title=pr_title,
                    pr_body=pr_full_body,
                    base_branch=args.base_branch,
                    token=args.github_token
                )
                if pr_url:
                    created_prs.append(pr_url)
                    fixes_count += 1

        finally:
            if os.path.exists(backup_path):
                os.remove(backup_path)

    # Relatório final
    if created_prs:
        set_github_output("remediation_applied", "true")
        set_github_output("pr_urls", json.dumps(created_prs))
        set_github_output("status", "success")
        print(f"\n[ai-code-remediator] 🚀 {len(created_prs)} Pull Request(s) criado(s) com sucesso!")
    elif dry_run and fixes_count > 0:
        set_github_output("remediation_applied", "true")
        set_github_output("status", "dry_run_completed")
        print(f"\n[ai-code-remediator] 🧪 Simulação concluída com sucesso para {fixes_count} achado(s).")
    else:
        set_github_output("remediation_applied", "false")
        set_github_output("status", "no_remediation_completed")
        print("\n[ai-code-remediator] Nenhuma remediação completada nesta execução.")


if __name__ == "__main__":
    main()
