FROM golang:1.25-alpine3.21 AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY --exclude=tests/ . .

RUN CGO_ENABLED=0 GOOS=linux go build -o donation-service

FROM alpine:3.23.3 AS final

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY --from=builder --chown=appuser:appgroup /app/donation-service /app/donation-service

USER appuser

EXPOSE 8082

ENTRYPOINT ["/app/donation-service"]