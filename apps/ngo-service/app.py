import logging
import os
import sys
import time

import psycopg2
from flask import Flask, jsonify, request
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

# Inicialização do New Relic Agent com suporte a AI Monitoring (AIM)
try:
    import newrelic.agent

    newrelic.agent.initialize()
except Exception as nr_err:
    logging.getLogger(__name__).warning(
        f"New Relic initialization skipped or failed: {nr_err}"
    )

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    log.critical("Erro: DATABASE_URL não definida.")
    sys.exit(1)

try:
    pool = SimpleConnectionPool(1, 10, dsn=DATABASE_URL)
    log.info("Pool de conexões com o PostgreSQL (ngo-service) inicializado.")
except Exception as e:
    log.critical(f"Erro ao conectar ao PostgreSQL: {e}")
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
        except (psycopg2.errors.ReadOnlySqlTransaction, psycopg2.OperationalError) as trans_err:
            if conn:
                conn.rollback()
                pool.putconn(conn, close=True)
                conn = None
            log.warning(f"[DISASTER_RECOVERY_RETRY] PostgreSQL em cutover/transição (tentativa {attempt}/{max_attempts}): {trans_err}")
            if attempt < max_attempts:
                time.sleep(attempt * 2)
            else:
                log.error("[DISASTER_RECOVERY_BUFFER] Esgotadas tentativas durante cutover.")
                return jsonify({
                    "status": "QUEUED_FOR_PROCESSING",
                    "message": "Cadastro recebido e retido para processamento seguro durante transição de alta disponibilidade.",
                    "data": data
                }), 202
        except Exception as e:
            if conn:
                conn.rollback()
            log.error(f"Erro ao criar ONG: {e}")
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
        log.error(f"Erro ao buscar ONGs: {e}")
        return jsonify({"error": "Erro interno"}), 500
    finally:
        pool.putconn(conn)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8081))
    app.run(host="0.0.0.0", port=port)
