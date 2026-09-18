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
                    start_l = cause.get("StartLine", "")
                    end_l = cause.get("EndLine", "")
                    line_span = f"{start_l}-{end_l}" if start_l and end_l and start_l != end_l else str(start_l)
                    loc = f"{target}:{line_span}" if line_span else target
                    resource_name = cause.get("Resource", "")
                    code_lines = cause.get("Code", {}).get("Lines", [])
                    code_snippet = ""
                    if code_lines:
                        code_snippet = "\n".join([f"{l.get('Number')}: {l.get('Content', '').rstrip()}" for l in code_lines if l.get("Content")])

                    raw_desc = conf.get("Description", "").strip()
                    raw_msg = conf.get("Message", "").strip()
                    raw_title = conf.get("Title", "Configuração Insegura de Infraestrutura")
                    raw_resol = conf.get("Resolution", "Ajustar configuração nos arquivos HCL do Terraform.")

                    full_desc = f"{raw_msg}. {raw_desc}" if raw_msg and raw_msg not in raw_desc else (raw_desc or raw_msg or "Configuração insegura detectada.")

                    findings.append({
                        "id": conf.get("ID", "IAC-MISCONFIG"),
                        "component": loc,
                        "resource": resource_name,
                        "severity": conf.get("Severity", "LOW").upper(),
                        "title": raw_title,
                        "description": full_desc.strip(),
                        "affected_code": code_snippet,
                        "how_to_improve": raw_resol,
                        "remediation": raw_resol,
                        "primary_url": conf.get("PrimaryURL", "")
                    })
        # B. Formato nativo TFSec (JSON com chave 'results')
        elif "results" in data and isinstance(data.get("results"), list):
            for r in data.get("results", []):
                loc_data = r.get("location", {})
                fn = loc_data.get("filename", "terraform")
                start_l = loc_data.get("start_line", "")
                end_l = loc_data.get("end_line", "")
                line_span = f"{start_l}-{end_l}" if start_l and end_l and start_l != end_l else str(start_l)
                comp = f"{fn}:{line_span}" if line_span else fn
                findings.append({
                    "id": r.get("rule_id") or r.get("long_id", "TFSEC-RULE"),
                    "component": comp,
                    "resource": r.get("resource", ""),
                    "severity": r.get("severity", "LOW").upper(),
                    "title": r.get("rule_description") or r.get("description", "Vulnerabilidade IaC"),
                    "description": f"{r.get('explanation', '')} {r.get('description', '')}".strip(),
                    "affected_code": "",
                    "how_to_improve": r.get("resolution", "Ajustar os parâmetros inseguros do recurso Terraform."),
                    "remediation": r.get("resolution", "Ajustar os parâmetros inseguros do recurso Terraform."),
                    "primary_url": r.get("links", [""])[0] if r.get("links") else ""
                })
        # C. Formato Checkov (JSON com chave 'results.failed_checks')
        elif "results" in data and isinstance(data.get("results"), dict):
            failed = data.get("results", {}).get("failed_checks", []) or []
            for fc in failed:
                fp = fc.get("file_path", "terraform")
                lines = fc.get("file_line_range", [])
                lines_str = f"{lines[0]}-{lines[1]}" if len(lines) > 1 else str(lines[0]) if lines else ""
                comp = f"{fp}:{lines_str}" if lines_str else fp
                findings.append({
                    "id": fc.get("check_id", "CKV-RULE"),
                    "component": comp,
                    "resource": fc.get("resource", ""),
                    "severity": (fc.get("severity") or "HIGH").upper(),
                    "title": fc.get("check_name", "Violação de Política IaC"),
                    "description": f"{fc.get('check_name', '')} no arquivo {fp}.",
                    "affected_code": "",
                    "how_to_improve": fc.get("guideline") or "Revisar diretrizes do Checkov e corrigir a configuração.",
                    "remediation": fc.get("guideline") or "Revisar diretrizes do Checkov e corrigir a configuração.",
                    "primary_url": ""
                })

    return findings


