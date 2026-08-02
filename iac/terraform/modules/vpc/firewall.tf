# resource "google_compute_firewall" "allow_ssh" {
#   name    = "allow-ssh"
#   network = google_compute_network.vpc_network.name
#   project = var.project_id

#   direction = "INGRESS"
#   priority  = 10

#   allow {
#     protocol = "tcp"
#     ports    = ["22"]
#   }

#   source_ranges = ["35.235.240.0/20"]

#   target_service_accounts = [var.sa_gke_email]
# }

resource "google_compute_firewall" "allow_health_check" {
  name    = "allow-health-check-gke"
  network = "projects/${var.project_id}/global/networks/${var.vpc_name}"
  project = var.project_id
  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }

  allow {
    protocol = "tcp"
    ports    = ["30000-32767"]
  }
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]

  direction = "INGRESS"

  target_service_accounts = [var.sa_gke_email]
}
