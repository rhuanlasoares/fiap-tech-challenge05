import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.ai_reasoner import AasReasoner
from core.config import settings
from core.k8s_client import K8sClient
from core.loki_client import LokiClient
from core.predictor import AiOpsPredictor
from core.prometheus_client import PrometheusClient
from core.remediator import AiOpsRemediator, send_slack_alert

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("aiops.main")

prom = PrometheusClient()
loki = LokiClient()
k8s = K8sClient()
predictor = AiOpsPredictor()
reasoner = AasReasoner()
remediator = AiOpsRemediator(k8s)

state_lock = threading.Lock()

state = {
    "current_score": 100,
    "predictions": [],
    "anomalies": [],
    "insights": [],
    "simulated_predictions": [],
    "simulated_anomalies": [],
    "simulated_insights": [],
    "log_errors": [],
    "warning_events": [],
    "nodes": [],
    "pvcs": [],
    "last_update": "",
}


def sync_analysis_cycle():
    global state
    logger.info("Executing AIOps Analysis Cycle...")
    namespaces = settings.TARGET_NAMESPACES

    try:
        mem_trends = prom.get_container_memory_trends(namespaces)
        golden_signals = prom.get_http_golden_signals(namespaces)
        pvcs_stat = prom.get_pvc_storage_forecast()
        nodes_stat = prom.get_node_health_summary()

        error_logs = loki.query_error_logs(namespaces, limit=20)
        events = k8s.get_cluster_warning_events(namespaces)

        mem_risks = predictor.analyze_memory_leaks(mem_trends)
        storage_risks = predictor.analyze_storage_risks(pvcs_stat)
        all_predictions = (
            mem_risks + storage_risks + state.get("simulated_predictions", [])
        )

        http_anomalies = predictor.analyze_http_anomalies(golden_signals)
        all_anomalies = http_anomalies + state.get("simulated_anomalies", [])

        score = predictor.calculate_cluster_health_score(
            all_predictions, all_anomalies, events
        )

        insights = []
        for item in mem_risks + storage_risks + http_anomalies:
            rca = reasoner.generate_rca(item, error_logs, events)
            if rca:
                rca["risk_id"] = item.get("id")
                rca["type"] = item.get("type")
                insights.append(rca)
                # Dispatch Slack alert for live detected incidents
                send_slack_alert(
                    title=item.get("type", "Cluster Incident"),
                    message=item.get("message", "Anomalia detectada no cluster."),
                    severity=item.get("severity", "WARNING"),
                    rca=rca,
                )

        all_insights = insights + state.get("simulated_insights", [])

        if settings.AUTO_HEALING_ENABLED:
            for risk in mem_risks:
                if (
                    risk.get("severity") == "CRITICAL"
                    and risk.get("estimated_minutes_to_failure", 999) < 15
                ):
                    logger.warning(
                        f"AUTO-HEALING: Automatically remediating {risk.get('id')}"
                    )
                    remediator.execute_preventive_action(risk)

        with state_lock:
            state["current_score"] = score
            state["predictions"] = all_predictions
            state["anomalies"] = all_anomalies
            state["insights"] = all_insights
            state["log_errors"] = error_logs[-15:]
            state["warning_events"] = events[-15:]
            state["nodes"] = nodes_stat
            state["pvcs"] = pvcs_stat
            state["last_update"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"AIOps cycle complete. Health Score: {score}/100, Risks: {len(all_predictions)}, Anomalies: {len(all_anomalies)}"
        )
    except Exception as e:
        logger.error(f"Error during AIOps analysis cycle: {e}")


async def run_analysis_cycle():
    await asyncio.to_thread(sync_analysis_cycle)


