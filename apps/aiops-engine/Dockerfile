# =========================================================================
# Estagio 1: Builder (Instalacao de pacotes FastAPI, ML e GenAI)
# =========================================================================
FROM python:3.12.14-alpine3.24 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =========================================================================
# Estagio 2: Runtime Distroless Non-Root (FastAPI + Uvicorn)
# =========================================================================
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

# Copia pacotes compilados do builder
COPY --from=builder /install /usr/local

# Copia codigo-fonte completo (core, static, main.py)
COPY --chown=nonroot:nonroot . .

ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages:/usr/local/lib/python3.11/site-packages:/usr/local/lib/python3.12/dist-packages:/usr/local/lib/python3.11/dist-packages \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER nonroot:nonroot

EXPOSE 8000

ENTRYPOINT ["/usr/bin/python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
