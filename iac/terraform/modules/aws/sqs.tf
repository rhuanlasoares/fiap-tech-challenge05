resource "aws_sqs_queue" "toggle_master_analytics" {
  name = "solidary-tech"

  visibility_timeout_seconds = 30
  message_retention_seconds  = 345600
  delay_seconds              = 0
  max_message_size           = 1024
  receive_wait_time_seconds  = 0

  sqs_managed_sse_enabled = true

  tags = {
    ManagedBy = "terraform"
    project   = "solidary-tech"
  }
}

data "aws_caller_identity" "current" {}

resource "aws_sqs_queue_policy" "toggle_master_analytics" {
  queue_url = aws_sqs_queue.toggle_master_analytics.id

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "__default_policy_ID"
    Statement = [
      {
        Sid    = "__owner_statement"
        Effect = "Allow"
        Principal = {
          AWS = data.aws_caller_identity.current.account_id
        }
        Action   = "SQS:*"
        Resource = aws_sqs_queue.toggle_master_analytics.arn
      }
    ]
  })
}