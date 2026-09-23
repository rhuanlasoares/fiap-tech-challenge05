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
