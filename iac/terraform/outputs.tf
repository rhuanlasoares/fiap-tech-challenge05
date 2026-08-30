output "gke_ip_lb" {
  description = "External IP address allocated for the GCP Load Balancer."
  value       = module.vpc.gke_ip_lb
}

output "sqs" {
  description = "URL of the provisioned AWS SQS queue."
  value       = module.aws.sqs_queue_url
}

output "service_account" {
  description = "Map of Service Account email addresses created."
  value       = module.service_accounts.sa_email
}

output "wifederation_name" {
  description = "Full identifier of the Workload Identity Federation provider."
  value       = module.wifederation.wifederation_name
}
