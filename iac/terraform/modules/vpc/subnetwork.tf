resource "google_compute_subnetwork" "subnets" {
  for_each      = var.subnets
  project       = var.project_id
  name          = each.value.name
  region        = each.value.region
  ip_cidr_range = each.value.ip_cidr_range
  network       = google_compute_network.vpc_network.self_link

  secondary_ip_range {
    range_name    = each.value.range_name_pods
    ip_cidr_range = each.value.ip_cidr_range_pods
  }

  secondary_ip_range {
    range_name    = each.value.range_name_services
    ip_cidr_range = each.value.ip_cidr_range_services
  }

  private_ip_google_access = true
}
