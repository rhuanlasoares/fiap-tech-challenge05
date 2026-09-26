import logging
from typing import Any, Dict, List, Optional

from core.config import settings

logger = logging.getLogger("aiops.k8s")


class K8sClient:
    def __init__(self):
        self.client = None
        self.core_api = None
        self.apps_api = None
        self.custom_api = None
        self._init_client()

    def _init_client(self):
        try:
            from kubernetes import client, config

            try:
                config.load_incluster_config()
                logger.info("Loaded in-cluster Kubernetes config")
            except Exception:
                config.load_kube_config()
                logger.info("Loaded local kube-config")
            # Configura cliente sem retentativas infinitas para conexões remotas
            conf = client.Configuration.get_default_copy()
            conf.retries = 0
            api_client = client.ApiClient(configuration=conf)
            self.core_api = client.CoreV1Api(api_client=api_client)
            self.apps_api = client.AppsV1Api(api_client=api_client)
            self.custom_api = client.CustomObjectsApi(api_client=api_client)
        except Exception as e:
            logger.warning(f"Kubernetes client initialization failed: {e}")

    def get_cluster_warning_events(self, namespaces: List[str]) -> List[Dict[str, Any]]:
        if not self.core_api:
            return []
        events_list = []
        try:
            for ns in namespaces:
                events = self.core_api.list_namespaced_event(
                    namespace=ns, _request_timeout=5
                )
                for ev in events.items:
                    if ev.type == "Warning":
                        events_list.append(
                            {
                                "namespace": ns,
                                "reason": ev.reason,
                                "message": ev.message,
                                "involved_object": f"{ev.involved_object.kind}/{ev.involved_object.name}",
                                "count": ev.count or 1,
                                "last_timestamp": str(
                                    ev.last_timestamp or ev.event_time or ""
                                ),
                            }
                        )
        except Exception as e:
            logger.debug(f"Error fetching k8s events: {e}")
        return events_list

    def get_pods_status_summary(self, namespaces: List[str]) -> List[Dict[str, Any]]:
        if not self.core_api:
            return []
        pods_summary = []
        try:
            for ns in namespaces:
                pods = self.core_api.list_namespaced_pod(
                    namespace=ns, _request_timeout=5
                )
                for pod in pods.items:
                    restart_count = 0
                    if pod.status.container_statuses:
                        restart_count = sum(
                            cs.restart_count for cs in pod.status.container_statuses
                        )

                    pods_summary.append(
                        {
                            "namespace": ns,
                            "name": pod.metadata.name,
                            "phase": pod.status.phase,
                            "restart_count": restart_count,
                            "node_name": pod.spec.node_name,
                            "creation_timestamp": str(pod.metadata.creation_timestamp),
                        }
                    )
        except Exception as e:
            logger.debug(f"Error fetching k8s pods: {e}")
        return pods_summary

    def rollout_restart_deployment(self, namespace: str, deployment_name: str) -> bool:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"kubectl.kubernetes.io/restartedAt": now}
                    }
                }
            }
        }

        # 1. Try restarting as Argo Rollout
        if self.custom_api:
            try:
                self.custom_api.patch_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="rollouts",
                    name=deployment_name,
                    body=body,
                    _request_timeout=5,
                )
                logger.info(
                    f"Triggered Argo Rollout restart for {namespace}/{deployment_name}"
                )
                return True
            except Exception:
                pass

        # 2. Try restarting as standard K8s Deployment
        if self.apps_api:
            try:
                self.apps_api.patch_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace,
                    body=body,
                    _request_timeout=5,
                )
                logger.info(
                    f"Triggered K8s Deployment restart for {namespace}/{deployment_name}"
                )
                return True
            except Exception as e:
                logger.warning(
                    f"Failed to restart deployment/rollout {namespace}/{deployment_name}: {e}"
                )

        return False

    def check_connectivity(self) -> Dict[str, Any]:
        """Testa se a API do Kubernetes está acessível e se possui permissão de leitura."""
        import time

        t0 = time.time()
        res: Dict[str, Any] = {
            "status": "unhealthy",
            "latency_ms": 0.0,
            "can_access_api": False,
            "message": "",
        }
        if not self.core_api:
            res["message"] = "Kubernetes client não inicializado (fora do cluster ou sem kube-config)."
            return res
        try:
            ns_list = self.core_api.list_namespace(limit=1, _request_timeout=3)
            res["latency_ms"] = round((time.time() - t0) * 1000, 2)
            res["status"] = "healthy"
            res["can_access_api"] = True
            res["message"] = f"K8s API Server 100% operacional ({res['latency_ms']}ms)."
        except Exception as e:
            res["latency_ms"] = round((time.time() - t0) * 1000, 2)
            res["message"] = f"Falha ao consultar K8s API Server: {e}"
        return res
