import asyncio
import logging
import os
import threading
import time
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
from core.loki_client import LokiClient, LokiLoggingHandler
from core.predictor import AiOpsPredictor
from core.prometheus_client import PrometheusClient
from core.remediator import (AiOpsRemediator, send_slack_alert,
                             send_slack_post_mortem)

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

# Conecta handler do Loki para encaminhamento autom?tico de logs ao Grafana
loki_handler = LokiLoggingHandler(loki)
loki_handler.setLevel(logging.INFO)
loki_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger.addHandler(loki_handler)

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
    "active_incident": None,
    "post_mortems": [],
    "integrations": {},
}


def check_all_telemetry_connectivity() -> Dict[str, Any]:
    """Auditoria e teste de conectividade de todos os subsistemas de telemetria."""
    loki_res = loki.check_connectivity(settings.TARGET_NAMESPACES)
    prom_res = prom.check_connectivity()
    k8s_res = k8s.check_connectivity()
    gemini_res = reasoner.check_connectivity()
    slack_configured = bool(settings.SLACK_WEBHOOK_URL)

    # Telemetria ? considerada operacional se ao menos um dos backends responder ou se estiver em modo simulado
    overall_ready = (
        loki_res["status"] == "healthy"
        or prom_res["status"] == "healthy"
        or k8s_res["status"] == "healthy"
    )

    return {
        "overall_status": "healthy" if overall_ready else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "loki": loki_res,
        "prometheus": prom_res,
        "kubernetes": k8s_res,
        "gemini": gemini_res,
        "slack": {
            "configured": slack_configured,
            "status": "healthy" if slack_configured else "not_configured",
            "message": (
                "Slack webhook URL configurada e pronta para alertas."
                if slack_configured
                else "SLACK_WEBHOOK_URL não configurada."
            ),
        },
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

        # Emissão de logs estruturados e alertas
        if mem_risks:
            for risk in mem_risks:
                pod = risk.get("pod", "unknown")
                ns = risk.get("namespace", "unknown")
                sev = risk.get("severity", "WARNING")
                msg = risk.get("message", "")
                mins = risk.get("estimated_minutes_to_failure", 0)
                log_line = (
                    f"[AIOPS-ALERT] [MEMORY_LEAK] Pod: {pod} | Namespace: {ns} | "
                    f"Severidade: {sev} | {msg} | Tempo estimado: {mins}min"
                )
                print(log_line)
                logger.warning(log_line)
                loki.push_log(
                    message=log_line,
                    level="ERROR" if sev == "CRITICAL" else "WARN",
                    extra_labels={
                        "alert_type": "MEMORY_LEAK",
                        "severity": sev,
                        "target_pod": pod,
                        "target_namespace": ns,
                    },
                )

        if storage_risks:
            for risk in storage_risks:
                pvc = risk.get("pvc", "unknown")
                ns = risk.get("namespace", "unknown")
                sev = risk.get("severity", "WARNING")
                msg = risk.get("message", "")
                log_line = (
                    f"[AIOPS-ALERT] [STORAGE_RISK] PVC: {pvc} | Namespace: {ns} | "
                    f"Severidade: {sev} | {msg}"
                )
                print(log_line)
                logger.warning(log_line)
                loki.push_log(
                    message=log_line,
                    level="ERROR" if sev == "CRITICAL" else "WARN",
                    extra_labels={
                        "alert_type": "STORAGE_RISK",
                        "severity": sev,
                        "target_pvc": pvc,
                        "target_namespace": ns,
                    },
                )

        if http_anomalies:
            for anom in http_anomalies:
                svc = anom.get("service", "unknown")
                ns = anom.get("namespace", "unknown")
                sev = anom.get("severity", "WARNING")
                msg = anom.get("message", "")
                log_line = (
                    f"[AIOPS-ALERT] [HTTP_ANOMALY] Serviço: {svc} | Namespace: {ns} | "
                    f"Severidade: {sev} | {msg}"
                )
                print(log_line)
                logger.warning(log_line)
                loki.push_log(
                    message=log_line,
                    level="ERROR" if sev == "CRITICAL" else "WARN",
                    extra_labels={
                        "alert_type": "HTTP_ANOMALY",
                        "severity": sev,
                        "target_service": svc,
                        "target_namespace": ns,
                    },
                )

        insights = []
        for item in mem_risks + storage_risks + http_anomalies:
            rca = reasoner.generate_rca(item, error_logs, events)
            if rca:
                rca["risk_id"] = item.get("id")
                rca["type"] = item.get("type")
                insights.append(rca)

                rca_log = (
                    f"[AIOPS-RCA] Incidente: {rca.get('title')} | "
                    f"Causa Raiz: {rca.get('probable_root_cause')} | "
                    f"Ação Recomendada: {rca.get('recommended_action')}"
                )
                print(rca_log)
                logger.info(rca_log)
                loki.push_log(
                    message=rca_log,
                    level="INFO",
                    extra_labels={
                        "alert_type": "RCA_DIAGNOSTIC",
                        "severity": item.get("severity", "WARNING"),
                    },
                )

                alert_key = (
                    item.get("id")
                    or f"{item.get('type')}:{item.get('pod') or item.get('service') or item.get('pvc')}"
                )
                send_slack_alert(
                    title=item.get("type", "Cluster Incident"),
                    message=item.get("message", "Anomalia detectada no cluster."),
                    severity=item.get("severity", "WARNING"),
                    rca=rca,
                    alert_key=alert_key,
                )

        all_insights = insights + state.get("simulated_insights", [])

        # Auto-Healing
        executed_remediations = []
        if settings.AUTO_HEALING_ENABLED:
            for risk in mem_risks:
                if (
                    risk.get("severity") == "CRITICAL"
                    and risk.get("estimated_minutes_to_failure", 999) < 15
                ):
                    heal_log = f"AUTO-HEALING: Executando remediação preventiva para {risk.get('id')}"
                    print(heal_log)
                    logger.warning(heal_log)
                    loki.push_log(
                        message=heal_log,
                        level="WARN",
                        extra_labels={"alert_type": "AUTO_HEALING"},
                    )
                    rem_res = remediator.execute_preventive_action(risk)
                    executed_remediations.append(rem_res)

        # MÁQUINA DE ESTADOS DO INCIDENTE & GERAÇÃO DE POST-MORTEM
        with state_lock:
            # 1. Se score < 90 ou há anomalias/riscos: abre ou atualiza contexto do incidente ativo
            if score < 90 or all_predictions or all_anomalies:
                if state["active_incident"] is None:
                    state["active_incident"] = {
                        "id": f"inc-{int(time.time())}",
                        "started_at": datetime.now(timezone.utc).isoformat(),
                        "start_timestamp": time.time(),
                        "initial_score": score,
                        "lowest_score": score,
                        "predictions": list(all_predictions),
                        "anomalies": list(all_anomalies),
                        "insights": list(all_insights),
                        "remediations": list(executed_remediations),
                        "error_logs_sample": [l.get("log") for l in error_logs[:5]],
                    }
                    logger.info(
                        f"🚨 Incidente operacional aberto em memória: {state['active_incident']['id']} (Score: {score})"
                    )
                else:
                    state["active_incident"]["lowest_score"] = min(
                        state["active_incident"]["lowest_score"], score
                    )
                    state["active_incident"]["predictions"] = list(all_predictions)
                    state["active_incident"]["anomalies"] = list(all_anomalies)
                    state["active_incident"]["insights"] = list(all_insights)
                    if executed_remediations:
                        state["active_incident"]["remediations"].extend(
                            executed_remediations
                        )

            # 2. Se score recuperou para >= 95 E havia um incidente ativo: CLUSTER ESTABILIZADO!
            elif score >= 95 and state["active_incident"] is not None:
                inc = state["active_incident"]
                inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
                duration = round(
                    time.time() - inc.get("start_timestamp", time.time()), 1
                )
                inc["duration_seconds"] = duration
                inc["final_score"] = score

                logger.info(
                    f"✅ Cluster estabilizado com Health Score {score}/100! "
                    f"Sintetizando Post-Mortem via Google Gemini (MTTR: {duration}s)..."
                )

                pm = reasoner.generate_post_mortem(inc)
                send_slack_post_mortem(pm)

                state["post_mortems"].insert(0, pm)
                if len(state["post_mortems"]) > 20:
                    state["post_mortems"].pop()

                post_mortem_log = (
                    f"[AIOPS-POST-MORTEM] Incidente {inc['id']} resolvido com sucesso! "
                    f"MTTR: {pm.get('mttr_formatted')} | Score: {score}/100"
                )
                print(post_mortem_log)
                logger.info(post_mortem_log)
                loki.push_log(
                    message=post_mortem_log,
                    level="INFO",
                    extra_labels={"alert_type": "POST_MORTEM", "mttr": str(duration)},
                )

                state["active_incident"] = None

            state["current_score"] = score
            state["predictions"] = all_predictions
            state["anomalies"] = all_anomalies
            state["insights"] = all_insights
            state["log_errors"] = error_logs[-15:]
            state["warning_events"] = events[-15:]
            state["nodes"] = nodes_stat
            state["pvcs"] = pvcs_stat
            state["last_update"] = datetime.now(timezone.utc).isoformat()

        status_log = (
            f"AIOps cycle complete. Health Score: {score}/100, "
            f"Risks: {len(all_predictions)}, Anomalies: {len(all_anomalies)}"
        )
        print(status_log)
        logger.info(status_log)
        loki.push_log(
            message=status_log,
            level="INFO",
            extra_labels={"alert_type": "CYCLE_SUMMARY", "health_score": str(score)},
        )
    except Exception as e:
        err_msg = f"Error during AIOps analysis cycle: {e}"
        print(err_msg)
        logger.error(err_msg)
        loki.push_log(
            message=err_msg,
            level="ERROR",
            extra_labels={"alert_type": "ENGINE_ERROR"},
        )


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
    # Pre-Flight Self-Check no startup do container
    logger.info("Executando Pre-Flight Connectivity Check do AIOps Engine...")
    print("=" * 72)
    print("🔍 [AIOPS-STARTUP] EXECUTANDO PRE-FLIGHT CHECK DE CONECTIVIDADE SRE")
    print("=" * 72)
    diag = check_all_telemetry_connectivity()
    state["integrations"] = diag

    print(
        f"  ✅ Grafana Loki:       [{diag['loki']['status'].upper()}] - {diag['loki']['message']}"
    )
    print(
        f"  ✅ Prometheus:         [{diag['prometheus']['status'].upper()}] - {diag['prometheus']['message']}"
    )
    print(
        f"  ✅ Kubernetes API:     [{diag['kubernetes']['status'].upper()}] - {diag['kubernetes']['message']}"
    )
    print(
        f"  ✅ Google Gemini GenAI:[{diag['gemini']['status'].upper()}] - {diag['gemini']['message']}"
    )
    print(
        f"  ✅ Slack Alerts:       [{diag['slack']['status'].upper()}] - {diag['slack']['message']}"
    )
    print("=" * 72)

    task = asyncio.create_task(background_monitor())
    yield
    task.cancel()


app = FastAPI(title="AIOps Predictive Engine", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/live")
def liveness_check():
    """Liveness probe do Kubernetes: rápido, valida apenas se o processo Python está vivo."""
    return {
        "status": "alive",
        "service": "aiops-engine",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def readiness_check():
    """Readiness probe do Kubernetes: valida se as dependências essenciais de telemetria respondem."""
    diag = check_all_telemetry_connectivity()
    state["integrations"] = diag

    # Em ambiente de produção, se nenhuma dependência responder, responde 503
    if diag["overall_status"] != "healthy":
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "message": "Dependências vitais de telemetria inacessíveis.",
                "diagnostics": diag,
            },
        )
    return {
        "status": "ready",
        "service": "aiops-engine",
        "score": state["current_score"],
        "diagnostics": diag,
    }


@app.get("/health")
def health_check():
    """Health check padrão mantido para compatibilidade com o GKE Application Load Balancer."""
    return {
        "status": "healthy",
        "service": "aiops-engine",
        "score": state["current_score"],
    }


@app.get("/pre-stop")
def pre_stop():
    logger.info("Kubernetes preStop hook recebido. Drenando conexoes por 5s...")
    time.sleep(5)
    return {"status": "drained", "service": "aiops-engine"}


@app.get("/api/status")
def get_status():
    return state


@app.get("/api/connectivity-test")
def get_connectivity_test():
    """Auditoria e teste de conectividade manual de todos os subsistemas de telemetria."""
    diag = check_all_telemetry_connectivity()
    state["integrations"] = diag
    return diag


@app.get("/api/post-mortems")
def get_post_mortems():
    """Retorna o histórico de relatórios formais de Post-Mortem SRE gerados."""
    return state.get("post_mortems", [])


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
    is_pt = settings.AIOPS_LANGUAGE.lower().startswith("pt")

    if req.scenario == "memory_leak":
        msg = (
            "Pod donation-service-7f88d se aproximando de OOMKilled! Uso atual: 94.2% do limite, crescendo a 4.2 KB/s."
            if is_pt
            else "Pod donation-service approaching OOMKilled! Current: 94.2% of limit, growing at 4.2 KB/s."
        )
        rec = (
            "Agendar rollout restart gracioso ou expandir limite de memória para prevenir OOMKilled."
            if is_pt
            else "Schedule graceful rollout restart or expand memory limit to prevent OOMKilled."
        )
        mock_risk = {
            "id": "oom_leak_donation_ns_donation-service-7f88d",
            "type": "MEMORY_LEAK_PREDICTION",
            "severity": "CRITICAL",
            "namespace": "donation-ns",
            "pod": "donation-service-7f88d",
            "container": "donation-service",
            "message": msg,
            "current_usage_mb": 241.2,
            "limit_mb": 256.0,
            "estimated_minutes_to_failure": 14.5,
            "recommendation": rec,
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

        # Abre incidente ativo na máquina de estados
        state["active_incident"] = {
            "id": f"sim-inc-oom-{int(time.time())}",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "start_timestamp": time.time(),
            "initial_score": 85,
            "lowest_score": 85,
            "predictions": [mock_risk],
            "anomalies": [],
            "insights": [rca] if rca else [],
            "remediations": [],
            "error_logs_sample": [mock_risk["message"]],
        }

        sim_log = f"[AIOPS-SIMULATION] [MEMORY_LEAK] {mock_risk['message']}"
        print(sim_log)
        logger.warning(sim_log)
        loki.push_log(
            message=sim_log,
            level="ERROR",
            extra_labels={"alert_type": "SIMULATION", "scenario": "memory_leak"},
        )

        send_slack_alert(
            title="Memory Leak Iminente (OOMKill Alert)",
            message=mock_risk["message"],
            severity="CRITICAL",
            rca=rca,
            force=True,
        )

    elif req.scenario == "5xx_surge":
        msg = (
            "Serviço donation-service com taxa anômala de erros HTTP de 18.4% (24.2 erros/seg)."
            if is_pt
            else "Service donation-service has an anomalous error rate of 18.4% (24.2 errors/sec)."
        )
        rec = (
            "Inspecionar autenticação do Cloud SQL e status de entrega na fila SQS."
            if is_pt
            else "Inspect Cloud SQL authentication and SQS delivery status."
        )
        mock_anom = {
            "id": "err_spike_donation_ns_donation-service",
            "type": "HTTP_5XX_ERROR_RATE_ANOMALY",
            "severity": "CRITICAL",
            "namespace": "donation-ns",
            "service": "donation-service",
            "message": msg,
            "current_value": 18.4,
            "unit": "%",
            "recommendation": rec,
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

        # Abre incidente ativo na máquina de estados
        state["active_incident"] = {
            "id": f"sim-inc-5xx-{int(time.time())}",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "start_timestamp": time.time(),
            "initial_score": 80,
            "lowest_score": 80,
            "predictions": [],
            "anomalies": [mock_anom],
            "insights": [rca] if rca else [],
            "remediations": [],
            "error_logs_sample": [mock_anom["message"]],
        }

        sim_log = f"[AIOPS-SIMULATION] [5XX_SURGE] {mock_anom['message']}"
        print(sim_log)
        logger.warning(sim_log)
        loki.push_log(
            message=sim_log,
            level="ERROR",
            extra_labels={"alert_type": "SIMULATION", "scenario": "5xx_surge"},
        )

        send_slack_alert(
            title="Surto de Erros HTTP 5xx Detectado",
            message=mock_anom["message"],
            severity="CRITICAL",
            rca=rca,
            force=True,
        )

    return {
        "status": "simulated_success",
        "score": state["current_score"],
        "insight": rca,
        "slack_notified": bool(settings.SLACK_WEBHOOK_URL),
    }


@app.post("/api/send-test-slack")
def send_test_slack():
    is_pt = settings.AIOPS_LANGUAGE.lower().startswith("pt")
    mock_risk = {
        "id": "test_alert_solidary_tech",
        "type": "SIMULATED_TEST_ALERT",
        "severity": "WARNING",
        "namespace": "donation-ns",
        "pod": "donation-service-manual-test",
        "message": (
            "Teste manual de integridade do webhook de notificações SRE do AIOps Engine."
            if is_pt
            else "Manual SRE notification webhook health check from AIOps Engine."
        ),
    }
    rca = {
        "probable_root_cause": (
            "Validação de conectividade e alertas proativos do canal SRE."
            if is_pt
            else "Validation of SRE channel connectivity and proactive alerts."
        ),
        "recommended_action": (
            "Nenhuma ação corretiva necessária. Canal de alertas 100% operacional."
            if is_pt
            else "No remediation needed. Alerting channel is 100% operational."
        ),
    }
    success = send_slack_alert(
        title="🛰️ Teste de Conectividade do AIOps",
        message=mock_risk["message"],
        severity="WARNING",
        rca=rca,
        force=True,
    )
    test_log = "[AIOPS-TEST] Teste de conectividade do webhook do Slack executado."
    print(test_log)
    logger.info(test_log)
    loki.push_log(
        message=test_log,
        level="INFO",
        extra_labels={"alert_type": "MANUAL_TEST"},
    )
    return {
        "slack_delivered": success,
        "webhook_configured": bool(settings.SLACK_WEBHOOK_URL),
    }


@app.post("/api/remediate/{risk_id}")
def remediate_risk(risk_id: str):
    matched_risk = None
    for r in state["predictions"] + state["anomalies"]:
        if r.get("id") == risk_id:
            matched_risk = r
            break

    if matched_risk:
        res = remediator.execute_preventive_action(matched_risk)

        # Atualiza lista de riscos
        state["predictions"] = [
            p for p in state["predictions"] if p.get("id") != risk_id
        ]
        state["anomalies"] = [a for a in state["anomalies"] if a.get("id") != risk_id]
        state["simulated_predictions"] = [
            p for p in state.get("simulated_predictions", []) if p.get("id") != risk_id
        ]
        state["simulated_anomalies"] = [
            a for a in state.get("simulated_anomalies", []) if a.get("id") != risk_id
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

        # Grava remediação no incidente ativo
        if state["active_incident"] is not None:
            state["active_incident"]["remediations"].append(res)

        # Se atingiu >= 95, normalizou! Gera o Post-Mortem imediatamente!
        post_mortem_generated = None
        if state["current_score"] >= 95 and state["active_incident"] is not None:
            inc = state["active_incident"]
            inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
            duration = round(time.time() - inc.get("start_timestamp", time.time()), 1)
            inc["duration_seconds"] = duration
            inc["final_score"] = state["current_score"]

            logger.info(
                f"Cluster normalizado após remediação manual! Gerando Post-Mortem SRE..."
            )
            post_mortem_generated = reasoner.generate_post_mortem(inc)
            send_slack_post_mortem(post_mortem_generated)

            state["post_mortems"].insert(0, post_mortem_generated)
            if len(state["post_mortems"]) > 20:
                state["post_mortems"].pop()

            state["active_incident"] = None

        return {
            "status": "remediated",
            "score": state["current_score"],
            "details": res,
            "post_mortem": post_mortem_generated,
        }

    raise HTTPException(status_code=404, detail="Risk ID not found")


static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    