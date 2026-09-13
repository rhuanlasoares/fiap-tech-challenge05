# Build multi-stage com imagem final distroless e nonroot
FROM golang:1.26-bookworm AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

# Binario estatico compilado para execucao sem libc e com remocao de simbolos de debug (-w -s)
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/donation-service .

# Imagem final sem shell nem gerenciador de pacotes (Minimizacao de superficie de ataque e Zero CVEs)
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app
COPY --from=builder /app/donation-service /app/donation-service

USER 65532:65532
EXPOSE 8082
ENTRYPOINT ["/app/donation-service"]
