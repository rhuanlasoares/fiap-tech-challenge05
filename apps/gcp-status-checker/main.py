#!/usr/bin/env python3
# ==============================================================================
# GCP Status Checker — Intelligent SRE Watchdog for Disaster Recovery
# Monitors GCP Official Incidents Feed, Manages State in Google Cloud Storage,
# Features Fast-Confirmation Loop (30s retries to avoid 15min delay),
# and Dispatches Automated Failover / Switchback via GitHub Actions REST API.
# ==============================================================================

import os
import sys
import re
import json
import time
import logging
from datetime import datetime, timezone
import requests

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("gcp-status-checker")

# Optional OpenTelemetry integration (graceful fallback if not running in cluster)
ENABLE_OTEL = os.getenv("ENABLE_OTEL", "false").strip().lower() in ("true", "1", "yes")
tracer = None

if ENABLE_OTEL:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create()
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter()
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        service_name = os.getenv("OTEL_SERVICE_NAME", "gcp-status-checker")
        tracer = trace.get_tracer(service_name)
    except Exception as otel_err:
        logger.warning(f"OpenTelemetry initialization skipped: {otel_err}")

# Configuration
TARGET_SERVICES_RAW = os.getenv("TARGET_SERVICES", "Cloud SQL,Google Kubernetes Engine")
TARGET_SERVICES = [s.strip() for s in TARGET_SERVICES_RAW.split(",") if s.strip()]
TARGET_REGION = os.getenv("TARGET_REGION", "southamerica-east1").strip().lower()

# Resilience Thresholds (Anti-Flapping / Hysteresis)
CONSECUTIVE_OUTAGE_THRESHOLD = int(os.getenv("CONSECUTIVE_OUTAGE_THRESHOLD", "3"))
CONSECUTIVE_HEALTHY_THRESHOLD = int(os.getenv("CONSECUTIVE_HEALTHY_THRESHOLD", "3"))

# Fast-Confirmation Mode (30s retries in-execution to avoid 15min waiting across crons)
FAST_CONFIRMATION_ENABLED = os.getenv("FAST_CONFIRMATION_ENABLED", "true").strip().lower() in ("true", "1", "yes")
FAST_CONFIRMATION_INTERVAL_SECONDS = int(os.getenv("FAST_CONFIRMATION_INTERVAL_SECONDS", "30"))

# Safety Gate & Automation Flags
AUTO_TRIGGER_DR = os.getenv("AUTO_TRIGGER_DR", "false").strip().lower() in ("true", "1", "yes")
REQUIRE_MANUAL_CONFIRMATION = os.getenv("REQUIRE_MANUAL_CONFIRMATION", "true").strip().lower() in ("true", "1", "yes")
DRY_RUN_DISPATCH = os.getenv("DR_DRY_RUN", "false").strip().lower() in ("true", "1", "yes")

# Integrations
GITHUB_REPO = os.getenv("GITHUB_REPO", "rhuanlasoares/fiap-tech-challenge05")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# GCS State Storage
GCS_STATE_BUCKET = os.getenv("GCS_STATE_BUCKET", "gcs-velero-bucket-solidary-tech-rh")
GCS_STATE_FILE = os.getenv("GCS_STATE_FILE", "gcp-status-checker-state.json")
LOCAL_STATE_FALLBACK = os.getenv("LOCAL_STATE_FALLBACK", "/tmp/gcp_dr_state.json")

# Simulation Mode
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "false").strip().lower() in ("true", "1", "yes")
SIMULATED_OUTAGE_SERVICES_RAW = os.getenv("SIMULATED_OUTAGE_SERVICES", "")
SIMULATED_OUTAGE_SERVICES = [s.strip().lower() for s in SIMULATED_OUTAGE_SERVICES_RAW.split(",") if s.strip()]

SERVICE_ALIASES = {
    "Cloud SQL": ["cloud sql", "sql"],
    "Google Kubernetes Engine": ["google kubernetes engine", "kubernetes engine", "gke", "kubernetes"],
    "Compute Engine": ["compute engine", "gce"],
    "Cloud Storage": ["cloud storage", "gcs"],
    "Artifact Registry": ["artifact registry", "gar"],
}

