# output "cloudsql_private_ips" {
#   description = "Private IPs of all Cloud SQL instances"
#   value = {
#     for name, mod in module.cloud_sql :
#     name => mod.private_ip
#   }
# }

# output "cloudsql_connection_names" {
#   description = "Connection names of all Cloud SQL instances"
#   value = {
#     for name, mod in module.cloud_sql :
#     name => mod.connection_name
#   }
# }

# output "artreg_uri" {
#   value = module.artifact_registry.artreg_uri
# }

# output "redis_private_ip" {
#   value = module.redis.redis_private_ip
# }

output "gke_ip_lb" {
  value = module.vpc.gke_ip_lb
}

output "sqs" {
  value = module.aws.sqs_queue_url
}

output "service_account" {
  value = module.service_accounts.sa_email
}

output "wifederation_name" {
  value = module.wifederation.wifederation_name
}