output "sqs_queue_url" {
  value = aws_sqs_queue.toggle_master_analytics.url
}