resource "google_container_cluster" "gke_actions" {
  count = var.should_be_create ? 1 : 0

  name     = var.gke_cluster_name
  location = var.region
  project  = var.project_id

  resource_labels = var.gke_resource_labels

  initial_node_count       = 1
  remove_default_node_pool = true
  deletion_protection      = false

  default_max_pods_per_node = 30

  gateway_api_config {
    channel = "CHANNEL_STANDARD"
  }

  network    = var.vpc_self_link
  subnetwork = var.subnet_self_link

  private_cluster_config {
    enable_private_nodes        = true
    private_endpoint_subnetwork = var.subnet_self_link
  }

  addons_config {
    horizontal_pod_autoscaling {
      disabled = false
    }
    http_load_balancing {
      disabled = false
    }
    gcp_filestore_csi_driver_config {
      enabled = false
    }
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.range_name_pods
    services_secondary_range_name = var.range_name_services
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  secret_manager_config {
    enabled = true
  }

  node_pool_defaults {
    node_config_defaults {
      gcfs_config {
        enabled = true
      }
    }
  }
}

resource "google_container_node_pool" "spot_nodes" {
  count = var.should_be_create ? 1 : 0

  name     = "${var.gke_cluster_name}-spot-pool"
  location = var.region
  cluster  = google_container_cluster.gke_actions[0].name
  project  = var.project_id

  initial_node_count = var.initial_node_count

  autoscaling {
    min_node_count = var.min_node_count
    max_node_count = var.max_node_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.machine_type
    spot         = true

    disk_size_gb = 50
    disk_type    = "pd-standard"
    image_type   = "COS_CONTAINERD"

    service_account = var.sa_gke_member
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    gcfs_config {
      enabled = true
    }

    labels = merge(var.gke_resource_labels, {
      "node_type" = "spot"
    })

    tags = ["gke-node", "${var.gke_cluster_name}-node"]
  }
}