output "vpc_self_link" {
  value = google_compute_network.vpc_network.self_link
}

output "subnet_self_link" {
  value = google_compute_subnetwork.subnet_gke.self_link
}

output "gke_ip_lb" {
  value = google_compute_global_address.default.self_link
}
