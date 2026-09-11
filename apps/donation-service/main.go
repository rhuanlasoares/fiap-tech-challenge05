package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/sqs"
	_ "github.com/jackc/pgx/v4/stdlib"
	"github.com/joho/godotenv"
	"github.com/newrelic/go-agent/v3/newrelic"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	oteltrace "go.opentelemetry.io/otel/trace"
)

type Donation struct {
	ID        int       `json:"id"`
	NgoID     int       `json:"ngo_id"`
	Amount    float64   `json:"amount"`
	DonorName string    `json:"donor_name"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type App struct {
	DB          *sql.DB
	SqsSvc      *sqs.SQS
	SqsQueueURL string
	NrApp       *newrelic.Application
}

func main() {
	_ = godotenv.Load()

	ctx := context.Background()
	shutdownOTEL, err := InitOpenTelemetry(ctx)
	if err != nil {
		log.Printf("Warning: Falha ao inicializar OpenTelemetry: %v", err)
	} else {
		defer func() {
			shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			if err := shutdownOTEL(shutdownCtx); err != nil {
				log.Printf("Erro ao finalizar OpenTelemetry: %v", err)
			}
		}()
	}

	// Inicialização do New Relic com suporte a AI Monitoring (AIM)
	var nrApp *newrelic.Application
	licenseKey := os.Getenv("NEW_RELIC_LICENSE_KEY")
	appName := os.Getenv("NEW_RELIC_APP_NAME")
	if appName == "" {
		appName = "donation-service"
	}

	if licenseKey != "" {
		var nrErr error
		nrApp, nrErr = newrelic.NewApplication(
			newrelic.ConfigAppName(appName),
			newrelic.ConfigLicense(licenseKey),
			newrelic.ConfigAIMonitoringEnabled(true),
			newrelic.ConfigAIMonitoringRecordContentEnabled(true),
			newrelic.ConfigAIMonitoringStreamingEnabled(true),
			newrelic.ConfigAppLogForwardingEnabled(true),
			newrelic.ConfigDistributedTracerEnabled(true),
		)
		if nrErr != nil {
			log.Printf("[WARN] Falha ao inicializar New Relic: %v", nrErr)
		} else {
			LogInfo(ctx, "New Relic Application inicializado com suporte a AI Monitoring.")
			defer nrApp.Shutdown(5 * time.Second)
		}
	} else {
		log.Println("[INFO] NEW_RELIC_LICENSE_KEY não informada. Executando sem New Relic.")
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8082"
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("DATABASE_URL é obrigatória")
	}

	db, err := sql.Open("pgx", dbURL)
	if err != nil {
		RecordError(ctx, err, "db_connection_error", "Erro ao abrir conexão com o banco de dados")
		log.Fatalf("Erro ao abrir conexão com o banco de dados: %v", err)
	}

	var pingErr error
	for attempts := 1; attempts <= 10; attempts++ {
		if pingErr = db.Ping(); pingErr == nil {
			break
		}
		log.Printf("[INFO] Aguardando banco de dados (tentativa %d/10): %v", attempts, pingErr)
		time.Sleep(1 * time.Second)
	}
	if pingErr != nil {
		RecordError(ctx, pingErr, "db_connection_error", "Erro ao conectar ao banco de dados")
		log.Fatalf("Erro ao conectar ao banco de dados: %v", pingErr)
	}
	LogInfo(ctx, "Conectado ao PostgreSQL (donation-service).")

	var sqsSvc *sqs.SQS
	queueURL := os.Getenv("AWS_SQS_URL")
	region := os.Getenv("AWS_REGION")
	if queueURL != "" && region != "" {
		awsCfg := &aws.Config{Region: aws.String(region)}
		if ep := os.Getenv("AWS_ENDPOINT_URL"); ep != "" {
			awsCfg.Endpoint = aws.String(ep)
		}
		sess, _ := session.NewSession(awsCfg)
		sqsSvc = sqs.New(sess)
		LogInfo(ctx, "Integração com AWS SQS ativada.")
	}

	app := &App{
		DB:          db,
		SqsSvc:      sqsSvc,
		SqsQueueURL: queueURL,
		NrApp:       nrApp,
	}

	mux := http.NewServeMux()

	// Registro de rotas com instrumentação do New Relic
	registerRoute := func(pattern string, handlerFunc http.HandlerFunc) {
		if nrApp != nil {
			mux.HandleFunc(newrelic.WrapHandleFunc(nrApp, pattern, handlerFunc))
		} else {
			mux.HandleFunc(pattern, handlerFunc)
		}
	}

	registerRoute("/health", app.HealthHandler)
	registerRoute("/donation-service/health", app.HealthHandler)
	registerRoute("/donations", app.DonationHandler)
	registerRoute("/donation-service/donations", app.DonationHandler)

	handler := HTTPMiddleware(mux)
	go app.startSQSBufferDrainWorker(ctx)

	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      handler,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		LogInfo(ctx, "donation-service rodando na porta "+port)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("Falha no servidor HTTP: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	LogInfo(ctx, "Recebido sinal de encerramento. Finalizando servidor graciosamente...")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Erro ao encerrar servidor HTTP: %v", err)
	}
	if db != nil {
		_ = db.Close()
	}
	LogInfo(ctx, "Servico finalizado com sucesso.")
}

func (a *App) HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok","service":"donation-service"}`))
}

