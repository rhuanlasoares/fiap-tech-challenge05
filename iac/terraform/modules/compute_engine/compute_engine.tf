resource "google_compute_instance" "default" {
  lifecycle {
    ignore_changes = [
      metadata,
    ]
  }
  project      = var.project_id
  name         = "gce-instance-rhuan"
  machine_type = "e2-medium"
  zone         = "${var.region}-a"

  boot_disk {
    initialize_params {
      image = "ubuntu-minimal-2510-questing-amd64-v20251217"
      labels = {
        project    = "${var.project_id}"
        created_by = "terraform"
      }
    }
  }

  network_interface {
    network            = var.network_self_link
    subnetwork         = var.subnetwork_self_link
    subnetwork_project = var.project_id
  }

  metadata_startup_script = file("${path.module}/startup_script.sh")

  service_account {
    scopes = ["cloud-platform"]
    email  = var.sa_gke_email
  }
}
