package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	otelLog "go.opentelemetry.io/otel/log"
	"go.opentelemetry.io/otel/log/global"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/propagation"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	oteltrace "go.opentelemetry.io/otel/trace"
)

type otelLogWriter struct {
	logger otelLog.Logger
}

func (w *otelLogWriter) Write(p []byte) (n int, err error) {
	msg := strings.TrimSpace(string(p))
	if msg != "" {
		var rec otelLog.Record
		rec.SetBody(otelLog.StringValue(msg))
		w.logger.Emit(context.Background(), rec)
	}
	return len(p), nil
}

var (
	tracer             oteltrace.Tracer
	meter              metric.Meter
	logger             otelLog.Logger
	requestsTotal      metric.Int64Counter
	requestDuration    metric.Float64Histogram
	httpServerDuration metric.Float64Histogram
	donationsCreated   metric.Int64Counter
	donationAmount     metric.Float64Counter
	donationErrors     metric.Int64Counter
)

const instrumentationScope = "donation-service"

// InitOpenTelemetry initializes OTLP exporters for traces, metrics, and logs.
// It returns a shutdown function to flush and release resources on service shutdown.
func InitOpenTelemetry(ctx context.Context) (func(context.Context) error, error) {
	serviceName := os.Getenv("OTEL_SERVICE_NAME")
	if serviceName == "" {
		serviceName = "donation-service"
	}

	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "opentelemetry-collector.monitoring-ns.svc.cluster.local:4317"
	} else {
		endpoint = strings.TrimPrefix(endpoint, "http://")
		endpoint = strings.TrimPrefix(endpoint, "https://")
	}

	insecure := os.Getenv("OTEL_EXPORTER_OTLP_INSECURE") != "false"

	res, err := createResource(ctx, serviceName)
	if err != nil {
		return nil, fmt.Errorf("failed to create OTEL resource: %w", err)
	}

	// 1. Traces Setup
	traceOpts := []otlptracegrpc.Option{otlptracegrpc.WithEndpoint(endpoint)}
	if insecure {
		traceOpts = append(traceOpts, otlptracegrpc.WithInsecure())
	}
	traceExporter, err := otlptracegrpc.New(ctx, traceOpts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create trace exporter: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	tracer = tp.Tracer(instrumentationScope)

	// 2. Metrics Setup
	metricOpts := []otlpmetricgrpc.Option{otlpmetricgrpc.WithEndpoint(endpoint)}
	if insecure {
		metricOpts = append(metricOpts, otlpmetricgrpc.WithInsecure())
	}
	metricExporter, err := otlpmetricgrpc.New(ctx, metricOpts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create metric exporter: %w", err)
	}

	mp := sdkmetric.NewMeterProvider(
		sdkmetric.WithResource(res),
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter, sdkmetric.WithInterval(5*time.Second))),
	)
	otel.SetMeterProvider(mp)
	meter = mp.Meter(instrumentationScope)

	if err := initMetricInstruments(); err != nil {
		return nil, fmt.Errorf("failed to initialize metric instruments: %w", err)
	}

	// 3. Logs Setup
	logOpts := []otlploggrpc.Option{otlploggrpc.WithEndpoint(endpoint)}
	if insecure {
		logOpts = append(logOpts, otlploggrpc.WithInsecure())
	}
	logExporter, err := otlploggrpc.New(ctx, logOpts...)
	if err != nil {
		return nil, fmt.Errorf("failed to create log exporter: %w", err)
	}

	lp := sdklog.NewLoggerProvider(
		sdklog.WithResource(res),
		sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
	)
	global.SetLoggerProvider(lp)
	logger = global.GetLoggerProvider().Logger(instrumentationScope)
	log.SetOutput(io.MultiWriter(os.Stdout, &otelLogWriter{logger: logger}))

	log.Printf("OpenTelemetry initialized for service '%s' pointing to collector '%s' (insecure: %v)", serviceName, endpoint, insecure)

	// Shutdown callback
	shutdown := func(shutdownCtx context.Context) error {
		var errs []error
		if err := tp.Shutdown(shutdownCtx); err != nil {
			errs = append(errs, fmt.Errorf("tracer provider shutdown error: %w", err))
		}
		if err := mp.Shutdown(shutdownCtx); err != nil {
			errs = append(errs, fmt.Errorf("meter provider shutdown error: %w", err))
		}
		if err := lp.Shutdown(shutdownCtx); err != nil {
			errs = append(errs, fmt.Errorf("logger provider shutdown error: %w", err))
		}
		return errors.Join(errs...)
	}

	return shutdown, nil
}

func createResource(ctx context.Context, serviceName string) (*sdkresource.Resource, error) {
	attrs := []attribute.KeyValue{
		semconv.ServiceNameKey.String(serviceName),
	}

	// Parse OTEL_RESOURCE_ATTRIBUTES if present (key1=val1,key2=val2)
	envAttrs := os.Getenv("OTEL_RESOURCE_ATTRIBUTES")
	if envAttrs != "" {
		for _, pair := range strings.Split(envAttrs, ",") {
			kv := strings.SplitN(pair, "=", 2)
			if len(kv) == 2 {
				k := strings.TrimSpace(kv[0])
				v := strings.TrimSpace(kv[1])
				if k != "" && v != "" {
					attrs = append(attrs, attribute.String(k, v))
				}
			}
		}
	}

	return sdkresource.New(
		ctx,
		sdkresource.WithAttributes(attrs...),
		sdkresource.WithFromEnv(),
		sdkresource.WithTelemetrySDK(),
	)
}

