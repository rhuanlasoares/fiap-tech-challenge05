output "private_ip" {
  description = "Private IP of the Cloud SQL instance"
  value       = google_sql_database_instance.main.private_ip_address
}

output "connection_name" {
  description = "Connection name of the Cloud SQL instance"
  value       = google_sql_database_instance.main.connection_name
}
