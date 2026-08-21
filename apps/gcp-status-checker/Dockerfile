FROM python:3.14.7-alpine3.24 AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.14.7-alpine3.24 AS production

RUN adduser -D -s /bin/sh appuser

RUN apk update && apk upgrade

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser main.py main.py

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

CMD ["python", "main.py"]