func initMetricInstruments() error {
	var err error
	requestsTotal, err = meter.Int64Counter(
		"http_requests_total",
		metric.WithDescription("Total number of HTTP requests processed"),
	)
	if err != nil {
		return err
	}

	requestDuration, err = meter.Float64Histogram(
		"http_request_duration_seconds",
		metric.WithDescription("HTTP request latency in seconds"),
		metric.WithUnit("s"),
	)
	if err != nil {
		return err
	}

	httpServerDuration, err = meter.Float64Histogram(
		"http.server.request.duration",
		metric.WithDescription("Duration of HTTP server requests"),
		metric.WithUnit("s"),
	)
	if err != nil {
		return err
	}

	donationsCreated, err = meter.Int64Counter(
		"donations_created_total",
		metric.WithDescription("Total number of donations successfully created"),
	)
	if err != nil {
		return err
	}

	donationAmount, err = meter.Float64Counter(
		"donation_amount_total",
		metric.WithDescription("Total monetary value of donations created"),
	)
	if err != nil {
		return err
	}

	donationErrors, err = meter.Int64Counter(
		"donation_errors_total",
		metric.WithDescription("Total number of errors encountered"),
	)
	if err != nil {
		return err
	}

	return nil
}

// Tracer returns the global tracer instance
func Tracer() oteltrace.Tracer {
	if tracer == nil {
		return otel.Tracer(instrumentationScope)
	}
	return tracer
}

// RecordError records an error on the active span, increments error metrics, and emits an OTEL log.
func RecordError(ctx context.Context, err error, errorType string, msg string) {
	if err == nil {
		return
	}

	fullMsg := fmt.Sprintf("%s: %v", msg, err)

	// Span error recording
	span := oteltrace.SpanFromContext(ctx)
	if span.IsRecording() {
		span.RecordError(err)
		span.SetStatus(codes.Error, fullMsg)
	}

	// Metric counter increment
	if donationErrors != nil {
		donationErrors.Add(ctx, 1, metric.WithAttributes(
			attribute.String("error_type", errorType),
		))
	}

	// OTEL Log emission & stdout fallback log
	emitLog(ctx, otelLog.SeverityError, fullMsg, attribute.String("error.type", errorType))
	log.Printf("[ERROR] [%s] %s", errorType, fullMsg)
}

// LogInfo records an info log entry with active trace context correlation.
func LogInfo(ctx context.Context, msg string, attrs ...attribute.KeyValue) {
	emitLog(ctx, otelLog.SeverityInfo, msg, attrs...)
	log.Printf("[INFO] %s", msg)
}

func emitLog(ctx context.Context, severity otelLog.Severity, body string, attrs ...attribute.KeyValue) {
	if logger == nil {
		return
	}

	var rec otelLog.Record
	rec.SetTimestamp(time.Now())
	rec.SetSeverity(severity)
	rec.SetBody(otelLog.StringValue(body))

	span := oteltrace.SpanFromContext(ctx)
	if span.SpanContext().IsValid() {
		attrs = append(attrs,
			attribute.String("trace_id", span.SpanContext().TraceID().String()),
			attribute.String("span_id", span.SpanContext().SpanID().String()),
		)
	}

	otAttrs := make([]otelLog.KeyValue, len(attrs))
	for i, a := range attrs {
		otAttrs[i] = otelLog.String(string(a.Key), a.Value.AsString())
	}
	rec.AddAttributes(otAttrs...)

	logger.Emit(ctx, rec)
}

// responseWriterInterceptor wraps http.ResponseWriter to capture status code
type responseWriterInterceptor struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriterInterceptor) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// HTTPMiddleware instruments incoming HTTP requests with tracing context, latency histograms, and request counters.
func HTTPMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))

		route := r.URL.Path
		spanName := fmt.Sprintf("%s %s", r.Method, route)

		ctx, span := Tracer().Start(ctx, spanName,
			oteltrace.WithSpanKind(oteltrace.SpanKindServer),
			oteltrace.WithAttributes(
				attribute.String("http.method", r.Method),
				attribute.String("http.request.method", r.Method),
				attribute.String("http.target", r.URL.Path),
				attribute.String("url.path", r.URL.Path),
				attribute.String("http.route", route),
				attribute.String("http.scheme", "http"),
			),
		)
		defer span.End()

		r = r.WithContext(ctx)

		rw := &responseWriterInterceptor{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(rw, r)

		duration := time.Since(start).Seconds()
		statusStr := strconv.Itoa(rw.statusCode)

		span.SetAttributes(
			attribute.Int("http.status_code", rw.statusCode),
			attribute.Int("http.response.status_code", rw.statusCode),
		)
		if rw.statusCode >= 400 {
			span.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", rw.statusCode))
		} else {
			span.SetStatus(codes.Ok, "")
		}

		attrs := metric.WithAttributes(
			attribute.String("http.method", r.Method),
			attribute.String("http.request.method", r.Method),
			attribute.String("http.route", route),
			attribute.String("http.status_code", statusStr),
			attribute.String("http.response.status_code", statusStr),
		)

		if requestsTotal != nil {
			requestsTotal.Add(ctx, 1, attrs)
		}
		if requestDuration != nil {
			requestDuration.Record(ctx, duration, attrs)
		}
		if httpServerDuration != nil {
			httpServerDuration.Record(ctx, duration, attrs)
		}
	})
}

