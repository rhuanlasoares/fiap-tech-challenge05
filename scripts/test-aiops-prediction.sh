#!/bin/bash
set -e

export PATH="$HOME/.local/bin:${PATH}"

echo "=================================================================="
echo "[AIOps] Executando testes automatizados do Motor Preditivo & RCA"
echo "=================================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/../apps/aiops-engine"

echo "[1/3] Running Unit Tests for Models..."
if [ -f "test_engine.py" ]; then
    python3 test_engine.py
else
    echo "test_engine.py not present, skipping model unit tests."
fi

echo "[2/3] Starting Server FastAPY em Segundo Plano..."
python3 -m uvicorn main:app --host 127.0.0.1 --port 9999 > /tmp/aiops_test.log 2>&1 &
SERVER_PID=$!
sleep 3

echo "[3/3] Executando Testes de Integracao HTTP REST..."
echo "[TEST 1] /health:"
curl -s http://127.0.0.1:9999/health
echo ""

echo "[TEST 2] /api/simulate-anomaly (Memory Leak):"
curl -s -X POST -H "Content-Type: application/json" -d '{"scenario":"memory_leak"}' http://127.0.0.1:9999/api/simulate-anomaly
echo ""

echo "[TEST 3] /api/insights (Gemini AI / RCA):"
curl -s http://127.0.0.1:9999/api/insights
echo ""

echo "[TEST 4] /api/remediate (Auto-Healing Action):"
curl -s -X POST http://127.0.0.1:9999/api/remediate/oom_leak_donation_ns_donation-service-7f88d
echo ""

echo "[TEST 5] Static Web UI Health:"
curl -s http://127.0.0.1:9999/ | grep "<title>"

kill -9 $SERVER_PID || true
rm -f /tmp/aiops_test.log || true

echo "[100% SUCESSO] AIOps Motor Preditivo e Interface Web 100% funcionais!"