func (a *App) DonationHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	ctx := r.Context()
	txn := newrelic.FromContext(ctx)

	if r.Method == http.MethodPost {
		var d Donation
		if err := json.NewDecoder(r.Body).Decode(&d); err != nil {
			if txn != nil {
				txn.NoticeError(err)
			}
			RecordError(ctx, err, "invalid_payload", "Payload de doação inválido")
			http.Error(w, `{"error":"Payload inválido"}`, http.StatusBadRequest)
			return
		}

		d.Status = "APPROVED" // Simulação de gateway de pagamento

		if txn != nil {
			txn.AddAttribute("donation.ngo_id", d.NgoID)
			txn.AddAttribute("donation.amount", d.Amount)
			txn.AddAttribute("donation.donor_name", d.DonorName)
		}

		dbCtx, span := Tracer().Start(ctx, "db.insert_donation",
			oteltrace.WithSpanKind(oteltrace.SpanKindClient),
			oteltrace.WithAttributes(
				attribute.String("db.system", "postgresql"),
				attribute.String("db.statement", "INSERT INTO donations"),
				attribute.Int("ngo_id", d.NgoID),
				attribute.Float64("amount", d.Amount),
			),
		)

		var dbSegment *newrelic.DatastoreSegment
		if txn != nil {
			dbSegment = &newrelic.DatastoreSegment{
				StartTime:          txn.StartSegmentNow(),
				Product:            newrelic.DatastorePostgres,
				Collection:         "donations",
				Operation:          "INSERT",
				ParameterizedQuery: "INSERT INTO donations (ngo_id, amount, donor_name, status) VALUES ($1, $2, $3, $4) RETURNING id, created_at",
			}
		}

		err := a.DB.QueryRowContext(
			dbCtx,
			"INSERT INTO donations (ngo_id, amount, donor_name, status) VALUES ($1, $2, $3, $4) RETURNING id, created_at",
			d.NgoID, d.Amount, d.DonorName, d.Status,
		).Scan(&d.ID, &d.CreatedAt)

		if dbSegment != nil {
			dbSegment.End()
		}
		span.End()

		if err != nil {
			if txn != nil {
				txn.NoticeError(err)
			}
			RecordError(ctx, err, "db_insert_error", "Erro ao salvar doação no PostgreSQL")

			// SRE Buffer Mode: Se o banco estiver indisponível ou em failover/read-only,
			// armazena a doação no AWS SQS com HTTP 202 Accepted para Zero Data Loss (RPO = 0).
			if a.SqsSvc != nil {
				d.Status = "PENDING_BUFFERED"
				d.CreatedAt = time.Now().UTC()
				d.ID = int(time.Now().UnixNano() / 1e6)

				LogInfo(ctx, "[DISASTER_RECOVERY_BUFFER] PostgreSQL em transicao. Armazenando doacao no AWS SQS...",
					attribute.Int("donation.id", d.ID),
					attribute.Int("donation.ngo_id", d.NgoID),
					attribute.Float64("donation.amount", d.Amount),
				)

				a.sendNotificationEvent(context.WithoutCancel(ctx), d)

				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusAccepted)
				_ = json.NewEncoder(w).Encode(map[string]interface{}{
					"status":   "QUEUED_FOR_PROCESSING",
					"message":  "Doacao recebida com sucesso e armazenada com seguranca em buffer de alta disponibilidade.",
					"donation": d,
				})
				return
			}

			http.Error(w, `{"error":"Erro interno"}`, http.StatusInternalServerError)
			return
		}

		if txn != nil {
			txn.AddAttribute("donation.id", d.ID)
		}

		if donationsCreated != nil {
			donationsCreated.Add(ctx, 1)
		}
		if donationAmount != nil {
			donationAmount.Add(ctx, d.Amount)
		}

		LogInfo(ctx, "Doação registrada com sucesso",
			attribute.Int("donation.id", d.ID),
			attribute.Int("donation.ngo_id", d.NgoID),
			attribute.Float64("donation.amount", d.Amount),
		)

		if a.SqsSvc != nil {
			go a.sendNotificationEvent(context.WithoutCancel(ctx), d)
		}

		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(d)
		return
	}

	if r.Method == http.MethodGet {
		dbCtx, span := Tracer().Start(ctx, "db.select_donations",
			oteltrace.WithSpanKind(oteltrace.SpanKindClient),
			oteltrace.WithAttributes(
				attribute.String("db.system", "postgresql"),
				attribute.String("db.statement", "SELECT FROM donations"),
			),
		)

		var dbSegment *newrelic.DatastoreSegment
		if txn != nil {
			dbSegment = &newrelic.DatastoreSegment{
				StartTime:          txn.StartSegmentNow(),
				Product:            newrelic.DatastorePostgres,
				Collection:         "donations",
				Operation:          "SELECT",
				ParameterizedQuery: "SELECT id, ngo_id, amount, donor_name, status, created_at FROM donations ORDER BY id DESC",
			}
		}

		rows, err := a.DB.QueryContext(dbCtx, "SELECT id, ngo_id, amount, donor_name, status, created_at FROM donations ORDER BY id DESC")

		if dbSegment != nil {
			dbSegment.End()
		}
		span.End()

		if err != nil {
			if txn != nil {
				txn.NoticeError(err)
			}
			RecordError(ctx, err, "db_query_error", "Erro ao buscar doações no PostgreSQL")
			http.Error(w, `{"error":"Erro interno"}`, http.StatusInternalServerError)
			return
		}
		defer func() {
			_ = rows.Close()
		}()

		donations := []Donation{}
		for rows.Next() {
			var d Donation
			if err := rows.Scan(&d.ID, &d.NgoID, &d.Amount, &d.DonorName, &d.Status, &d.CreatedAt); err != nil {
				if txn != nil {
					txn.NoticeError(err)
				}
				RecordError(ctx, err, "db_scan_error", "Erro ao ler registro de doação")
				http.Error(w, `{"error":"Erro interno"}`, http.StatusInternalServerError)
				return
			}
			donations = append(donations, d)
		}

		if err := rows.Err(); err != nil {
			if txn != nil {
				txn.NoticeError(err)
			}
			RecordError(ctx, err, "db_rows_error", "Erro na iteracao dos registros de doacao")
			http.Error(w, `{"error":"Erro interno"}`, http.StatusInternalServerError)
			return
		}

		_ = json.NewEncoder(w).Encode(donations)
		return
	}

	RecordError(ctx, nil, "method_not_allowed", "Método não permitido: "+r.Method)
	http.Error(w, `{"error":"Método não permitido"}`, http.StatusMethodNotAllowed)
}