# ==============================================================================
# GCS State Storage Manager
# ==============================================================================
class GCSStateManager:
    """Manages the persistent state of consecutive failures/health in GCS."""
    def __init__(self, bucket_name: str, file_name: str):
        self.bucket_name = bucket_name
        self.file_name = file_name
        self.gcs_client = None
        try:
            from google.cloud import storage
            self.gcs_client = storage.Client()
        except Exception as e:
            logger.warning(f"Could not initialize Google Cloud Storage client: {e}. Using local state fallback.")

    def default_state(self) -> dict:
        return {
            "current_topology": "NORMAL",  # NORMAL, FAILOVER_SQL, FAILOVER_GKE, FAILOVER_FULL
            "consecutive_failures": {s: 0 for s in TARGET_SERVICES},
            "consecutive_healthy": {s: CONSECUTIVE_HEALTHY_THRESHOLD for s in TARGET_SERVICES},
            "active_incident_ids": [],
            "last_action_dispatched": "none",
            "last_checked_at": None,
            "last_status_change_at": None,
        }

    def load_state(self) -> dict:
        if self.gcs_client and self.bucket_name:
            try:
                bucket = self.gcs_client.bucket(self.bucket_name)
                blob = bucket.blob(self.file_name)
                if blob.exists():
                    data = json.loads(blob.download_as_text())
                    logger.info(f"Loaded DR state from gs://{self.bucket_name}/{self.file_name}: Topology={data.get('current_topology')}")
                    return data
            except Exception as e:
                logger.warning(f"Failed to read state from GCS: {e}. Trying local fallback.")

        # Local fallback
        if os.path.exists(LOCAL_STATE_FALLBACK):
            try:
                with open(LOCAL_STATE_FALLBACK, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read local fallback state: {e}")

        logger.info("Initializing new default DR state.")
        return self.default_state()

    def save_state(self, state: dict):
        state["last_checked_at"] = datetime.now(timezone.utc).isoformat()
        state_json = json.dumps(state, indent=2)

        # Write to GCS
        saved_gcs = False
        if self.gcs_client and self.bucket_name:
            try:
                bucket = self.gcs_client.bucket(self.bucket_name)
                blob = bucket.blob(self.file_name)
                blob.upload_from_string(state_json, content_type="application/json")
                logger.info(f"Saved updated state to gs://{self.bucket_name}/{self.file_name}")
                saved_gcs = True
            except Exception as e:
                logger.warning(f"Failed to save state to GCS: {e}")

        # Local cache
        try:
            with open(LOCAL_STATE_FALLBACK, "w", encoding="utf-8") as f:
                f.write(state_json)
        except Exception as e:
            logger.warning(f"Failed to save local state fallback: {e}")

        return saved_gcs

# ==============================================================================
# Helper Functions
# ==============================================================================
def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', text.lower()).strip('_')

def matches_service(service: str, incident: dict) -> bool:
    aliases = SERVICE_ALIASES.get(service, [service.lower()])
    service_name_incident = (incident.get("service_name") or "").lower()
    for alias in aliases:
        if alias in service_name_incident:
            return True
    for prod in incident.get("affected_products", []):
        title = (prod.get("title") or "").lower()
        for alias in aliases:
            if alias in title:
                return True
    if "multiple" in service_name_incident or not incident.get("affected_products"):
        desc = (incident.get("external_desc") or "").lower()
        for alias in aliases:
            if alias in desc:
                return True
    return False

def matches_region(incident: dict, target_region: str) -> bool:
    if not target_region:
        return True
    locations = incident.get("currently_affected_locations", [])
    if not locations:
        return True
    for loc in locations:
        loc_id = (loc.get("id") or "").lower()
        loc_title = (loc.get("title") or "").lower()
        if target_region in loc_id or target_region in loc_title or "global" in loc_id:
            return True
    return False

def send_slack_notification(title: str, message: str, severity: str, action: str, dry_run: bool):
    """Sends structured incident & DR execution card to Slack."""
    if not SLACK_WEBHOOK_URL:
        logger.info(f"[SLACK DISABLED] {title}: {message}")
        return

    color = "#FF0000" if severity == "CRITICAL" else "#FFA500" if severity == "WARNING" else "#36A64F"
    workflow_url = f"https://github.com/{GITHUB_REPO}/actions/workflows/disaster-recovery.yaml"

    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"🛡️ [GCP Status Watchdog] {title}",
                "title_link": workflow_url,
                "text": message,
                "fields": [
                    {"title": "Severidade", "value": severity, "short": True},
                    {"title": "Ação Proposta / Executada", "value": f"`{action}`", "short": True},
                    {"title": "Região Alvo", "value": TARGET_REGION, "short": True},
                    {"title": "Modo Dry-Run", "value": str(dry_run), "short": True},
                    {"title": "Aprovação Manual Requerida", "value": str(REQUIRE_MANUAL_CONFIRMATION), "short": True},
                    {"title": "Workflow GitHub Actions", "value": f"<{workflow_url}|Abrir Pipeline de DR>", "short": False}
                ],
                "footer": "SolidaryTech — Autonomous SRE Watchdog",
                "ts": int(datetime.now(timezone.utc).timestamp())
            }
        ]
    }

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            logger.info("Slack alert successfully dispatched.")
        else:
            logger.warning(f"Slack webhook returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to dispatch Slack alert: {e}")

