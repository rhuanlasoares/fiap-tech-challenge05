# =========================================================================
# Estagio 1: Builder
# =========================================================================
FROM python:3.12-alpine AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =========================================================================
# Estagio 2: Runtime Hardened Zero-Shell (SEM SHELL, SEM GERENCIADOR, ZERO CVEs)
# =========================================================================
FROM python:3.12-alpine

# 1. Atualiza os pacotes do SO para mitigar CVEs conhecidas
# 2. Cria usuario e grupo restritos sem shell de login (/sbin/nologin)
# 3. Purga completamente gerenciadores de pacotes e interpretadores shell (/bin/sh, /bin/ash, /bin/busybox)
RUN apk update && apk upgrade --no-cache && \
    addgroup -g 10001 -S appgroup && \
    adduser -u 10001 -S appuser -G appgroup -s /sbin/nologin && \
    rm -rf /sbin/apk /etc/apk /lib/apk /usr/share/apk && \
    rm -rf /bin/sh /bin/ash /bin/busybox

WORKDIR /app

# Copia pacotes compilados do builder
COPY --from=builder /install /usr/local

# Copia codigo da aplicacao com ownership restrito
COPY --chown=10001:10001 main.py .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10001:10001

ENTRYPOINT ["python", "main.py"]
