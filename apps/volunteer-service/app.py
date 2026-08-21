import os
import sys
import uuid
import time
import logging
import boto3
from flask import Flask, request, jsonify

# Inicialização do New Relic Agent com suporte a AI Monitoring (AIM)
try:
    import newrelic.agent
    newrelic.agent.initialize()
except Exception as nr_err:
    logging.getLogger(__name__).warning(f"New Relic initialization skipped or failed: {nr_err}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMODB_TABLE = os.getenv("AWS_DYNAMODB_TABLE")

if not DYNAMODB_TABLE:
    log.critical("Erro: AWS_DYNAMODB_TABLE não definida.")
    sys.exit(1)

try:
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION, endpoint_url=endpoint_url)
    else:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    log.info(f"Conectado à tabela DynamoDB: {DYNAMODB_TABLE}")
except Exception as e:
    log.critical(f"Falha ao conectar no DynamoDB: {e}")
    sys.exit(1)

@app.route('/volunteer-service/health')
@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "volunteer-service"})

@app.route('/volunteers', methods=['POST'])
@app.route('/volunteer-service/volunteers', methods=['POST'])
def register_volunteer():
    data = request.get_json()
    if not data or not all(k in data for k in ('name', 'email', 'ngo_id')):
        return jsonify({"error": "Campos obrigatórios ausentes"}), 400
    
    volunteer_id = str(uuid.uuid4())
    event_id = data.get('event_id') or str(uuid.uuid4())
    item = {
        'event_id': event_id,
        'volunteer_id': volunteer_id,
        'name': data['name'],
        'email': data['email'],
        'ngo_id': int(data['ngo_id']),
        'registered_at': str(int(time.time()))
    }
    
    try:
        table.put_item(Item=item)
        return jsonify(item), 201
    except Exception as e:
        log.error(f"Erro ao salvar voluntário no DynamoDB: {e}")
        return jsonify({"error": "Erro interno ao processar dados"}), 500

@app.route('/volunteers/<int:ngo_id>', methods=['GET'])
@app.route('/volunteer-service/volunteers/<int:ngo_id>', methods=['GET'])
def get_volunteers_by_ngo(ngo_id):
    try:
        # Nota para avaliação dos alunos: Operação Scan simplificada para fins de desenvolvimento.
        # Em cenários complexos de produção, índices globais secundários (GSI) seriam exigidos.
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('ngo_id').eq(ngo_id)
        )
        return jsonify(response.get('Items', [])), 200
    except Exception as e:
        log.error(f"Erro ao buscar dados no DynamoDB: {e}")
        return jsonify({"error": "Erro interno"}), 500

@app.route('/error', methods=['GET'])
@app.route('/volunteer-service/error', methods=['GET'])
def error():
    return jsonify({"error": "Erro interno"}), 500

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8083))
    app.run(host='0.0.0.0', port=port)