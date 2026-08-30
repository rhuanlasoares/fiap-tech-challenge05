FROM python:3.14.7-alpine3.24 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.14.7-alpine3.24 AS production

RUN adduser -D -s /bin/sh appuser

RUN apk update && apk upgrade --no-cache

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser app.py app.py

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8083

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8083/health')" || exit 1

CMD ["newrelic-admin", "run-program", "opentelemetry-instrument", "gunicorn", "--bind", "0.0.0.0:8083", "app:app"]