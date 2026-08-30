import os
import sys
import re
import requests
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Inicializa o provedor utilizando as variáveis de ambiente padrão do OpenTelemetry injetadas pelo Kubernetes
resource = Resource.create()
provider = TracerProvider(resource=resource)

# O OtlpGrpcSpanExporter lê automaticamente variáveis como OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_INSECURE, etc.
exporter = OTLPSpanExporter()
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Obtém o nome do serviço para logs e tracing
service_name = os.getenv("OTEL_SERVICE_NAME", "gcp-status-checker")
tracer = trace.get_tracer(service_name)

# Configuração dos serviços e regiões monitorados
TARGET_SERVICES_RAW = os.getenv("TARGET_SERVICES", "Cloud SQL,Google Kubernetes Engine")
TARGET_SERVICES = [s.strip() for s in TARGET_SERVICES_RAW.split(",") if s.strip()]
TARGET_REGION = os.getenv("TARGET_REGION", "").strip().lower()

# Modo de Simulação para Testes e Demonstrações de Disaster Recovery
# SIMULATION_MODE: "true" ou "false" (default: "false" -> funcionamento normal)
# SIMULATED_OUTAGE_SERVICES: nomes dos serviços com falha simulada (ex: "Cloud SQL" ou "Google Kubernetes Engine" ou "all")
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "false").strip().lower() in ("true", "1", "yes")
SIMULATED_OUTAGE_SERVICES_RAW = os.getenv("SIMULATED_OUTAGE_SERVICES", "")
SIMULATED_OUTAGE_SERVICES = [s.strip().lower() for s in SIMULATED_OUTAGE_SERVICES_RAW.split(",") if s.strip()]

# Sinônimos/Aliases comuns para busca precisa no feed da GCP
SERVICE_ALIASES = {
    "Cloud SQL": ["cloud sql", "sql"],
    "Google Kubernetes Engine": ["google kubernetes engine", "kubernetes engine", "gke", "kubernetes"],
    "Compute Engine": ["compute engine", "gce"],
    "Cloud Storage": ["cloud storage", "gcs"],
    "Artifact Registry": ["artifact registry", "gar"],
}

def slugify(text: str) -> str:
    """Converte o nome do serviço para formato de atributo OpenTelemetry (ex: cloud_sql)."""
    return re.sub(r'[^a-z0-9_]', '_', text.lower()).strip('_')

def matches_service(service: str, incident: dict) -> bool:
    """Verifica se um incidente afeta o serviço especificado."""
    aliases = SERVICE_ALIASES.get(service, [service.lower()])
    
    # 1. Checa o campo service_name principal
    service_name_incident = (incident.get("service_name") or "").lower()
    for alias in aliases:
        if alias in service_name_incident:
            return True
            
    # 2. Checa os produtos afetados no array affected_products
    for prod in incident.get("affected_products", []):
        title = (prod.get("title") or "").lower()
        for alias in aliases:
            if alias in title:
                return True
                
    # 3. Checa a descrição externa caso seja incidente de múltiplos produtos
    if "multiple" in service_name_incident or not incident.get("affected_products"):
        desc = (incident.get("external_desc") or "").lower()
        for alias in aliases:
            if alias in desc:
                return True
                
    return False

def matches_region(incident: dict, target_region: str) -> bool:
    """Verifica se o incidente afeta a região configurada (ou se é global)."""
    if not target_region:
        return True  # Se não houver filtro de região, considera qualquer impacto
        
    locations = incident.get("currently_affected_locations", [])
    if not locations:
        return True  # Se não especifica localidades, pode ter impacto global
        
    for loc in locations:
        loc_id = (loc.get("id") or "").lower()
        loc_title = (loc.get("title") or "").lower()
        if target_region in loc_id or target_region in loc_title or "global" in loc_id:
            return True
            
    return False

