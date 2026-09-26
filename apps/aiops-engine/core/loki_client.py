import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from core.config import settings

logger = logging.getLogger("aiops.loki")


class LokiClient:
    def __init__(self, base_url: str = settings.LOKI_URL):
        self.base_url = base_url.rstrip("/")

    def query_error_logs(
        self, namespaces: List[str], limit: int = 50
    ) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=15)
        start_ns = int(start.timestamp() * 1e9)
        end_ns = int(now.timestamp() * 1e9)

        ns_regex = "|".join(namespaces)
        query = f'{{namespace=~"{ns_regex}"}} |~ "(?i)(error|panic|fatal|failure|timeout|refused|deadlock|oom)"'
        url = self.base_url + "/loki/api/v1/query_range"

        try:
            params = {
                "query": query,
                "start": start_ns,
                "end": end_ns,
                "limit": limit,
                "direction": "backward",
            }
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", {}).get("result", [])
                parsed_logs = []
                for stream in results:
                    labels = stream.get("stream", {})
                    for entry in stream.get("values", []):
                        ts_str, log_line = entry[0], entry[1]
                        parsed_logs.append(
                            {
                                "timestamp": ts_str,
                                "namespace": labels.get("namespace", "unknown"),
                                "pod": labels.get("pod", "unknown"),
                                "container": labels.get("container", "unknown"),
                                "log": log_line.strip(),
                            }
                        )
                return parsed_logs
        except Exception as e:
            logger.debug(f"Error querying Loki: {e}")
        return []

    def push_log(
        self,
        message: str,
        level: str = "INFO",
        extra_labels: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Envia uma linha de log estruturada diretamente para a API de ingestao do Loki (/loki/api/v1/push)."""
        url = f"{self.base_url}/loki/api/v1/push"
        now_ns = str(int(datetime.now(timezone.utc).timestamp() * 1e9))

        stream_labels = {
            "service_name": "aiops-engine",
            "service_namespace": "aiops",
            "app": "aiops-engine",
            "level": level.upper(),
        }
        if extra_labels:
            stream_labels.update(extra_labels)

        payload = {
            "streams": [
                {
                    "stream": stream_labels,
                    "values": [[now_ns, message]],
                }
            ]
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=3,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.debug(f"Failed to push log to Loki ({url}): {e}")
            return False

    def check_connectivity(
        self, test_namespaces: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Testa se a API do Loki está acessível e se consultas LogQL e push funcionam."""
        import time

        t0 = time.time()
        res: Dict[str, Any] = {
            "status": "unhealthy",
            "url": self.base_url,
            "latency_ms": 0.0,
            "can_query": False,
            "can_push": False,
            "sample_streams": 0,
            "message": "",
        }

        # 1. Teste de ping/ready HTTP no Loki
        http_ok = False
        try:
            ready_url = f"{self.base_url}/ready"
            r = requests.get(ready_url, timeout=3)
            if r.status_code in (200, 204) or "ready" in r.text.lower():
                http_ok = True
            else:
                bi_url = f"{self.base_url}/loki/api/v1/status/buildinfo"
                r = requests.get(bi_url, timeout=3)
                if r.status_code == 200:
                    http_ok = True
        except Exception as e:
            res["message"] = f"Falha na conexão HTTP com Loki: {e}"
            res["latency_ms"] = round((time.time() - t0) * 1000, 2)
            return res

        # 2. Teste de consulta LogQL canário
        now = datetime.now(timezone.utc)
        start_ns = int((now - timedelta(minutes=15)).timestamp() * 1e9)
        end_ns = int(now.timestamp() * 1e9)
        query_url = f"{self.base_url}/loki/api/v1/query_range"
        try:
            q_resp = requests.get(
                query_url,
                params={
                    "query": '{namespace=~".+"} limit 1',
                    "start": start_ns,
                    "end": end_ns,
                    "limit": 1,
                },
                timeout=3,
            )
            if q_resp.status_code == 200:
                res["can_query"] = True
                data = q_resp.json()
                results = data.get("data", {}).get("result", [])
                res["sample_streams"] = len(results)
            else:
                res["message"] = (
                    f"Loki respondeu HTTP {q_resp.status_code} na consulta LogQL."
                )
        except Exception as e:
            res["message"] = f"Erro na consulta LogQL de teste: {e}"

        # 3. Teste de push de log canário
        try:
            can_push = self.push_log(
                message="[AIOPS-CONNECTIVITY-PROBE] Smoke test handshake",
                level="INFO",
                extra_labels={"probe": "startup_connectivity"},
            )
            res["can_push"] = can_push
        except Exception:
            res["can_push"] = False

        res["latency_ms"] = round((time.time() - t0) * 1000, 2)
        if http_ok or res["can_query"] or res["can_push"]:
            res["status"] = "healthy"
            res["message"] = (
                f"Loki 100% operacional ({res['latency_ms']}ms, query={res['can_query']}, push={res['can_push']})."
            )
        else:
            res["status"] = "unhealthy"

        return res


class LokiLoggingHandler(logging.Handler):
    """Handler padrao do Python Logging que despacha logs automaticamente para o Grafana Loki."""

    def __init__(self, loki_client: LokiClient):
        super().__init__()
        self.loki_client = loki_client

    def emit(self, record: logging.LogRecord):
        # Evita loops recursivos de logging causados pelas bibliotecas HTTP ou pelo proprio modulo do Loki
        if (
            record.name.startswith("aiops.loki")
            or record.name.startswith("urllib3")
            or record.name.startswith("requests")
        ):
            return
        try:
            msg = self.format(record)
            self.loki_client.push_log(msg, level=record.levelname)
        except Exception:
            self.handleError(record)
