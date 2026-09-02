# =========================================================================
# Estagio 1: Builder (Instalacao limpa de dependencias em prefixo isolado)
# =========================================================================
FROM python:3.12.14-alpine3.24 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =========================================================================
# Estagio 2: Runtime Distroless Non-Root (SEM SHELL, SEM GERENCIADOR, ZERO CVEs)
# =========================================================================
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

# Copia pacotes compilados do builder
COPY --from=builder /install /usr/local

# Copia codigo da aplicacao
COPY --chown=nonroot:nonroot app.py .
COPY --chown=nonroot:nonroot db/ ./db/

ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages:/usr/local/lib/python3.11/site-packages:/usr/local/lib/python3.12/dist-packages:/usr/local/lib/python3.11/dist-packages \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Usuario nativo nonroot do Distroless (UID 65532)
USER nonroot:nonroot

EXPOSE 8081

# Execucao direta do entrypoint via interpretador Python sem intermediacao de shell
ENTRYPOINT ["/usr/bin/python3", "-m", "gunicorn", "--bind", "0.0.0.0:8081", "app:app"]