def trigger_github_dr_workflow(action: str, dry_run: bool = False) -> bool:
    """Triggers the disaster-recovery.yaml workflow in GitHub Actions via REST API."""
    if not GITHUB_TOKEN:
        logger.error("Cannot dispatch GitHub workflow: GITHUB_TOKEN is not configured!")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/disaster-recovery.yaml/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    payload = {
        "ref": "main",
        "inputs": {
            "action": action,
            "service": "all",
            "dry_run": dry_run,
            "confirmation": "CONFIRMAR-DR" if not dry_run else ""
        }
    }

    logger.info(f"Dispatching GitHub Actions workflow ({url}) with action={action}, dry_run={dry_run}...")

    if dry_run or GITHUB_TOKEN.startswith("mock-"):
        logger.info(f"[DRY-RUN / MOCK] Simulação ativa de dispatch no GitHub Actions para ação '{action}'. Retornando sucesso.")
        return True

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code == 204:
            logger.info(f"SUCCESS! GitHub Actions DR workflow dispatched successfully for action '{action}'.")
            return True
        else:
            logger.error(f"Failed to dispatch GitHub Actions workflow. HTTP {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Exception during GitHub Actions dispatch: {e}")
        return False

def fetch_and_evaluate_services() -> tuple:
    """Fetches GCP official incidents and returns (unstable_services_list, service_incidents_map)."""
    gcp_incidents_url = "https://status.cloud.google.com/incidents.json"
    active_incidents = []

    try:
        resp = requests.get(gcp_incidents_url, timeout=10)
        if resp.status_code == 200:
            all_incidents = resp.json()
            active_incidents = [inc for inc in all_incidents if not inc.get("end")]
        else:
            logger.warning(f"Unexpected status from GCP Status API: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to fetch GCP status feed: {e}")

    # Handle Simulation Mode
    if SIMULATION_MODE and SIMULATED_OUTAGE_SERVICES:
        for sim_svc in SIMULATED_OUTAGE_SERVICES:
            active_incidents.append({
                "id": f"SIMULATED-DR-{sim_svc.upper().replace(' ', '-')}",
                "service_name": sim_svc,
                "severity": "high",
                "status_impact": "SERVICE_OUTAGE",
                "external_desc": f"[SIMULATION] Artificial incident for {sim_svc} in {TARGET_REGION}.",
                "affected_products": [{"title": sim_svc}],
                "currently_affected_locations": [{"id": TARGET_REGION, "title": TARGET_REGION}],
                "end": None
            })

    unstable_services = []
    service_incidents_map = {}

    for service in TARGET_SERVICES:
        matched = [
            inc for inc in active_incidents
            if matches_service(service, inc) and matches_region(inc, TARGET_REGION)
        ]
        service_incidents_map[service] = matched
        if matched:
            unstable_services.append(service)

    return unstable_services, service_incidents_map

