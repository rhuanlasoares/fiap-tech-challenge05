import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

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