def call_gemini_api(api_key: str, prompt: str, model: str = "gemini-2.5-flash") -> dict:
    """Chama a API do Google AI Studio com Structured JSON Output."""
    models_to_try = [model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    seen = set()
    models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    for m in models:
        print(f"[ai-issue-analyzer] Tentando modelo Gemini '{m}' via Google AI Studio...")
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
                if text_response:
                    parsed = json.loads(text_response)
                    print(f"[ai-issue-analyzer] ✅ Sucesso! Análise recebida com sucesso do modelo '{m}'.")
                    return parsed
        except Exception as e:
            print(f"[ai-issue-analyzer] ❌ Falha com modelo '{m}': {e}")
    return None


IAC_DICTIONARY = {
    # DynamoDB
    "point in time recovery should be enabled to protect dynamodb table": "A recuperação contínua (Point-in-Time Recovery - PITR) deve estar habilitada na tabela DynamoDB",
    "enable point in time recovery": "Habilitar a recuperação contínua Point-in-Time Recovery (PITR)",
    "point-in-time recovery is not enabled": "A recuperação contínua Point-in-Time Recovery (PITR) não está habilitada",
    "dynamodb tables should use at rest encryption with a customer managed key": "Tabelas DynamoDB devem utilizar criptografia em repouso com chave gerenciada pelo cliente (KMS CMK)",
    "enable server side encryption with a customer managed key": "Habilitar criptografia em repouso com chave KMS gerenciada pelo cliente (CMK)",
    "table encryption does not use a customer-managed kms key": "A criptografia da tabela não utiliza uma chave KMS gerenciada pelo cliente (CMK)",
    # Firewall / VPC
    "limit firewall rules to necessary port ranges only": "Restringir regras de firewall apenas para as faixas de portas estritamente necessárias",
    "an ingress security group rule allows traffic from /0": "Regra de entrada de firewall permite tráfego público irrestrito (0.0.0.0/0)",
    "opening up ports to the public internet is generally to be avoided": "A exposição de portas para a internet pública (0.0.0.0/0) deve ser evitada para impedir ataques e explorações diretas",
    "set a more restrictive cidr range in the firewall rule": "Definir uma faixa CIDR restrita aos IPs corporativos ou utilizar o Cloud IAP / VPN",
    # Cloud SQL
    "ensure that cloud sql database instances are not open to the world": "Garantir que instâncias do Cloud SQL não estejam expostas com IP público aberto (0.0.0.0/0)",
    "ensure that cloud sql instances have ssl/tls enabled": "Exigir conexões criptografadas com SSL/TLS nas instâncias do Cloud SQL",
    # Storage / Buckets
    "ensure that cloud storage buckets have uniform bucket-level access enabled": "Garantir que os buckets do Cloud Storage tenham o controle de acesso uniforme ativado (uniform_bucket_level_access = true)",
    "ensure that storage buckets are encrypted using kms keys": "Garantir que os buckets de armazenamento sejam criptografados com chaves KMS gerenciadas pelo cliente",
    # GKE
    "ensure that gke cluster is not running with default service account": "Evitar executar o cluster GKE com a Service Account padrão do Compute Engine",
    "ensure that gke has stackdriver logging enabled": "Habilitar a coleta de logs do Cloud Operations (Stackdriver Logging) no GKE",
    "ensure that gke has stackdriver monitoring enabled": "Habilitar as métricas do Cloud Operations (Stackdriver Monitoring) no GKE",
}

def translate_to_portuguese(text: str) -> str:
    """Traduz com precisão técnica termos de segurança de infraestrutura para Português do Brasil."""
    if not text:
        return ""
    t = text.strip()
    low = t.lower().rstrip(".")
    if low in IAC_DICTIONARY:
        return IAC_DICTIONARY[low]
    for eng, pt in IAC_DICTIONARY.items():
        if eng in low:
            t = re.sub(re.escape(eng), pt, t, flags=re.IGNORECASE)

    replacements = [
        (r'(?i)point in time recovery should be enabled to protect dynamodb table', 'A recuperação contínua (PITR) deve estar ativada para proteger a tabela DynamoDB'),
        (r'(?i)dynamodb tables should be protected against accidentally or malicious write/delete actions by ensuring that there is adequate protection', 'As tabelas do DynamoDB devem ser protegidas contra gravações ou deleções acidentais e maliciosas, garantindo recuperação em caso de desastres'),
        (r'(?i)by enabling point-in-time-recovery you can restore to a known point in the event of loss of data', 'Ao habilitar o Point-in-Time Recovery (PITR), é possível restaurar a tabela para qualquer segundo nos últimos 35 dias em caso de perda ou corrupção de dados'),
        (r'(?i)using aws managed keys does not allow for fine grained control or rotation', 'O uso de chaves gerenciadas pela AWS não permite auditoria refinada via CloudTrail nem controle sobre a rotação das chaves criptográficas'),
        (r'(?i)limit firewall rules to necessary port ranges only', 'Restrinja as regras de firewall apenas para as faixas de portas estritamente necessárias'),
        (r'(?i)firewall rules should not allow unrestricted access to all ports', 'Regras de firewall não devem permitir acesso irrestrito a todas as portas ou intervalos desnecessários'),
        (r'(?i)is not enabled', 'não está habilitado(a)'),
        (r'(?i)should be enabled', 'deve estar habilitado(a)'),
        (r'(?i)should be protected', 'deve ser protegido(a)'),
        (r'(?i)should use', 'deve utilizar'),
        (r'(?i)does not use', 'não utiliza'),
        (r'(?i)to protect', 'para proteger'),
        (r'(?i)at rest encryption', 'criptografia em repouso'),
        (r'(?i)customer managed key', 'chave gerenciada pelo cliente (KMS CMK)'),
        (r'(?i)in the event of loss of data', 'em caso de perda ou corrupção de dados'),
        (r'(?i)must be enabled', 'deve estar habilitado'),
        (r'(?i)should not be exposed', 'não deve ser exposto'),
        (r'(?i)ensure that', 'garanta que'),
        (r'(?i)set a more restrictive', 'defina uma faixa mais restritiva de'),
        (r'(?i)or wide ranges unnecessarily', 'ou faixas excessivamente amplas'),
        (r'(?i)rule allows port range', 'A regra de firewall permite a faixa de portas'),
        (r'(?i)point-in-time recovery is not enabled', 'A recuperação contínua (PITR) não está habilitada'),
    ]
    for pattern, repl in replacements:
        t = re.sub(pattern, repl, t)
    return t


def generate_suggested_hcl_fix(finding_id: str, title: str, desc: str, resource_name: str, aff_code: str) -> str:
    """Gera automaticamente o bloco de código Terraform HCL corrigido para o achado."""
    combined = f"{finding_id} {title} {desc}".lower()

    # 1. DynamoDB PITR
    if "point in time" in combined or "aws-0024" in combined or "pitr" in combined:
        return (
            "# Adicione o bloco point_in_time_recovery no recurso da tabela DynamoDB:\n"
            "resource \"aws_dynamodb_table\" \"toggle_master_analytics\" {\n"
            "  name         = \"SolidaryTech\"\n"
            "  billing_mode = \"PROVISIONED\"\n"
            "  read_capacity  = 1\n"
            "  write_capacity = 1\n"
            "  hash_key       = \"event_id\"\n\n"
            "  # ✅ Ativação de Recuperação Contínua (PITR):\n"
            "  point_in_time_recovery {\n"
            "    enabled = true\n"
            "  }\n\n"
            "  attribute {\n"
            "    name = \"event_id\"\n"
            "    type = \"S\"\n"
            "  }\n"
            "}"
        )

    # 2. DynamoDB KMS Customer Managed Key
    if "customer managed" in combined or "aws-0025" in combined or ("dynamodb" in combined and "encryption" in combined):
        return (
            "# Adicione o bloco server_side_encryption com a chave KMS gerenciada pelo cliente:\n"
            "resource \"aws_dynamodb_table\" \"toggle_master_analytics\" {\n"
            "  name         = \"SolidaryTech\"\n"
            "  billing_mode = \"PROVISIONED\"\n"
            "  read_capacity  = 1\n"
            "  write_capacity = 1\n"
            "  hash_key       = \"event_id\"\n\n"
            "  # ✅ Criptografia em Repouso com Chave KMS Própria (CMK):\n"
            "  server_side_encryption {\n"
            "    enabled     = true\n"
            "    kms_key_arn = var.kms_key_arn # ou aws_kms_key.dynamo_key.arn\n"
            "  }\n"
            "}"
        )

    # 3. GCP Firewall Port Ranges
    if "gcp-0074" in combined or "necessary port ranges" in combined or "port ranges" in combined:
        return (
            "# Especifique apenas as portas estritamente necessárias no bloco allow:\n"
            "resource \"google_compute_firewall\" \"allow_health_check\" {\n"
            "  name    = \"allow-health-check-gke\"\n"
            "  network = \"projects/${var.project_id}/global/networks/${var.vpc_name}\"\n\n"
            "  allow {\n"
            "    protocol = \"tcp\"\n"
            "    # ✅ Especifique apenas as portas dos health checks ou serviços (ex: 80, 443, 10256):\n"
            "    ports    = [\"80\", \"443\", \"10256\"]\n"
            "  }\n\n"
            "  source_ranges = [\"130.211.0.0/22\", \"35.191.0.0/16\"]\n"
            "  direction     = \"INGRESS\"\n"
            "}"
        )

    # 4. Ingress 0.0.0.0/0
    if "0.0.0.0/0" in combined or "ingress" in combined or "avd-gcp-0001" in combined:
        return (
            "# Restrinja o source_ranges para a faixa de IPs autorizados ou Cloud IAP:\n"
            "resource \"google_compute_firewall\" \"allow_restricted\" {\n"
            "  name    = \"allow-restricted\"\n"
            "  network = google_compute_network.vpc.name\n\n"
            "  allow {\n"
            "    protocol = \"tcp\"\n"
            "    ports    = [\"22\"]\n"
            "  }\n\n"
            "  # ✅ Faixa segura do Identity-Aware Proxy (IAP) do GCP:\n"
            "  source_ranges = [\"35.235.240.0/20\"]\n"
            "}"
        )

    # 5. Cloud Storage Uniform Bucket Access
    if "uniform_bucket_level_access" in combined or "bucket" in combined:
        return (
            "# Ative o controle uniforme no nível de bucket:\n"
            "resource \"google_storage_bucket\" \"example\" {\n"
            "  name                        = \"meu-bucket-seguro\"\n"
            "  location                    = \"SOUTHAMERICA-EAST1\"\n"
            "  uniform_bucket_level_access = true\n"
            "}"
        )

    return (
        "# Revise os atributos do recurso e adicione os parâmetros de segurança recomendados:\n"
        "# Certifique-se de configurar criptografia, controle de acesso e auditoria conforme as melhores práticas."
    )


def generate_fallback_issue(scan_type: str, tool_name: str, service_name: str, findings: list, language: str = "pt-BR") -> dict:
    """Gera estrutura padrão e localizada caso a API do Gemini falhe ou não possua chave."""
    sev_counts = {f.get("severity", "LOW"): True for f in findings}
    max_sev = "CRITICAL" if "CRITICAL" in sev_counts else "HIGH" if "HIGH" in sev_counts else "MEDIUM" if "MEDIUM" in sev_counts else "LOW"

    is_pt = language.lower() in ["pt-br", "pt", "portugues", "português"]
    is_iac = scan_type.lower() == "iac"

    processed_findings = []
    for f in findings[:20]:
        item = dict(f)
        if is_pt:
            item["title"] = translate_to_portuguese(item.get("title", ""))
            item["description"] = translate_to_portuguese(item.get("description", ""))
            how = translate_to_portuguese(item.get("how_to_improve", "") or item.get("remediation", ""))
            item["how_to_improve"] = how
            item["remediation"] = how

            if is_iac and not item.get("suggested_fix_code"):
                item["suggested_fix_code"] = generate_suggested_hcl_fix(
                    item.get("id", ""),
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("resource", ""),
                    item.get("affected_code", "")
                )
        processed_findings.append(item)

    if is_pt:
        component_type = "componente de infraestrutura (IaC)" if is_iac else f"microsserviço {service_name}"
        return {
            "should_create_issue": True,
            "max_severity": max_sev,
            "title_summary": f"{len(findings)} vulnerabilidade(s) detectada(s) ({max_sev})",
            "executive_summary": f"Identificados {len(findings)} apontamento(s) de segurança/conformidade na ferramenta {tool_name} para o {component_type}. Revise as vulnerabilidades indicadas e aplique as correções recomendadas no código Terraform HCL.",
            "findings": processed_findings,
            "action_checklist": [
                "Revisar os recursos de infraestrutura e parâmetros apontados no código Terraform",
                "Substituir regras abertas (ex: 0.0.0.0/0) por faixas restritas ou Cloud IAP",
                "Aplicar as correções nos arquivos .tf e executar terraform validate antes do commit"
            ] if is_iac else [
                "Revisar vulnerabilidades e cabeçalhos de segurança apontados",
                "Aplicar correções recomendadas no código ou configuração"
            ]
        }
    else:
        return {
            "should_create_issue": True,
            "max_severity": max_sev,
            "title_summary": f"{len(findings)} findings detected ({max_sev})",
            "executive_summary": f"Identified {len(findings)} findings in tool {tool_name} for {service_name}.",
            "findings": processed_findings,
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
Você é um especialista sênior em DevSecOps, AppSec e Engenharia de Infraestrutura em Nuvem (Terraform/IaC).
Analise com rigor técnico os achados da ferramenta '{args.tool_name}' ({args.scan_type.upper()}) para o componente '{args.service_name}'.
Achados brutos ({len(findings)} itens): {json.dumps(findings[:25], ensure_ascii=False)}

DIRETRIZES FUNDAMENTAIS DE IDIOMA E LOCALIZAÇÃO:
1. IDIOMA MANDATÓRIO: Você DEVE responder ESTRITAMENTE em {lang_name}.
   - NUNCA retorne títulos, resumos, descrições ou soluções em inglês.
   - Todos os textos explicativos ('title_summary', 'executive_summary', 'title', 'description', 'how_to_improve', 'action_checklist') DEVEM estar 100% em {lang_name}.
   - Traduza termos técnicos em inglês para português claro e profissional.

DIRETRIZES DE SOLUÇÃO, LOCAL AFETADO E CÓDIGO TERRAFORM HCL:
2. Para CADA achado no array 'findings':
   - 'component': Mantenha o caminho exato do arquivo e linha(s) afetada(s) (ex: iac/terraform/modules/vpc/main.tf:45-52).
   - 'resource': Nome do recurso Terraform analisado (ex: google_compute_firewall.allow_ssh).
   - 'title': Título curto e objetivo em {lang_name} resumindo o problema.
   - 'description': Explique detalhadamente em {lang_name} o risco real em nuvem (ex: por que abrir 0.0.0.0/0 é perigoso, impacto de bucket público, falta de TLS, etc.).
   - 'affected_code': Mostre o trecho de código vulnerável atual (se disponível).
   - 'how_to_improve': Explique em {lang_name} o passo a passo de como solucionar e melhorar a infraestrutura.
   - 'suggested_fix_code': Forneça o bloco de código Terraform HCL CORRIGIDO completo (com comentários em {lang_name} explicando os parâmetros ajustados).

Responda ESTRITAMENTE neste formato JSON schema:
{{
  "should_create_issue": true,
  "max_severity": "CRITICAL",
  "title_summary": "resumo conciso para o título da issue em {lang_name}",
  "executive_summary": "resumo executivo do impacto em {lang_name}",
  "findings": [
    {{
      "id": "AVD-GCP-0001",
      "component": "iac/terraform/modules/vpc/main.tf:45-52",
      "resource": "google_compute_firewall.allow_ssh",
      "severity": "HIGH",
      "title": "Regra de firewall permite tráfego público irrestrito (0.0.0.0/0)",
      "description": "Explicação em {lang_name} do risco de segurança e impacto...",
      "affected_code": "resource \"google_compute_firewall\" \"allow_ssh\" { ... }",
      "how_to_improve": "Explicação em {lang_name} de como melhorar...",
      "suggested_fix_code": "resource \"google_compute_firewall\" \"allow_ssh\" {{\\n  # Exemplo de código HCL seguro...\\n}}"
    }}
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

    is_iac = args.scan_type.lower() == "iac"

    # Pós-processamento de garantia: assegurar que todos os campos estão em Português e têm código HCL
    if is_pt:
        for f in ai_result.get("findings", []):
            f["title"] = translate_to_portuguese(f.get("title", ""))
            f["description"] = translate_to_portuguese(f.get("description", ""))
            how = translate_to_portuguese(f.get("how_to_improve", "") or f.get("remediation", ""))
            f["how_to_improve"] = how
            f["remediation"] = how
            if is_iac and not f.get("suggested_fix_code"):
                f["suggested_fix_code"] = generate_suggested_hcl_fix(
                    f.get("id", ""),
                    f.get("title", ""),
                    f.get("description", ""),
                    f.get("resource", ""),
                    f.get("affected_code", "")
                )

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

    if is_iac:
        # Tabela executiva inicial
        md.extend([
            "",
            "## 📋 Resumo das Vulnerabilidades Detectadas",
            "",
            "| Regra / ID | Local Afetado | Severidade | Ação Recomendada |",
            "|---|---|---|---|"
        ])
        for f in ai_result.get("findings", []):
            f_id = f.get("id", "N/A")
            comp = f.get("component", "N/A")
            sev = f.get("severity", "UNKNOWN")
            short_act = (f.get("how_to_improve") or f.get("remediation", "")).split(".")[0].replace("\n", " ")
            md.append(f"| `{f_id}` | `{comp}` | **{sev}** | {short_act} |")

        md.extend([
            "",
            "## 🔍 Detalhamento dos Achados, Local Afetado & Como Solucionar",
            ""
        ])

        for f in ai_result.get("findings", []):
            f_id = f.get("id", "N/A")
            comp = f.get("component", "N/A")
            res_name = f.get("resource", "")
            res_line = f"\n- 🏷️ **Recurso Terraform:** `{res_name}`" if res_name else ""
            sev = f.get("severity", "UNKNOWN")
            title = f.get("title") or f_id
            desc = f.get("description", "Sem descrição disponível.")
            how_improve = f.get("how_to_improve") or f.get("remediation", "Revisar o recurso de infraestrutura e aplicar os princípios de segurança em nuvem.")
            aff_code = f.get("affected_code", "")
            fix_code = f.get("suggested_fix_code", "")

            md.extend([
                f"### 🔸 [{f_id}] {title} ({sev})",
                "",
                f"- 📍 **Local Afetado:** `{comp}`{res_line}",
                f"- ⚠️ **Diagnóstico & Risco:** {desc}",
                f"- 💡 **Como Poderia Melhorar:** {how_improve}",
                ""
            ])

            if aff_code and aff_code.strip():
                clean_aff = aff_code.strip()
                if not clean_aff.startswith("```"):
                    clean_aff = f"```hcl\n{clean_aff}\n```"
                md.extend([
                    "#### ❌ Trecho de Código Afetado Atual:",
                    clean_aff,
                    ""
                ])

            if fix_code and fix_code.strip():
                clean_fix = fix_code.strip()
                if not clean_fix.startswith("```"):
                    clean_fix = f"```hcl\n{clean_fix}\n```"
                md.extend([
                    "#### ✅ Sugestão de Código Corrigido (Terraform HCL):",
                    clean_fix,
                    ""
                ])

            md.append("---")
    else:
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
            "---"
        ])

    md.append(footer_text)

    with open(args.output_file, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(md))

    set_github_output("create_issue", "true")
    set_github_output("issue_file", args.output_file)
    set_github_output("max_severity", max_sev)

if __name__ == "__main__":
    main()
