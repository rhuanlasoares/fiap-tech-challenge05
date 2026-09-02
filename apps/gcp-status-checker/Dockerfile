# =========================================================================
# Estagio 1: Builder
# =========================================================================
FROM python:3.12.14-alpine3.24 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =========================================================================
# Estagio 2: Runtime Distroless Non-Root
# =========================================================================
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=nonroot:nonroot main.py .

ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages:/usr/local/lib/python3.11/site-packages:/usr/local/lib/python3.12/dist-packages:/usr/local/lib/python3.11/dist-packages \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER nonroot:nonroot

ENTRYPOINT ["/usr/bin/python3", "main.py"]
