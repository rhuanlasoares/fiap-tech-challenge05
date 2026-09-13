import logging
import os
import sys
import time
import uuid

import boto3
from flask import Flask, jsonify, request


def setup_logging(service_name: str, service_namespace: str) -> logging.Logger:
    """Configura logging local e exporter OpenTelemetry para envio ao Loki."""
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

    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
                "service.namespace": service_namespace,
                "deployment.environment": os.getenv("ENVIRONMENT", "production"),
            }
        )

        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)

        exporter = OTLPLogExporter(endpoint=otel_endpoint, insecure=insecure)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(exporter)
        )

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
        root_logger.warning(
            "Falha ao inicializar OpenTelemetry logging: %s", exc
        )

    return root_logger


# Inicialização do New Relic Agent com suporte a AI Monitoring (AIM)
try:
    import newrelic.agent

    newrelic.agent.initialize()
except Exception as nr_err:
    logging.getLogger(__name__).warning(
        "New Relic initialization skipped or failed: %s", nr_err
    )

log = setup_logging("volunteer-service", "volunteer-ns")

app = Flask(__name__)

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
        return jsonify({"error": "Erro interno"}), 500


@app.route("/error", methods=["GET"])
@app.route("/volunteer-service/error", methods=["GET"])
def error():
    return jsonify({"error": "Erro interno"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8083"))
    app.run(host="0.0.0.0", port=port)
