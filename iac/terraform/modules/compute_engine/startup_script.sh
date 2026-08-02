#!/bin/bash
set -e

echo "[INFO] Iniciando startup script..."

export DEBIAN_FRONTEND=noninteractive

echo "[INFO] Atualizando repositórios..."
apt-get update -y

echo "[INFO] Instalando PostgreSQL e nano..."
apt-get install -y \
  postgresql \
  postgresql-client \
  nano \
  telnet

echo "[INFO] Verificando versões instaladas..."
psql --version || true
nano --version || true

echo "[INFO] Startup script finalizado com sucesso!"
