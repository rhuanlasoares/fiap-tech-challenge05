resource "google_compute_subnetwork" "subnet_gke" {
  project       = var.project_id
  name          = var.subnet_name
  ip_cidr_range = var.ip_cidr_range_subnet_gke
  region        = var.region
  network       = google_compute_network.vpc_network.self_link
  secondary_ip_range {
    range_name    = var.range_name_pods
    ip_cidr_range = var.ip_cidr_range_pods
  }
  secondary_ip_range {
    range_name    = var.range_name_services
    ip_cidr_range = var.ip_cidr_range_services
  }

  private_ip_google_access = true
}
