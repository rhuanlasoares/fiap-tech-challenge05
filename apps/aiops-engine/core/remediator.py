import logging
import threading
import time
from typing import Any, Dict, Optional

import requests

from core.config import settings
from core.k8s_client import K8sClient

logger = logging.getLogger("aiops.remediator")

_last_alert_timestamps: Dict[str, float] = {}
_alert_lock = threading.Lock()


def send_slack_alert(
    title: str,
    message: str,
    severity: str = "CRITICAL",
    rca: Optional[Dict[str, Any]] = None,
    alert_key: Optional[str] = None,
    force: bool = False,
) -> bool:
    if not settings.SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not configured.")
        return False

    # Janela de cooldown para evitar spam repetido no Slack
    key = alert_key or f"{title}:{rca.get('affected_service') if rca else ''}:{severity}"
    now = time.time()
    cooldown = settings.SLACK_ALERT_COOLDOWN_SECONDS

    if not force and cooldown > 0:
        with _alert_lock:
            last_sent = _last_alert_timestamps.get(key, 0.0)
            elapsed = now - last_sent
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                logger.info(
                    f"Slack alert suprimido para '{key}' devido à janela de cooldown ({remaining}s restantes)."
                )
                return False
            _last_alert_timestamps[key] = now
            if len(_last_alert_timestamps) > 100:
                _last_alert_timestamps.clear()
                _last_alert_timestamps[key] = now
    elif force:
        with _alert_lock:
            _last_alert_timestamps[key] = now

    emoji = "🚨" if severity == "CRITICAL" else "⚠️" if severity == "WARNING" else "ℹ️"

    text = f"{emoji} *[AIOps Engine]* {title}\n>{message}"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} AIOps Incident Alert: {title}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severidade:*\n`{severity}`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Cluster / Engine:*\n`gke-samerica / AIOps`",
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Descrição do Evento:*\n{message}"},
        },
    ]

    if rca:
        if rca.get("probable_root_cause"):
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🧠 Diagnóstico de Causa Raiz (Google Gemini AI):*\n{rca.get('probable_root_cause')}",
                    },
                }
            )
        if rca.get("recommended_action"):
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🛠️ Ação Recomendada:*\n```{rca.get('recommended_action')}```",
                    },
                }
            )

    payload = {"text": text, "blocks": blocks}

    try:
        resp = requests.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5)
        logger.info(f"Slack notification sent for '{key}' (Status: {resp.status_code})")
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to deliver Slack webhook alert: {e}")
        return False


class AiOpsRemediator:
    def __init__(self, k8s_client: K8sClient):
        self.k8s = k8s_client
        self.auto_healing_enabled = settings.AUTO_HEALING_ENABLED

    def execute_preventive_action(self, risk_details: Dict[str, Any]) -> Dict[str, Any]:
        risk_type = risk_details.get("type")
        namespace = risk_details.get("namespace", "default")
        pod = risk_details.get("pod") or ""

        deployment_name = pod
        if "-" in pod:
            parts = pod.split("-")
            if len(parts) >= 3:
                deployment_name = "-".join(parts[:-2])
            elif len(parts) >= 2:
                deployment_name = parts[0]

        if risk_type == "MEMORY_LEAK_PREDICTION":
            logger.info(
                f"Initiating preventive rollout restart for deployment {deployment_name} in {namespace}"
            )
            success = self.k8s.rollout_restart_deployment(namespace, deployment_name)

            send_slack_alert(
                title=f"Auto-Healing Executado: {deployment_name}",
                message=f"Vazamento de memória detectado em `{namespace}/{pod}`. Rollout restart disparado com sucesso para evitar OOMKilled.",
                severity="INFO",
                force=True,
            )

            return {
                "success": success,
                "action": "ROLLOUT_RESTART",
                "target": f"{namespace}/{deployment_name}",
                "message": (
                    "Graceful rollout restart triggered successfully before OOM occurred."
                    if success
                    else "Rollout restart commanded."
                ),
            }

        return {
            "success": False,
            "action": "NONE",
            "message": "No automated remediation handler defined for this risk type.",
        }

def send_slack_post_mortem(
    post_mortem: Dict[str, Any],
    force: bool = True,
) -> bool:
    """Envia o card oficial de Post-Mortem gerado com Slack Block Kit."""
    if not settings.SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not configured for Post-Mortem.")
        return False

    title = post_mortem.get("title", "Relatório Oficial de Post-Mortem SRE")
    status = post_mortem.get("status", "RESOLVED")
    mttr = post_mortem.get("mttr_formatted") or f"{post_mortem.get("mttr_minutes", 0)} min"
    score = post_mortem.get("final_score", 100)
    summary = post_mortem.get("executive_summary", "")
    rca = post_mortem.get("root_cause_analysis", "")
    rem = post_mortem.get("remediation_details", "")
    action_items = post_mortem.get("action_items", [])

    text = f"📋 *[AIOps SRE Post-Mortem]* {title}\n>Status: {status} | MTTR: {mttr} | Health Score: {score}/100"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 SRE Incident Post-Mortem: {status}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status do Incidente:*\n`✅ {status}`"},
                {"type": "mrkdwn", "text": f"*Duração (MTTR):*\n`⏱️ {mttr}`"},
                {"type": "mrkdwn", "text": f"*Health Score Final:*\n`🎯 {score}/100`"},
                {"type": "mrkdwn", "text": "*Cluster / Engine:*\n`gke-samerica / AIOps`"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📋 Resumo Executivo:*\n{summary}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🔍 Causa Raiz Técnica (Google Gemini GenAI):*\n{rca}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🛠️ Remediação que Estabilizou o Cluster:*\n```{rem}```"},
        },
    ]

    if action_items:
        items_str = "\n".join([f"• {item}" if not item.startswith("•") and not item[0].isdigit() else item for item in action_items])
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🛡️ Ações Preventivas (Action Items):*\n{items_str}"},
            }
        )

    payload = {"text": text, "blocks": blocks}

    try:
        resp = requests.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5)
        logger.info(f"Slack Post-Mortem notification sent (Status: {resp.status_code})")
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Failed to deliver Slack Post-Mortem: {e}")
        return False
