import logging
import requests
from typing import Dict, Any, Optional
from core.config import settings
from core.k8s_client import K8sClient

logger = logging.getLogger("aiops.remediator")

def send_slack_alert(title: str, message: str, severity: str = "CRITICAL", rca: Optional[Dict[str, Any]] = None) -> bool:
    if not settings.SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not configured.")
        return False

    emoji = "🚨" if severity == "CRITICAL" else "⚠️" if severity == "WARNING" else "ℹ️"
    
    text = f"{emoji} *[AIOps Engine]* {title}\n>{message}"
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} AIOps Incident Alert: {title}"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severidade:*\n`{severity}`"},
                {"type": "mrkdwn", "text": f"*Cluster / Engine:*\n`gke-samerica / AIOps`"}
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Descrição do Evento:*\n{message}"
            }
        }
    ]
    
    if rca:
        if rca.get("probable_root_cause"):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🧠 Diagnóstico de Causa Raiz (Google Gemini AI):*\n{rca.get('probable_root_cause')}"
                }
            })
        if rca.get("recommended_action"):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🛠️ Ação Recomendada:*\n```{rca.get('recommended_action')}```"
                }
            })

    payload = {
        "text": text,
        "blocks": blocks
    }
    
    try:
        resp = requests.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5)
        logger.info(f"Slack notification sent (Status: {resp.status_code})")
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
            logger.info(f"Initiating preventive rollout restart for deployment {deployment_name} in {namespace}")
            success = self.k8s.rollout_restart_deployment(namespace, deployment_name)
            
            send_slack_alert(
                title=f"Auto-Healing Executado: {deployment_name}",
                message=f"Vazamento de memória detectado em `{namespace}/{pod}`. Rollout restart disparado com sucesso para evitar OOMKilled.",
                severity="INFO"
            )
            
            return {
                "success": success,
                "action": "ROLLOUT_RESTART",
                "target": f"{namespace}/{deployment_name}",
                "message": "Graceful rollout restart triggered successfully before OOM occurred." if success else "Rollout restart commanded."
            }

        return {
            "success": False,
            "action": "NONE",
            "message": "No automated remediation handler defined for this risk type."
        }