async def background_monitor():
    await asyncio.sleep(2)
    while True:
        try:
            await run_analysis_cycle()
        except Exception as e:
            logger.error(f"Background monitoring error: {e}")
        await asyncio.sleep(settings.ANALYSIS_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(background_monitor())
    yield
    task.cancel()


app = FastAPI(title="AIOps Predictive Engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "aiops-engine",
        "score": state["current_score"],
    }


@app.get("/api/status")
def get_status():
    return state


@app.get("/api/predictions")
def get_predictions():
    return state["predictions"]


@app.get("/api/anomalies")
def get_anomalies():
    return state["anomalies"]


@app.get("/api/insights")
def get_insights():
    return state["insights"]


@app.post("/api/analyze-now")
async def trigger_analysis():
    await run_analysis_cycle()
    return {"status": "completed", "score": state["current_score"]}


class SimulateRequest(BaseModel):
    scenario: str


@app.post("/api/simulate-anomaly")
def post_simulation(req: SimulateRequest):
    rca = None
    if req.scenario == "memory_leak":
        mock_risk = {
            "id": "oom_leak_donation_ns_donation-service-7f88d",
            "type": "MEMORY_LEAK_PREDICTION",
            "severity": "CRITICAL",
            "namespace": "donation-ns",
            "pod": "donation-service-7f88d",
            "container": "donation-service",
            "message": "Pod donation-service approaching OOMKilled! Current: 94.2% of limit, growing at 4.2 KB/s.",
            "current_usage_mb": 241.2,
            "limit_mb": 256.0,
            "estimated_minutes_to_failure": 14.5,
            "recommendation": "Schedule graceful rollout restart or expand memory limit to prevent OOMKilled.",
        }
        state["simulated_predictions"] = [mock_risk]
        state["simulated_anomalies"] = []
        state["predictions"] = [mock_risk]
        rca = reasoner.generate_rca(
            mock_risk, state["log_errors"], state["warning_events"]
        )
        if rca:
            rca["risk_id"] = mock_risk["id"]
            rca["type"] = mock_risk["type"]
        state["simulated_insights"] = [rca] if rca else []
        state["insights"] = [rca] if rca else []
        state["current_score"] = 85

        # Enviar alerta para o Slack
        send_slack_alert(
            title="Memory Leak Iminente (OOMKill Alert)",
            message=mock_risk["message"],
            severity="CRITICAL",
            rca=rca,
        )

    elif req.scenario == "5xx_surge":
        mock_anom = {
            "id": "err_spike_donation_ns_donation-service",
            "type": "HTTP_5XX_ERROR_RATE_ANOMALY",
            "severity": "CRITICAL",
            "namespace": "donation-ns",
            "service": "donation-service",
            "message": "Service donation-service has an anomalous error rate of 18.4% (24.2 errors/sec).",
            "current_value": 18.4,
            "unit": "%",
            "recommendation": "Inspect Cloud SQL authentication and SQS delivery status.",
        }
        state["simulated_anomalies"] = [mock_anom]
        state["simulated_predictions"] = []
        state["anomalies"] = [mock_anom]
        rca = reasoner.generate_rca(
            mock_anom, state["log_errors"], state["warning_events"]
        )
        if rca:
            rca["risk_id"] = mock_anom["id"]
            rca["type"] = mock_anom["type"]
        state["simulated_insights"] = [rca] if rca else []
        state["insights"] = [rca] if rca else []
        state["current_score"] = 80

        # Enviar alerta para o Slack
        send_slack_alert(
            title="Surto de Erros HTTP 5xx Detectado",
            message=mock_anom["message"],
            severity="CRITICAL",
            rca=rca,
        )

    return {
        "status": "simulated_success",
        "score": state["current_score"],
        "insight": rca,
        "slack_notified": bool(settings.SLACK_WEBHOOK_URL),
    }


@app.post("/api/send-test-slack")
def send_test_slack():
    mock_risk = {
        "id": "test_alert_solidary_tech",
        "type": "SIMULATED_TEST_ALERT",
        "severity": "WARNING",
        "namespace": "donation-ns",
        "pod": "donation-service-manual-test",
        "message": "Teste manual de integridade do webhook de notificações SRE do AIOps Engine.",
    }
    rca = {
        "probable_root_cause": "Validação de conectividade e alertas proativos do canal SRE.",
        "recommended_action": "Nenhuma ação corretiva necessária. Canal de alertas 100% operacional.",
    }
    success = send_slack_alert(
        title="🔔 Teste de Conectividade do AIOps",
        message=mock_risk["message"],
        severity="WARNING",
        rca=rca,
    )
    return {
        "slack_delivered": success,
        "webhook_configured": bool(settings.SLACK_WEBHOOK_URL),
    }


@app.post("/api/remediate/{risk_id}")
def remediate_risk(risk_id: str):
    for r in state["predictions"] + state["anomalies"]:
        if r.get("id") == risk_id:
            res = remediator.execute_preventive_action(r)
            state["predictions"] = [
                p for p in state["predictions"] if p.get("id") != risk_id
            ]
            state["anomalies"] = [
                a for a in state["anomalies"] if a.get("id") != risk_id
            ]
            state["simulated_predictions"] = [
                p
                for p in state.get("simulated_predictions", [])
                if p.get("id") != risk_id
            ]
            state["simulated_anomalies"] = [
                a
                for a in state.get("simulated_anomalies", [])
                if a.get("id") != risk_id
            ]
            state["simulated_insights"] = [
                i
                for i in state.get("simulated_insights", [])
                if i.get("risk_id") != risk_id
            ]
            state["insights"] = [
                i for i in state["insights"] if i.get("risk_id") != risk_id
            ]
            state["current_score"] = min(100, state["current_score"] + 15)
            return {"status": "remediated", "details": res}
    raise HTTPException(status_code=404, detail="Risk ID not found")


static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