func (a *App) sendNotificationEvent(ctx context.Context, d Donation) {
	txn := newrelic.FromContext(ctx)

	sqsCtx, span := Tracer().Start(ctx, "sqs.send_message",
		oteltrace.WithSpanKind(oteltrace.SpanKindProducer),
		oteltrace.WithAttributes(
			attribute.String("messaging.system", "aws_sqs"),
			attribute.String("messaging.destination", a.SqsQueueURL),
			attribute.Int("donation.id", d.ID),
		),
	)
	defer span.End()

	var msgSegment *newrelic.MessageProducerSegment
	if txn != nil {
		msgSegment = &newrelic.MessageProducerSegment{
			StartTime:            txn.StartSegmentNow(),
			DestinationType:      newrelic.MessageQueue,
			DestinationName:      a.SqsQueueURL,
			DestinationTemporary: false,
		}
	}

	body, err := json.Marshal(d)
	if err != nil {
		if txn != nil {
			txn.NoticeError(err)
		}
		RecordError(sqsCtx, err, "sqs_marshal_error", "Falha ao serializar doação para SQS")
		return
	}

	_, err = a.SqsSvc.SendMessageWithContext(sqsCtx, &sqs.SendMessageInput{
		MessageBody: aws.String(string(body)),
		QueueUrl:    aws.String(a.SqsQueueURL),
	})

	if msgSegment != nil {
		msgSegment.End()
	}

	if err != nil {
		if txn != nil {
			txn.NoticeError(err)
		}
		RecordError(sqsCtx, err, "sqs_send_error", "Falha ao despachar evento SQS")
	} else {
		span.SetStatus(codes.Ok, "Mensagem enviada com sucesso ao SQS")
		LogInfo(sqsCtx, "Evento de doação despachado para SQS", attribute.Int("donation.id", d.ID))
	}
}

