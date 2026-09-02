package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestInitOpenTelemetry(t *testing.T) {
	ctx := context.Background()
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
	t.Setenv("OTEL_EXPORTER_OTLP_INSECURE", "true")
	t.Setenv("OTEL_SERVICE_NAME", "donation-service-test")

	shutdown, err := InitOpenTelemetry(ctx)
	if err != nil {
		t.Fatalf("InitOpenTelemetry failed: %v", err)
	}
	defer func() {
		if err := shutdown(ctx); err != nil {
			t.Logf("Shutdown returned error: %v", err)
		}
	}()

	if Tracer() == nil {
		t.Error("Tracer() returned nil")
	}
}

func TestHTTPMiddleware(t *testing.T) {
	handler := HTTPMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	}))

	req := httptest.NewRequest("GET", "/health", nil)
	rr := httptest.NewRecorder()

	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rr.Code)
	}
}
