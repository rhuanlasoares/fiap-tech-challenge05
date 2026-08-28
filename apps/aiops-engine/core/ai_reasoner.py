import logging
import json
from typing import Dict, List, Any, Optional
from core.config import settings

logger = logging.getLogger("aiops.ai_reasoner")

class AasReasoner:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.model = None
        self._init_gemini()

    def _init_gemini(self):
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                
                available_models = []
                try:
                    for m in genai.list_models():
                        if "generateContent" in getattr(m, "supported_generation_methods", []):
                            available_models.append(m.name.replace("models/", ""))
                except Exception as list_err:
                    logger.debug(f"Could not list models: {list_err}")

                logger.info(f"Available Gemini models for key: {available_models}")

                preferred_models = [
                    "gemini-3.6-flash",
                    "gemini-3.5-flash-lite",
                    "gemini-3-flash-preview",
                    "gemini-3.1-flash-lite",
                    "gemini-3.1-flash-lite-preview",
                    "gemini-3.5-flash",
                    "gemini-3.1-pro-preview",
                    "gemini-flash-latest",
                    "gemini-pro-latest"
                ]

                chosen = None
                for candidate in preferred_models:
                    if candidate in available_models:
                        chosen = candidate
                        break

                if not chosen:
                    chosen = available_models[0] if available_models else "gemini-3.6-flash"

                self.model_name = chosen
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"Initialized Gemini model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini API: {e}")

    def generate_rca(self, risk_or_anomaly: Dict[str, Any], context_logs: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.model:
            rca = self._call_gemini(risk_or_anomaly, context_logs, events)
            if rca:
                return rca
        return self._expert_rulebook_rca(risk_or_anomaly, context_logs, events)

    def _call_gemini(self, item: Dict[str, Any], logs: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        import google.generativeai as genai
        prompt = (
            "You are an expert SRE and AIOps Engineer monitoring a GKE cluster running Cloud SQL, DynamoDB, SQS, and microservices (Donation, NGO, Volunteer).\n"
            "Analyze this incident telemetry:\n"
            + json.dumps(item, indent=2, default=str)
            + "\nProvide RCA in strict JSON format: {title, severity, affected_service, probable_root_cause, time_to_impact_minutes, recommended_action, prevention_playbook}"
        )
        
        candidates = [
            self.model_name,
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.1-flash-lite-preview",
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview"
        ]
        unique_candidates = list(dict.fromkeys([c for c in candidates if c]))

        for candidate in unique_candidates:
            try:
                model = genai.GenerativeModel(candidate)
                resp = model.generate_content(prompt)
                text = resp.text.strip()
                if text.startswith("```json"):
                    text = text[7:-3].strip()
                elif text.startswith("```"):
                    text = text[3:-3].strip()
                result = json.loads(text)
                logger.info(f"Successfully generated RCA using Gemini model: {candidate}")
                return result
            except Exception as e:
                logger.warning(f"Model '{candidate}' failed: {e}. Trying fallback model...")
        
        return None

    def _expert_rulebook_rca(self, item: Dict[str, Any], logs: List[Dict[str, Any]], events: List[Dict[str, Any]]) -> Dict[str, Any]:
        item_type = item.get("type", "")
        namespace = str(item.get("namespace", "default"))
        svc_pod = str(item.get("pod") or item.get("service") or item.get("pvc") or "unknown")

        if item_type == "MEMORY_LEAK_PREDICTION":
            mins = item.get("estimated_minutes_to_failure", 45)
            return {
                "title": f"Memory Leak Detected in {svc_pod}",
                "severity": item.get("severity", "CRITICAL"),
                "affected_service": svc_pod,
                "probable_root_cause": f"Continuous linear memory ramp without GC deallocation. Container will be terminated by Kernel OOM in {mins} minutes.",
                "time_to_impact_minutes": mins,
                "recommended_action": f"Execute graceful rollout restart via kubectl rollout restart deployment/{svc_pod} -n {namespace} before traffic drops.",
                "prevention_playbook": [
                    "Step 1: Trigger a rollout restart to reset heap memory allocations.",
                    "Step 2: Profile global variables, unclosed database connections, and IO buffers.",
                    "Step 3: Temporarily expand resource limits in deployment manifest."
                ]
            }
        elif item_type == "HTTP_5XX_ERROR_RATE_ANOMALY":
            return {
                "title": f"Excessive HTTP 5xx Surge on {svc_pod}",
                "severity": "CRITICAL",
                "affected_service": svc_pod,
                "probable_root_cause": f"Unhandled exceptions or upstream Cloud SQL / AWS authentication timeout. Error rate at {item.get('current_value')}%.",
                "time_to_impact_minutes": 0,
                "recommended_action": "Inspect Cloud SQL Proxy pods and verify database user authentication secrets.",
                "prevention_playbook": [
                    "Step 1: Check Cloud SQL connection pool saturation.",
                    "Step 2: Review latest Loki logs for SQL syntax or authorization denials.",
                    "Step 3: Verify otel-collector tracing spans for identifying the failing endpoint."
                ]
            }
        elif item_type == "LATENCY_DEGRADATION_ANOMALY":
            return {
                "title": f"Severe Latency Degradation on {svc_pod}",
                "severity": "WARNING",
                "affected_service": svc_pod,
                "probable_root_cause": "Database locks, slow queries, or CPU throttling causing p99 latency to spike.",
                "time_to_impact_minutes": 5,
                "recommended_action": "Scale out pod replicas and inspect pg_stat_activity for runaway queries.",
                "prevention_playbook": [
                    "Step 1: Increase pod replicas via KEDA / HPA.",
                    "Step 2: Analyze postgres locks or DynamoDB provisioned throughput exhaustion."
                ]
            }
        else:
            return {
                "title": f"System Telemetry Risk in {svc_pod}",
                "severity": item.get("severity", "INFO"),
                "affected_service": svc_pod,
                "probable_root_cause": str(item.get("message", "Anomalous system telemetry detected.")),
                "time_to_impact_minutes": 15,
                "recommended_action": str(item.get("recommendation", "Inspect pod telemetry and logs.")),
                "prevention_playbook": ["Check Metrics in Prometheus", "Review Logs in Loki", "Verify K8s Events"]
            }