# ==============================================================================
# Main Execution Cycle
# ==============================================================================
def run_watchdog():
    logger.info(f"=== Starting GCP Status Watchdog (Region: {TARGET_REGION}) ===")
    state_mgr = GCSStateManager(GCS_STATE_BUCKET, GCS_STATE_FILE)
    state = state_mgr.load_state()

    current_topology = state.get("current_topology", "NORMAL")
    consecutive_failures = state.get("consecutive_failures", {})
    consecutive_healthy = state.get("consecutive_healthy", {})

    for svc in TARGET_SERVICES:
        consecutive_failures.setdefault(svc, 0)
        consecutive_healthy.setdefault(svc, CONSECUTIVE_HEALTHY_THRESHOLD)

    # 1. Primeira Verificação do Feed GCP
    unstable_services, service_incidents_map = fetch_and_evaluate_services()

    # --------------------------------------------------------------------------
    # Fast-Confirmation Loop: Se detectar falha em topologia NORMAL, executa
    # 2 re-verificações com intervalo de 30 segundos (reduzindo MTTD de 15m para 1m)
    # --------------------------------------------------------------------------
    if current_topology == "NORMAL" and unstable_services:
        logger.warning(f"⚠️ Instabilidade detectada na 1ª checagem para: {', '.join(unstable_services)}!")
        
        # Inicializa contadores para a rodada
        for svc in TARGET_SERVICES:
            if svc in unstable_services:
                consecutive_failures[svc] = 1
                consecutive_healthy[svc] = 0
            else:
                consecutive_healthy[svc] = 1
                consecutive_failures[svc] = 0

        if FAST_CONFIRMATION_ENABLED and CONSECUTIVE_OUTAGE_THRESHOLD > 1:
            logger.warning(f"⚡ [FAST-CONFIRMATION ATIVO] Executando {CONSECUTIVE_OUTAGE_THRESHOLD - 1} re-verificações a cada {FAST_CONFIRMATION_INTERVAL_SECONDS}s...")

            for check_idx in range(2, CONSECUTIVE_OUTAGE_THRESHOLD + 1):
                logger.info(f"[FAST-CONFIRMATION] Aguardando {FAST_CONFIRMATION_INTERVAL_SECONDS}s para re-verificação {check_idx}/{CONSECUTIVE_OUTAGE_THRESHOLD}...")
                time.sleep(FAST_CONFIRMATION_INTERVAL_SECONDS)

                re_unstable, re_incidents = fetch_and_evaluate_services()
                for svc in TARGET_SERVICES:
                    if svc in re_unstable:
                        consecutive_failures[svc] += 1
                        consecutive_healthy[svc] = 0
                        service_incidents_map[svc] = re_incidents[svc]
                        logger.warning(f"   [Check {check_idx}] ❌ {svc} confirmado com falha ativa ({consecutive_failures[svc]}/{CONSECUTIVE_OUTAGE_THRESHOLD})")
                    else:
                        consecutive_healthy[svc] += 1
                        consecutive_failures[svc] = 0
                        logger.info(f"   [Check {check_idx}] ✅ {svc} normalizou. Falso alarme descartado.")

    # --------------------------------------------------------------------------
    # Fast-Confirmation Loop para Switchback: Se estiver em Failover e os
    # serviços aparecerem saudáveis, confirma 3x com 30s de intervalo
    # --------------------------------------------------------------------------
    elif current_topology != "NORMAL" and not unstable_services:
        logger.info("✅ Serviços detectados como saudáveis na 1ª checagem pós-incidente!")

        for svc in TARGET_SERVICES:
            consecutive_healthy[svc] = 1
            consecutive_failures[svc] = 0

        if FAST_CONFIRMATION_ENABLED and CONSECUTIVE_HEALTHY_THRESHOLD > 1:
            logger.info(f"⚡ [FAST-CONFIRMATION ATIVO] Confirmando estabilidade em {CONSECUTIVE_HEALTHY_THRESHOLD - 1} re-verificações a cada {FAST_CONFIRMATION_INTERVAL_SECONDS}s...")

            for check_idx in range(2, CONSECUTIVE_HEALTHY_THRESHOLD + 1):
                logger.info(f"[FAST-CONFIRMATION] Aguardando {FAST_CONFIRMATION_INTERVAL_SECONDS}s para re-verificação de estabilidade {check_idx}/{CONSECUTIVE_HEALTHY_THRESHOLD}...")
                time.sleep(FAST_CONFIRMATION_INTERVAL_SECONDS)

                re_unstable, re_incidents = fetch_and_evaluate_services()
                for svc in TARGET_SERVICES:
                    if svc not in re_unstable:
                        consecutive_healthy[svc] += 1
                        consecutive_failures[svc] = 0
                        logger.info(f"   [Check {check_idx}] ✅ {svc} confirmado estável ({consecutive_healthy[svc]}/{CONSECUTIVE_HEALTHY_THRESHOLD})")
                    else:
                        consecutive_failures[svc] += 1
                        consecutive_healthy[svc] = 0
                        service_incidents_map[svc] = re_incidents[svc]
                        logger.warning(f"   [Check {check_idx}] ⚠️ {svc} oscilou! Abortando switchback por instabilidade.")

    # --------------------------------------------------------------------------
    # Em tempo de paz ou continuidade de estado
    # --------------------------------------------------------------------------
    else:
        for svc in TARGET_SERVICES:
            if svc in unstable_services:
                consecutive_failures[svc] += 1
                consecutive_healthy[svc] = 0
                logger.warning(f"⚠️ {svc} permanece UNHEALTHY ({consecutive_failures[svc]} checagens consecutivas)")
            else:
                consecutive_healthy[svc] += 1
                consecutive_failures[svc] = 0
                logger.info(f"✅ {svc} permanece HEALTHY ({consecutive_healthy[svc]} checagens consecutivas)")

    # --------------------------------------------------------------------------
    # Máquina de Estados & Motor de Decisão
    # --------------------------------------------------------------------------
    action_to_dispatch = None
    target_new_topology = current_topology
    decision_reason = ""

    sql_outage = consecutive_failures.get("Cloud SQL", 0) >= CONSECUTIVE_OUTAGE_THRESHOLD
    gke_outage = consecutive_failures.get("Google Kubernetes Engine", 0) >= CONSECUTIVE_OUTAGE_THRESHOLD

    sql_healthy = consecutive_healthy.get("Cloud SQL", 0) >= CONSECUTIVE_HEALTHY_THRESHOLD
    gke_healthy = consecutive_healthy.get("Google Kubernetes Engine", 0) >= CONSECUTIVE_HEALTHY_THRESHOLD

    # --- DECISÃO DE FAILOVER (Topologia NORMAL) ---
    if current_topology == "NORMAL":
        if sql_outage and gke_outage:
            action_to_dispatch = "full-regional-failover"
            target_new_topology = "FAILOVER_FULL"
            decision_reason = f"Blackout Regional confirmado em menos de 70 segundos! Tanto Cloud SQL quanto GKE falharam {CONSECUTIVE_OUTAGE_THRESHOLD} vezes consecutivas em {TARGET_REGION}."
        elif sql_outage:
            action_to_dispatch = "cross-region-sql-failover"
            target_new_topology = "FAILOVER_SQL"
            decision_reason = f"Falha Isolada de Cloud SQL confirmada em menos de 70 segundos ({CONSECUTIVE_OUTAGE_THRESHOLD} checagens a cada {FAST_CONFIRMATION_INTERVAL_SECONDS}s). GKE mantido em SP."
        elif gke_outage:
            action_to_dispatch = "gke-failover"
            target_new_topology = "FAILOVER_GKE"
            decision_reason = f"Falha Isolada de GKE confirmada em menos de 70 segundos ({CONSECUTIVE_OUTAGE_THRESHOLD} checagens a cada {FAST_CONFIRMATION_INTERVAL_SECONDS}s). Cloud SQL mantido em SP."

    # --- DECISÃO DE SWITCHBACK (Retorno de Failover Ativo) ---
    elif current_topology == "FAILOVER_SQL":
        if sql_healthy:
            action_to_dispatch = "switchback-sql"
            target_new_topology = "NORMAL"
            decision_reason = f"Cloud SQL em {TARGET_REGION} restabeleceu estabilidade confirmada em {CONSECUTIVE_HEALTHY_THRESHOLD} checagens consecutivas. Iniciando Switchback seguro com Zero Data Loss."
    elif current_topology == "FAILOVER_GKE":
        if gke_healthy:
            action_to_dispatch = "switchback-gke"
            target_new_topology = "NORMAL"
            decision_reason = f"GKE em {TARGET_REGION} restabeleceu estabilidade confirmada em {CONSECUTIVE_HEALTHY_THRESHOLD} checagens consecutivas. Iniciando Switchback e desligamento FinOps nos EUA."
    elif current_topology == "FAILOVER_FULL":
        if sql_healthy and gke_healthy:
            action_to_dispatch = "full-regional-switchback"
            target_new_topology = "NORMAL"
            decision_reason = f"Região {TARGET_REGION} totalmente recuperada! Ambos Cloud SQL e GKE saudáveis por {CONSECUTIVE_HEALTHY_THRESHOLD} checagens consecutivas. Retornando operação completa a SP."

    # --------------------------------------------------------------------------
    # Execução da Ação & Envio de Notificações
    # --------------------------------------------------------------------------
    if action_to_dispatch:
        logger.info(f"🔥 DECISÃO TOMADA: Ação '{action_to_dispatch}' selecionada. Motivo: {decision_reason}")
        
        severity = "CRITICAL" if "failover" in action_to_dispatch else "INFO"

        if AUTO_TRIGGER_DR and not REQUIRE_MANUAL_CONFIRMATION:
            logger.info("Auto-Trigger está ATIVO e validação manual está DESATIVADA. Disparando pipeline imediatamente...")
            success = trigger_github_dr_workflow(action=action_to_dispatch, dry_run=DRY_RUN_DISPATCH)
            
            status_text = "EXECUÇÃO DISPARADA AUTOMATICAMENTE" if success else "FALHA NO DISPARO AUTOMÁTICO"
            send_slack_notification(
                title=f"{status_text}: {action_to_dispatch}",
                message=f"{decision_reason}\n\n*Status da Pipeline:* Disparada com sucesso no GitHub Actions.",
                severity=severity,
                action=action_to_dispatch,
                dry_run=DRY_RUN_DISPATCH
            )
            if success:
                state["current_topology"] = target_new_topology
                state["last_action_dispatched"] = action_to_dispatch
                state["last_status_change_at"] = datetime.now(timezone.utc).isoformat()
        else:
            logger.info("Ação identificada, mas requer aprovação manual do operador ou confirmação de segurança.")
            send_slack_notification(
                title=f"AÇÃO REQUERIDA (Validação Manual): {action_to_dispatch}",
                message=f"{decision_reason}\n\n⚠️ *Aviso de Segurança:* O modo de disparo automático está com flag de validação manual ativa. Acesse o link abaixo para autorizar o Disaster Recovery.",
                severity=severity,
                action=action_to_dispatch,
                dry_run=DRY_RUN_DISPATCH
            )
            state["last_action_dispatched"] = f"PENDING_MANUAL_CONFIRMATION:{action_to_dispatch}"

    # --------------------------------------------------------------------------
    # Persistência do Estado no GCS
    # --------------------------------------------------------------------------
    state["consecutive_failures"] = consecutive_failures
    state["consecutive_healthy"] = consecutive_healthy
    state["active_incident_ids"] = [inc.get("id") for incs in service_incidents_map.values() for inc in incs]
    state_mgr.save_state(state)

    logger.info(f"=== Watchdog Cycle Complete: Topology={state.get('current_topology')} | Failures={consecutive_failures} | Healthy={consecutive_healthy} ===")

if __name__ == "__main__":
    run_watchdog()
