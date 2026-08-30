# ==========================================================
# Multi-stage Build para AIOps Engine (FastAPI + ML + GenAI)
# ==========================================================

# Estagio 1: Builder
FROM python:3.14.7-alpine3.24 AS builder

WORKDIR /app

# Instala dependencias no ~/.local do usuario sem precisar de compiladores no runtime
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Estagio 2: Runtime de Producao
FROM python:3.14.7-alpine3.24 AS production

# Cria usuario sem privilegios (rootless para seguranca em Kubernetes)
RUN adduser -D -s /bin/sh appuser

WORKDIR /app

# Copia os pacotes Python instalados
COPY --from=builder /root/.local /home/appuser/.local

# Copia o codigo-fonte completo, incluindo modulos core e frontend estatico
COPY --chown=appuser:appuser . .

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

# Health check nativo via endpoint /health do FastAPI
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Executa o servidor ASGI Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]