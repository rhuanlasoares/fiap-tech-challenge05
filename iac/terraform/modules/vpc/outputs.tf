output "vpc_self_link" {
  value = google_compute_network.vpc_network.self_link
}

output "subnet_self_link" {
  value = { for k, v in google_compute_subnetwork.subnets : k => v.self_link }
}

output "gke_ip_lb" {
  value = google_compute_global_address.default.self_link
}