def check_gcp_status():
    # URL oficial de incidentes em formato JSON da GCP
    url = "https://status.cloud.google.com/incidents.json"
    
    with tracer.start_as_current_span("check_gcp_resource_status") as span:
        span.set_attribute("gcp.monitored_services", TARGET_SERVICES)
        if TARGET_REGION:
            span.set_attribute("gcp.target_region", TARGET_REGION)
        span.set_attribute("gcp.simulation.active", SIMULATION_MODE)
            
        try:
            print(f"[{service_name}] [INFO] Consultando status oficial da GCP em {url}...")
            response = requests.get(url, timeout=10)
            span.set_attribute("http.status_code", response.status_code)
            
            if response.status_code != 200:
                print(f"[{service_name}] [ALERTA] Resposta inesperada da API da GCP! HTTP Status: {response.status_code}")
                span.set_attribute("gcp.overall.available", False)
                provider.shutdown()
                sys.exit(1)
                
            incidents_data = response.json()
            
            # Filtra apenas incidentes ativos (onde o campo 'end' é nulo ou vazio)
            active_incidents = [inc for inc in incidents_data if not inc.get("end")]

            # Se o modo de simulação estiver ativo, injeta incidentes simulados
            if SIMULATION_MODE and SIMULATED_OUTAGE_SERVICES:
                print(f"[{service_name}] [MODO SIMULAÇÃO ATIVO] Injetando falha simulada para: {', '.join(SIMULATED_OUTAGE_SERVICES)}")
                for sim_svc in SIMULATED_OUTAGE_SERVICES:
                    active_incidents.append({
                        "id": f"SIMULATED-DR-{sim_svc.upper().replace(' ', '-')}",
                        "service_name": sim_svc,
                        "severity": "high",
                        "status_impact": "SERVICE_OUTAGE",
                        "external_desc": f"[SIMULAÇÃO DISASTER RECOVERY] Falha simulada para demonstração de resiliência e failover no recurso {sim_svc}.",
                        "affected_products": [{"title": sim_svc}],
                        "currently_affected_locations": [{"id": TARGET_REGION or "southamerica-east1", "title": TARGET_REGION or "southamerica-east1"}],
                        "end": None
                    })

            span.set_attribute("gcp.total_active_incidents", len(active_incidents))
            
            has_unstable_monitored_service = False
            
            print(f"[{service_name}] [INFO] Monitorando {len(TARGET_SERVICES)} recurso(s): {', '.join(TARGET_SERVICES)}")
            
            for service in TARGET_SERVICES:
                slug = slugify(service)
                # Filtra incidentes que afetam este serviço e a região desejada
                service_incidents = [
                    inc for inc in active_incidents 
                    if matches_service(service, inc) and matches_region(inc, TARGET_REGION)
                ]
                
                is_available = len(service_incidents) == 0
                span.set_attribute(f"gcp.resource.{slug}.available", is_available)
                span.set_attribute(f"gcp.resource.{slug}.incident_count", len(service_incidents))
                
                if is_available:
                    print(f"[{service_name}] [INFO] ✅ {service}: Estável (Nenhum incidente ativo detectado).")
                else:
                    has_unstable_monitored_service = True
                    incident_ids = [inc.get("id") for inc in service_incidents]
                    severities = [inc.get("severity") for inc in service_incidents]
                    impacts = [inc.get("status_impact") for inc in service_incidents]
                    
                    span.set_attribute(f"gcp.resource.{slug}.incident_ids", incident_ids)
                    span.set_attribute(f"gcp.resource.{slug}.severity", severities)
                    span.set_attribute(f"gcp.resource.{slug}.status_impact", impacts)
                    
                    print(f"[{service_name}] [ALERTA] ⚠️ Instabilidade detectada em '{service}'!")
                    for inc in service_incidents:
                        print(f"[{service_name}] [ALERTA]   - Incidente ID: {inc.get('id')} | Severidade: {inc.get('severity')} | Impacto: {inc.get('status_impact')}")
                        print(f"[{service_name}] [ALERTA]   - Descrição: {inc.get('external_desc')}")
            
            span.set_attribute("gcp.overall.available", not has_unstable_monitored_service)
            
            if has_unstable_monitored_service:
                print(f"[{service_name}] [ALERTA] Um ou mais recursos monitorados apresentam degradação ou indisponibilidade na GCP.")
                provider.shutdown()
                sys.exit(1)
            else:
                print(f"[{service_name}] [INFO] Todos os recursos monitorados ({', '.join(TARGET_SERVICES)}) estão 100% operacionais.")
                provider.shutdown()
                
        except Exception as e:
            print(f"[{service_name}] [ERRO] Falha ao verificar status dos recursos na GCP: {e}")
            span.record_exception(e)
            span.set_attribute("gcp.overall.available", False)
            provider.shutdown()
            sys.exit(1)

if __name__ == "__main__":
    check_gcp_status()