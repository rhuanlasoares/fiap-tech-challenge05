import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from core.config import settings

logger = logging.getLogger("aiops.prometheus")

class PrometheusClient:
    def __init__(self, base_url: str = settings.PROMETHEUS_URL):
        self.base_url = base_url.rstrip("/")

    def query(self, promql: str) -> Optional[List[Dict[str, Any]]]:
        url = self.base_url + "/api/v1/query"
        try:
            resp = requests.get(url, params={"query": promql}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data.get("data", {}).get("result", [])
            logger.warning(f"Prometheus query failed: {promql} -> Status {resp.status_code}")
        except Exception as e:
            logger.debug(f"Error querying Prometheus: {e}")
        return None

    def query_range(self, promql: str, start_ts: int, end_ts: int, step: str = "60s") -> Optional[List[Dict[str, Any]]]:
        url = self.base_url + "/api/v1/query_range"
        try:
            params = {
                "query": promql,
                "start": start_ts,
                "end": end_ts,
                "step": step
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data.get("data", {}).get("result", [])
        except Exception as e:
            logger.debug(f"Error range querying Prometheus: {e}")
        return None

    def get_container_memory_trends(self, namespaces: List[str], window_minutes: int = 30) -> List[Dict[str, Any]]:
        now = int(datetime.now(timezone.utc).timestamp())
        start = now - (window_minutes * 60)
        ns_regex = "|".join(namespaces)
        
        mem_query = f'container_memory_working_set_bytes{{namespace=~"{ns_regex}", container!="", container!="POD"}}'
        limit_query = f'container_spec_memory_limit_bytes{{namespace=~"{ns_regex}", container!="", container!="POD"}}'

        mem_results = self.query_range(mem_query, start, now, step="60s")
        limit_results = self.query(limit_query)

        limits_map = {}
        if limit_results:
            for item in limit_results:
                metric = item.get("metric", {})
                key = f"{metric.get('namespace')}/{metric.get('pod')}/{metric.get('container')}"
                try:
                    val = float(item.get("value", [0, 0])[1])
                    if val > 0:
                        limits_map[key] = val
                except (ValueError, IndexError):
                    pass

        trends = []
        if mem_results:
            for item in mem_results:
                metric = item.get("metric", {})
                namespace = metric.get("namespace")
                pod = metric.get("pod")
                container = metric.get("container")
                key = f"{namespace}/{pod}/{container}"
                values = item.get("values", [])
                
                if len(values) >= 3:
                    parsed_values = []
                    for ts, val in values:
                        try:
                            parsed_values.append((int(ts), float(val)))
                        except (ValueError, TypeError):
                            pass
                    
                    if parsed_values:
                        trends.append({
                            "key": key,
                            "namespace": namespace,
                            "pod": pod,
                            "container": container,
                            "values": parsed_values,
                            "limit_bytes": limits_map.get(key, 0.0),
                            "current_bytes": parsed_values[-1][1]
                        })
        return trends

    def get_http_golden_signals(self, namespaces: List[str]) -> List[Dict[str, Any]]:
        ns_regex = "|".join(namespaces)
        
        rate_query = f'sum by (namespace, service, job) (rate(http_requests_total{{namespace=~"{ns_regex}"}}[2m]))'
        errors_query = f'sum by (namespace, service, job) (rate(http_requests_total{{namespace=~"{ns_regex}", status=~"5.."}}[2m]))'
        lat95 = f'histogram_quantile(0.95, sum by (le, namespace, service) (rate(http_request_duration_seconds_bucket{{namespace=~"{ns_regex}"}}[5m])))'
        lat99 = f'histogram_quantile(0.99, sum by (le, namespace, service) (rate(http_request_duration_seconds_bucket{{namespace=~"{ns_regex}"}}[5m])))'

        rates = self.query(rate_query) or []
        errors = self.query(errors_query) or []
        l95 = self.query(lat95) or []
        l99 = self.query(lat99) or []

        signals = {}
        for r in rates:
            metric = r.get("metric", {})
            svc = metric.get("service") or metric.get("job") or "unknown"
            ns = metric.get("namespace", "default")
            key = f"{ns}/{svc}"
            val = float(r.get("value", [0, 0])[1])
            signals[key] = {
                "namespace": ns,
                "service": svc,
                "req_per_sec": round(val, 2),
                "error_5xx_per_sec": 0.0,
                "error_rate_pct": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0
            }

        for e in errors:
            metric = e.get("metric", {})
            svc = metric.get("service") or metric.get("job") or "unknown"
            ns = metric.get("namespace", "default")
            key = f"{ns}/{svc}"
            err_val = float(e.get("value", [0, 0])[1])
            if key in signals:
                signals[key]["error_5xx_per_sec"] = round(err_val, 2)
                rps = signals[key]["req_per_sec"]
                if rps > 0:
                    signals[key]["error_rate_pct"] = round((err_val / rps) * 100, 2)

        for l in l95:
            metric = l.get("metric", {})
            svc = metric.get("service") or metric.get("job") or "unknown"
            ns = metric.get("namespace", "default")
            key = f"{ns}/{svc}"
            val = float(l.get("value", [0, 0])[1])
            if key in signals and val > 0:
                signals[key]["p95_latency_ms"] = round(val * 1000, 2)

        for l in l99:
            metric = l.get("metric", {})
            svc = metric.get("service") or metric.get("job") or "unknown"
            ns = metric.get("namespace", "default")
            key = f"{ns}/{svc}"
            val = float(l.get("value", [0, 0])[1])
            if key in signals and val > 0:
                signals[key]["p99_latency_ms"] = round(val * 1000, 2)

        return list(signals.values())

    def get_pvc_storage_forecast(self) -> List[Dict[str, Any]]:
        used_q = "kubelet_volume_stats_used_bytes"
        cap_q = "kubelet_volume_stats_capacity_bytes"
        pred_q = "predict_linear(kubelet_volume_stats_available_bytes[2h], 8 * 3600)"

        used = self.query(used_q) or []
        caps = self.query(cap_q) or []
        preds = self.query(pred_q) or []

        pvcs = {}
        for c in caps:
            metric = c.get("metric", {})
            pvc_name = metric.get("persistentvolumeclaim")
            ns = metric.get("namespace")
            if pvc_name and ns:
                key = f"{ns}/{pvc_name}"
                val = float(c.get("value", [0, 0])[1])
                pvcs[key] = {
                    "namespace": ns,
                    "pvc": pvc_name,
                    "capacity_bytes": val,
                    "used_bytes": 0.0,
                    "used_pct": 0.0,
                    "hours_to_full": 999.0
                }

        for u in used:
            metric = u.get("metric", {})
            pvc_name = metric.get("persistentvolumeclaim")
            ns = metric.get("namespace")
            key = f"{ns}/{pvc_name}"
            if key in pvcs:
                val = float(u.get("value", [0, 0])[1])
                pvcs[key]["used_bytes"] = val
                cap = pvcs[key]["capacity_bytes"]
                if cap > 0:
                    pvcs[key]["used_pct"] = round((val / cap) * 100, 1)

        for p in preds:
            metric = p.get("metric", {})
            pvc_name = metric.get("persistentvolumeclaim")
            ns = metric.get("namespace")
            key = f"{ns}/{pvc_name}"
            val = float(p.get("value", [0, 0])[1])
            if key in pvcs and val <= 0:
                pvcs[key]["hours_to_full"] = round(8.0 * (pvcs[key]["capacity_bytes"] - pvcs[key]["used_bytes"]) / max(1.0, pvcs[key]["capacity_bytes"]), 1)

        return list(pvcs.values())

    def get_node_health_summary(self) -> List[Dict[str, Any]]:
        node_cpu = self.query("100 - (avg by (instance) (rate(node_cpu_seconds_total{mode='idle'}[2m])) * 100)") or []
        node_mem = self.query("(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100") or []

        nodes = {}
        for c in node_cpu:
            inst = c.get("metric", {}).get("instance", "unknown")
            val = float(c.get("value", [0, 0])[1])
            nodes[inst] = {"instance": inst, "cpu_usage_pct": round(val, 1), "mem_usage_pct": 0.0}

        for m in node_mem:
            inst = m.get("metric", {}).get("instance", "unknown")
            val = float(m.get("value", [0, 0])[1])
            if inst in nodes:
                nodes[inst]["mem_usage_pct"] = round(val, 1)
            else:
                nodes[inst] = {"instance": inst, "cpu_usage_pct": 0.0, "mem_usage_pct": round(val, 1)}

        return list(nodes.values())