func (a *App) startSQSBufferDrainWorker(ctx context.Context) {
	if a.SqsSvc == nil || a.SqsQueueURL == "" || a.DB == nil {
		return
	}
	LogInfo(ctx, "Iniciando worker de drenagem de contingencia SQS...")
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := a.DB.PingContext(ctx); err != nil {
				continue
			}

			out, err := a.SqsSvc.ReceiveMessageWithContext(ctx, &sqs.ReceiveMessageInput{
				QueueUrl:            aws.String(a.SqsQueueURL),
				MaxNumberOfMessages: aws.Int64(10),
				WaitTimeSeconds:     aws.Int64(2),
			})
			if err != nil || len(out.Messages) == 0 {
				continue
			}

			for _, msg := range out.Messages {
				if msg.Body == nil {
					continue
				}
				var d Donation
				if err := json.Unmarshal([]byte(*msg.Body), &d); err != nil {
					continue
				}
				if d.Status == "PENDING_BUFFERED" {
					var insertedID int
					var insertedAt time.Time
					err := a.DB.QueryRowContext(
						ctx,
						"INSERT INTO donations (ngo_id, amount, donor_name, status) VALUES ($1, $2, $3, 'APPROVED') RETURNING id, created_at",
						d.NgoID, d.Amount, d.DonorName,
					).Scan(&insertedID, &insertedAt)

					if err == nil {
						LogInfo(ctx, "[DISASTER_RECOVERY_DRAINED] Doacao recuperada do SQS e gravada no PostgreSQL com sucesso",
							attribute.Int("donation.id", insertedID),
							attribute.Int("donation.ngo_id", d.NgoID),
						)
						_, _ = a.SqsSvc.DeleteMessageWithContext(ctx, &sqs.DeleteMessageInput{
							QueueUrl:      aws.String(a.SqsQueueURL),
							ReceiptHandle: msg.ReceiptHandle,
						})
					}
				}
			}
		}
	}
}
