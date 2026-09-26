import logging
import os
import sys
import time
import uuid

import boto3
from flask import Flask, jsonify, request


def setup_telemetry(service_name: str, service_namespace: str):
    """Configura logging (Loki) e métricas (Prometheus) via OpenTelemetry Collector."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    if not root_logger.handlers:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    otel_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "opentelemetry-collector.monitoring-ns.svc.cluster.local:4317",
    )
    insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() != "false"
    pod_name = os.getenv("POD_NAME", "unknown")

    # 1. OpenTelemetry Logging (Loki)
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import \
            OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource

        log_resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
                "service.namespace": service_namespace,
                "deployment.environment": os.getenv("ENVIRONMENT", "production"),
                "pod": pod_name,
                "k8s.pod.name": pod_name,
            }
        )

        logger_provider = LoggerProvider(resource=log_resource)
        set_logger_provider(logger_provider)

        log_exporter = OTLPLogExporter(endpoint=otel_endpoint, insecure=insecure)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))

        has_otel = any(isinstance(h, LoggingHandler) for h in root_logger.handlers)
        if not has_otel:
            otel_handler = LoggingHandler(
                level=logging.INFO, logger_provider=logger_provider
            )
            root_logger.addHandler(otel_handler)
        root_logger.info(
            "OpenTelemetry logging inicializado para %s -> %s",
            service_name,
            otel_endpoint,
        )
    except Exception as exc:
        root_logger.warning("Falha ao inicializar OpenTelemetry logging: %s", exc)

    # 2. OpenTelemetry Metrics (Prometheus via OTel Collector)
    requests_counter = None
    latency_histogram = None
    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import \
            OTLPMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import \
            PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource

        metric_resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
                "service.namespace": service_namespace,
                "deployment.environment": os.getenv("ENVIRONMENT", "production"),
                "pod": pod_name,
                "k8s.pod.name": pod_name,
            }
        )

        metric_exporter = OTLPMetricExporter(endpoint=otel_endpoint, insecure=insecure)
        reader = PeriodicExportingMetricReader(
            metric_exporter, export_interval_millis=5000
        )
        meter_provider = MeterProvider(
            resource=metric_resource, metric_readers=[reader]
        )
        metrics.set_meter_provider(meter_provider)
        meter = metrics.get_meter(service_name)

        requests_counter = meter.create_counter(
            "http_requests_total",
            description="Total number of HTTP requests processed",
        )
        latency_histogram = meter.create_histogram(
            "http_server_duration_milliseconds",
            description="Duration of HTTP requests in milliseconds",
            unit="ms",
        )
        root_logger.info(
            "OpenTelemetry metrics inicializado para %s -> %s",
            service_name,
            otel_endpoint,
        )
    except Exception as exc:
        root_logger.warning("Falha ao inicializar OpenTelemetry metrics: %s", exc)

    # 3. OpenTelemetry Tracing (Traces & Server Spans para New Relic APM via OTel Collector)
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
            OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        trace_resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
                "service.namespace": service_namespace,
                "deployment.environment": os.getenv("ENVIRONMENT", "production"),
                "pod": pod_name,
                "k8s.pod.name": pod_name,
            }
        )

        span_exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=insecure)
        tracer_provider = TracerProvider(resource=trace_resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)
        root_logger.info(
            "OpenTelemetry tracing inicializado para %s -> %s",
            service_name,
            otel_endpoint,
        )
    except Exception as exc:
        root_logger.warning("Falha ao inicializar OpenTelemetry tracing: %s", exc)

    return root_logger, requests_counter, latency_histogram


# Inicialização do New Relic Agent com suporte a AI Monitoring (AIM)
try:
    import newrelic.agent

    newrelic.agent.initialize()
except Exception as nr_err:
    logging.getLogger(__name__).warning(
        "New Relic initialization skipped or failed: %s", nr_err
    )

log, requests_counter, latency_histogram = setup_telemetry(
    "volunteer-service", "volunteer-ns"
)

app = Flask(__name__)

# Auto-instrumentação OpenTelemetry para Flask e Boto3 (Gera Server Spans para o New Relic APM)
try:
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    FlaskInstrumentor().instrument_app(app)
except Exception as exc:
    log.warning("Falha ao instrumentar Flask com OpenTelemetry: %s", exc)

try:
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

    BotocoreInstrumentor().instrument()
except Exception as exc:
    log.warning("Falha ao instrumentar Botocore com OpenTelemetry: %s", exc)


@app.before_request
def before_request():
    request._start_time = time.time()


@app.after_request
def after_request(response):
    try:
        # Notifica explicitamente o New Relic sobre status HTTP 5xx
        if response.status_code >= 500:
            try:
                import newrelic.agent

                newrelic.agent.notice_error()
            except Exception:
                pass

        start_time = getattr(request, "_start_time", None)
        duration_ms = (time.time() - start_time) * 1000 if start_time else 0.0
        status_str = str(response.status_code)
        pod_name = os.getenv("POD_NAME", "unknown")
        service_name = os.getenv("OTEL_SERVICE_NAME", "volunteer-service")
        route = request.path

        attrs = {
            "service_name": service_name,
            "status": status_str,
            "http_status_code": status_str,
            "http_response_status_code": status_str,
            "http_method": request.method,
            "http_request_method": request.method,
            "http_route": route,
            "pod": pod_name,
        }

        if requests_counter:
            requests_counter.add(1, attrs)
        if latency_histogram:
            latency_histogram.record(duration_ms, attrs)
    except Exception as e:
        log.warning("Erro ao registrar métricas HTTP: %s", e)
    return response


AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMODB_TABLE = os.getenv("AWS_DYNAMODB_TABLE")

if not DYNAMODB_TABLE:
    log.critical("Erro: AWS_DYNAMODB_TABLE não definida.")
    sys.exit(1)

try:
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        dynamodb = boto3.resource(
            "dynamodb", region_name=AWS_REGION, endpoint_url=endpoint_url
        )
    else:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    log.info("Conectado à tabela DynamoDB: %s", DYNAMODB_TABLE)
except Exception as e:
    log.critical("Falha ao conectar no DynamoDB: %s", e)
    sys.exit(1)


@app.route("/volunteer-service/health")
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "volunteer-service"})


@app.route("/volunteer-service/pre-stop", methods=["GET"])
@app.route("/pre-stop", methods=["GET"])
def pre_stop():
    log.info("Kubernetes preStop hook recebido. Drenando conexoes por 10s...")
    time.sleep(10)
    return jsonify({"status": "drained", "service": "volunteer-service"}), 200


@app.route("/volunteers", methods=["POST"])
@app.route("/volunteer-service/volunteers", methods=["POST"])
def register_volunteer():
    data = request.get_json()
    if not data or not all(k in data for k in ("name", "email", "ngo_id")):
        return jsonify({"error": "Campos obrigatórios ausentes"}), 400

    volunteer_id = str(uuid.uuid4())
    event_id = data.get("event_id") or str(uuid.uuid4())
    item = {
        "event_id": event_id,
        "volunteer_id": volunteer_id,
        "name": data["name"],
        "email": data["email"],
        "ngo_id": int(data["ngo_id"]),
        "registered_at": str(int(time.time())),
    }

    try:
        table.put_item(Item=item)
        return jsonify(item), 201
    except Exception as e:
        log.error("Erro ao salvar voluntário no DynamoDB: %s", e)
        try:
            import newrelic.agent

            newrelic.agent.notice_error()
        except Exception:
            pass
        return jsonify({"error": "Erro interno ao processar dados"}), 500


@app.route("/volunteers/<int:ngo_id>", methods=["GET"])
@app.route("/volunteer-service/volunteers/<int:ngo_id>", methods=["GET"])
def get_volunteers_by_ngo(ngo_id):
    try:
        # Nota para avaliação dos alunos: Operação Scan simplificada para fins de desenvolvimento.
        # Em cenários complexos de produção, índices globais secundários (GSI) seriam exigidos.
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr("ngo_id").eq(ngo_id)
        )
        return jsonify(response.get("Items", [])), 200
    except Exception as e:
        log.error("Erro ao buscar dados no DynamoDB: %s", e)
        try:
            import newrelic.agent

            newrelic.agent.notice_error()
        except Exception:
            pass
        return jsonify({"error": "Erro interno"}), 500


@app.route("/error", methods=["GET"])
@app.route("/volunteer-service/error", methods=["GET"])
def error():
    try:
        import newrelic.agent

        newrelic.agent.notice_error()
    except Exception:
        pass
    return jsonify({"error": "Erro interno"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8083"))
    app.run(host="0.0.0.0", port=port)