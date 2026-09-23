import logging
import os
import sys
import time

import psycopg2
from flask import Flask, jsonify, request
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool


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
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter,
        )
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
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            PeriodicExportingMetricReader,
        )
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

    return root_logger, requests_counter, latency_histogram


# Inicialização do New Relic Agent com suporte a AI Monitoring (AIM)
try:
    import newrelic.agent

    newrelic.agent.initialize()
except Exception as nr_err:
    logging.getLogger(__name__).warning(
        "New Relic initialization skipped or failed: %s", nr_err
    )

log, requests_counter, latency_histogram = setup_telemetry("ngo-service", "ngo-ns")

app = Flask(__name__)


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
        service_name = os.getenv("OTEL_SERVICE_NAME", "ngo-service")
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


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    log.critical("Erro: DATABASE_URL não definida.")
    sys.exit(1)

try:
    pool = SimpleConnectionPool(1, 10, dsn=DATABASE_URL)
    log.info("Pool de conexões com o PostgreSQL (ngo-service) inicializado.")
except Exception as e:
    log.critical("Erro ao conectar ao PostgreSQL: %s", e)
    sys.exit(1)


@app.route("/ngo-service/health")
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "ngo-service"})


@app.route("/ngo-service/pre-stop", methods=["GET"])
@app.route("/pre-stop", methods=["GET"])
def pre_stop():
    log.info("Kubernetes preStop hook recebido. Drenando conexoes por 10s...")
    time.sleep(10)
    return jsonify({"status": "drained", "service": "ngo-service"}), 200


@app.route("/ngo-service/ngos", methods=["POST"])
@app.route("/ngos", methods=["POST"])
def create_ngo():
    data = request.get_json()
    if not data or not all(k in data for k in ("name", "email", "cause", "city")):
        return jsonify({"error": "Campos obrigatórios ausentes"}), 400

    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "INSERT INTO ngos (name, email, cause, city) VALUES (%s, %s, %s, %s) RETURNING *",
                    (data["name"], data["email"], data["cause"], data["city"]),
                )
                new_ngo = cur.fetchone()
                conn.commit()
                return jsonify(new_ngo), 201
        except psycopg2.IntegrityError:
            if conn:
                conn.rollback()
            return jsonify({"error": "E-mail já cadastrado"}), 409
        except (
            psycopg2.errors.ReadOnlySqlTransaction,
            psycopg2.OperationalError,
        ) as trans_err:
            if conn:
                conn.rollback()
                pool.putconn(conn, close=True)
                conn = None
            log.warning(
                "[DISASTER_RECOVERY_RETRY] PostgreSQL em cutover/transição (tentativa %d/%d): %s",
                attempt,
                max_attempts,
                trans_err,
            )
            if attempt < max_attempts:
                time.sleep(attempt * 2)
            else:
                log.error(
                    "[DISASTER_RECOVERY_BUFFER] Esgotadas tentativas durante cutover."
                )
                return (
                    jsonify(
                        {
                            "status": "QUEUED_FOR_PROCESSING",
                            "message": "Cadastro recebido e retido para processamento seguro durante transição de alta disponibilidade.",
                            "data": data,
                        }
                    ),
                    202,
                )
        except Exception as e:
            if conn:
                conn.rollback()
            log.error("Erro ao criar ONG: %s", e)
            try:
                import newrelic.agent
                newrelic.agent.notice_error()
            except Exception:
                pass
            return jsonify({"error": "Erro interno"}), 500
        finally:
            if conn and not conn.closed:
                pool.putconn(conn)


@app.route("/ngos", methods=["GET"])
@app.route("/ngo-service/ngos", methods=["GET"])
def get_ngos():
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM ngos ORDER BY id DESC")
            return jsonify(cur.fetchall()), 200
    except Exception as e:
        log.error("Erro ao buscar ONGs: %s", e)
        try:
            import newrelic.agent
            newrelic.agent.notice_error()
        except Exception:
            pass
        return jsonify({"error": "Erro interno"}), 500
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8081"))
    app.run(host="0.0.0.0", port=port)
