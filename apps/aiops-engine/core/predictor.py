import logging
from typing import Any, Dict, List

import numpy as np

from core.config import settings

logger = logging.getLogger("aiops.predictor")


class AiOpsPredictor:
    def __init__(self):
        pass

    def analyze_memory_leaks(
        self, mem_metrics: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        risks = []
        is_pt = settings.AIOPS_LANGUAGE.lower().startswith("pt")
        for item in mem_metrics:
            values = item.get("values", [])
            limit_bytes = float(item.get("limit_bytes", 0.0))
            if limit_bytes == 0 and "limit_mb" in item:
                limit_bytes = float(item.get("limit_mb")) * 1024 * 1024

            current_bytes = float(item.get("current_bytes", 0.0))
            if current_bytes == 0 and "current_usage_mb" in item:
                current_bytes = float(item.get("current_usage_mb")) * 1024 * 1024

            slope_given = item.get("slope_bytes_sec")
            slope = 0.0
            if slope_given is not None:
                slope = float(slope_given)
            elif len(values) >= 5 and limit_bytes > 0:
                tss = np.array([float(t[0]) for t in values])
                vals = np.array([float(t[1]) for t in values])
                tss_norm = tss - tss[0]
                if tss_norm[-1] >= 30:
                    slope, _intercept = np.polyfit(tss_norm, vals, 1)

            if slope > 1024 and limit_bytes > 0:
                remaining_bytes = max(1.0, limit_bytes - current_bytes)
                seconds_to_oom = remaining_bytes / slope
                minutes_to_oom = round(seconds_to_oom / 60.0, 1)
                current_pct = round((current_bytes / limit_bytes) * 100, 1)

                if minutes_to_oom < 120:
                    severity = "CRITICAL" if minutes_to_oom < 30 else "WARNING"
                    if is_pt:
                        msg = (
                            f"Pod {item.get('pod')} se aproximando de OOMKilled! "
                            f"Uso atual: {current_pct}% do limite, crescendo a {round(slope / 1024, 1)} KB/s."
                        )
                        rec = "Agendar rollout restart gracioso ou aumentar limite de memória para prevenir OOMKilled."
                    else:
                        msg = (
                            f"Pod {item.get('pod')} approaching OOMKilled! "
                            f"Current: {current_pct}% of limit, growing at {round(slope / 1024, 1)} KB/s."
                        )
                        rec = "Schedule graceful rollout restart or expand memory limit to prevent OOMKilled."

                    risks.append(
                        {
                            "id": f"oom_leak_{item.get('namespace')}_{item.get('pod')}",
                            "type": "MEMORY_LEAK_PREDICTION",
                            "severity": severity,
                            "namespace": item.get("namespace"),
                            "pod": item.get("pod"),
                            "container": item.get("container"),
                            "message": msg,
                            "current_usage_mb": round(current_bytes / (1024 * 1024), 1),
                            "limit_mb": round(limit_bytes / (1024 * 1024), 1),
                            "estimated_minutes_to_failure": minutes_to_oom,
                            "recommendation": rec,
                        }
                    )
        return risks

    def analyze_http_anomalies(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        anomalies = []
        is_pt = settings.AIOPS_LANGUAGE.lower().startswith("pt")
        for sig in signals:
            svc = sig.get("service")
            ns = sig.get("namespace")
            err_pct = float(sig.get("error_rate_pct", 0.0))
            p99_ms = float(sig.get("p99_latency_ms", 0.0))

            if err_pct > 5.0:
                if is_pt:
                    msg = f"Serviço {svc} com taxa anômala de erros HTTP de {err_pct}%."
                    rec = "Verificar conectividade com banco de dados e logs de erro do pod para exceções."
                else:
                    msg = f"Service {svc} has an anomalous error rate of {err_pct}%."
                    rec = "Check database connectivity and pod logs for unhandled exceptions."

                anomalies.append(
                    {
                        "id": f"err_spike_{ns}_{svc}",
                        "type": "HTTP_5XX_ERROR_RATE_ANOMALY",
                        "severity": "CRITICAL" if err_pct > 25.0 else "WARNING",
                        "namespace": ns,
                        "service": svc,
                        "message": msg,
                        "current_value": err_pct,
                        "unit": "%",
                        "recommendation": rec,
                    }
                )

            if p99_ms > 1000.0:
                if is_pt:
                    msg = f"Latência do serviço {svc} está inaceitavelmente alta (p99={p99_ms}ms)."
                    rec = "Inspecionar consultas lentas no Cloud SQL ou atrasos na fila SQS."
                else:
                    msg = f"Service {svc} latency is unacceptably high (p99={p99_ms}ms)."
                    rec = "Inspect downstream queries in Cloud SQL or SQS backlog delays."

                anomalies.append(
                    {
                        "id": f"lat_spike_{ns}_{svc}",
                        "type": "LATENCY_DEGRADATION_ANOMALY",
                        "severity": "CRITICAL" if p99_ms > 3000.0 else "WARNING",
                        "namespace": ns,
                        "service": svc,
                        "message": msg,
                        "current_value": p99_ms,
                        "unit": "ms",
                        "recommendation": rec,
                    }
                )
        return anomalies

    def analyze_storage_risks(self, pvcs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        risks = []
        is_pt = settings.AIOPS_LANGUAGE.lower().startswith("pt")
        for pvc in pvcs:
            hs_full = float(pvc.get("hours_to_full", 999.0))
            used_pct = float(pvc.get("used_pct", 0.0))
            if used_pct > 85.0 or hs_full < 24.0:
                if is_pt:
                    msg = f"PVC {pvc.get('pvc')} está com {used_pct}% de uso. Previsão de esgotamento em {hs_full} horas."
                    rec = "Expandir capacidade do PVC via StorageClass ou limpar logs/dados antigos."
                else:
                    msg = f"PVC {pvc.get('pvc')} is {used_pct}% full. Projected to exhaust in {hs_full} hours."
                    rec = "Expand PVC capacity via StorageClass or cleanup old logs/data."

                risks.append(
                    {
                        "id": f"disk_full_{pvc.get('namespace')}_{pvc.get('pvc')}",
                        "type": "STORAGE_EXHAUSTION_PREDICTION",
                        "severity": "CRITICAL" if used_pct > 92.0 else "WARNING",
                        "namespace": pvc.get("namespace"),
                        "pvc": pvc.get("pvc"),
                        "message": msg,
                        "estimated_hours_to_failure": hs_full,
                        "recommendation": rec,
                    }
                )
        return risks

    def calculate_cluster_health_score(
        self, predictions: List[Any], anomalies: List[Any], events: List[Any]
    ) -> int:
        score = 100
        for p in predictions:
            if p.get("severity") == "CRITICAL":
                score -= 15
            elif p.get("severity") == "WARNING":
                score -= 5

        for a in anomalies:
            if a.get("severity") == "CRITICAL":
                score -= 15
            elif a.get("severity") == "WARNING":
                score -= 5

        score -= min(15, len(events) * 2)
        return max(0, min(100, score))
