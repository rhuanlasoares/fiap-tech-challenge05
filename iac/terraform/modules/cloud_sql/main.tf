resource "google_sql_database_instance" "main" {
  database_version = var.database_version
  name             = var.cloud_sql_instance_name
  project          = var.project_id
  region           = var.region

  settings {
    user_labels       = var.instance_labels
    tier              = var.instance_tier
    edition           = "ENTERPRISE"
    availability_type = "REGIONAL"

    ip_configuration {
      ipv4_enabled       = false
      private_network    = var.vpc_self_link
      allocated_ip_range = var.psa_name
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      binary_log_enabled             = false
      start_time                     = "23:00"
    }

    disk_autoresize = true
    disk_size       = 20
    disk_type       = "PD_SSD"
  }

  deletion_protection = false

  lifecycle {
    ignore_changes = [
      settings[0].maintenance_window,
      settings[0].disk_size
    ]
  }
}

resource "google_sql_database_instance" "replica" {
  count            = var.enable_cross_region_replica ? 1 : 0
  name             = "${var.cloud_sql_instance_name}-replica"
  project          = var.project_id
  region           = var.replica_region
  database_version = var.database_version

  master_instance_name = google_sql_database_instance.main.name

  settings {
    user_labels = merge(var.instance_labels, {
      "sql-replica" = "true"
    })
    edition           = "ENTERPRISE"
    tier              = var.instance_tier
    availability_type = "ZONAL"
    ip_configuration {
      ipv4_enabled       = false
      private_network    = var.vpc_self_link
      allocated_ip_range = var.psa_name
    }
    disk_autoresize = true
    disk_size       = 20
    disk_type       = "PD_SSD"
  }
  deletion_protection = false

  lifecycle {
    ignore_changes = [
      master_instance_name,
      settings[0].maintenance_window,
      settings[0].disk_size
    ]
  }
}

resource "google_sql_database" "database" {
  project         = var.project_id
  name            = var.database_name
  instance        = google_sql_database_instance.main.name
  deletion_policy = "ABANDON"
}

resource "google_sql_user" "iam_user" {
  name     = var.username
  instance = google_sql_database_instance.main.name
  project  = var.project_id
  password = var.password.secret_data

  deletion_policy = "ABANDON"
}
