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
