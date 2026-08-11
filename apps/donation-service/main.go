package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/sqs"
	_ "github.com/jackc/pgx/v4/stdlib"
	"github.com/joho/godotenv"
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
		sess, _ := session.NewSession(&aws.Config{Region: aws.String(region)})
		sqsSvc = sqs.New(sess)
		LogInfo(ctx, "Integração com AWS SQS ativada.")
	}

	app := &App{DB: db, SqsSvc: sqsSvc, SqsQueueURL: queueURL}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", app.HealthHandler)
	mux.HandleFunc("/donation-service/health", app.HealthHandler)
	mux.HandleFunc("/donations", app.DonationHandler)
	mux.HandleFunc("/donation-service/donations", app.DonationHandler)

	handler := HTTPMiddleware(mux)

	LogInfo(ctx, "donation-service rodando na porta "+port)
	log.Fatal(http.ListenAndServe(":"+port, handler))
}

func (a *App) HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"ok","service":"donation-service"}`))
}

func (a *App) DonationHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	ctx := r.Context()

	if r.Method == http.MethodPost {
		var d Donation
		if err := json.NewDecoder(r.Body).Decode(&d); err != nil {
			RecordError(ctx, err, "invalid_payload", "Payload de doação inválido")
			http.Error(w, `{"error":"Payload inválido"}`, http.StatusBadRequest)
			return
		}

		d.Status = "APPROVED" // Simulação de gateway de pagamento

		dbCtx, span := Tracer().Start(ctx, "db.insert_donation",
			oteltrace.WithSpanKind(oteltrace.SpanKindClient),
			oteltrace.WithAttributes(
				attribute.String("db.system", "postgresql"),
				attribute.String("db.statement", "INSERT INTO donations"),
				attribute.Int("ngo_id", d.NgoID),
				attribute.Float64("amount", d.Amount),
			),
		)
		err := a.DB.QueryRowContext(
			dbCtx,
			"INSERT INTO donations (ngo_id, amount, donor_name, status) VALUES ($1, $2, $3, $4) RETURNING id, created_at",
			d.NgoID, d.Amount, d.DonorName, d.Status,
		).Scan(&d.ID, &d.CreatedAt)
		span.End()

		if err != nil {
			RecordError(ctx, err, "db_insert_error", "Erro ao salvar doação no PostgreSQL")
			http.Error(w, `{"error":"Erro interno"}`, http.StatusInternalServerError)
			return
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
		json.NewEncoder(w).Encode(d)
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
		rows, err := a.DB.QueryContext(dbCtx, "SELECT id, ngo_id, amount, donor_name, status, created_at FROM donations ORDER BY id DESC")
		span.End()

		if err != nil {
			RecordError(ctx, err, "db_query_error", "Erro ao buscar doações no PostgreSQL")
			http.Error(w, `{"error":"Erro interno"}`, http.StatusInternalServerError)
			return
		}
		defer rows.Close()

		donations := []Donation{}
		for rows.Next() {
			var d Donation
			if err := rows.Scan(&d.ID, &d.NgoID, &d.Amount, &d.DonorName, &d.Status, &d.CreatedAt); err != nil {
				RecordError(ctx, err, "db_scan_error", "Erro ao ler registro de doação")
				http.Error(w, `{"error":"Erro interno"}`, http.StatusInternalServerError)
				return
			}
			donations = append(donations, d)
		}

		json.NewEncoder(w).Encode(donations)
		return
	}

	RecordError(ctx, nil, "method_not_allowed", "Método não permitido: "+r.Method)
	http.Error(w, `{"error":"Método não permitido"}`, http.StatusMethodNotAllowed)
}

func (a *App) sendNotificationEvent(ctx context.Context, d Donation) {
	sqsCtx, span := Tracer().Start(ctx, "sqs.send_message",
		oteltrace.WithSpanKind(oteltrace.SpanKindProducer),
		oteltrace.WithAttributes(
			attribute.String("messaging.system", "aws_sqs"),
			attribute.String("messaging.destination", a.SqsQueueURL),
			attribute.Int("donation.id", d.ID),
		),
	)
	defer span.End()

	body, err := json.Marshal(d)
	if err != nil {
		RecordError(sqsCtx, err, "sqs_marshal_error", "Falha ao serializar doação para SQS")
		return
	}

	_, err = a.SqsSvc.SendMessageWithContext(sqsCtx, &sqs.SendMessageInput{
		MessageBody: aws.String(string(body)),
		QueueUrl:    aws.String(a.SqsQueueURL),
	})
	if err != nil {
		RecordError(sqsCtx, err, "sqs_send_error", "Falha ao despachar evento SQS")
	} else {
		span.SetStatus(codes.Ok, "Mensagem enviada com sucesso ao SQS")
		LogInfo(sqsCtx, "Evento de doação despachado para SQS", attribute.Int("donation.id", d.ID))
	}
}