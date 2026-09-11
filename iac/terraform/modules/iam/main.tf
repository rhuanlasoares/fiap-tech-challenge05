resource "google_compute_subnetwork_iam_member" "member" {
  for_each   = var.subnets
  project    = var.project_id
  region     = each.value.region
  subnetwork = each.value.name
  role       = "roles/compute.networkUser"
  member     = var.sa_gke_member
}

resource "google_project_iam_member" "sa_cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = var.sa_gke_member
}

resource "google_project_iam_member" "sa_user" {
  project = var.project_id
  role    = "roles/iam.workloadIdentityUser"
  member  = var.sa_gke_member
}

resource "google_project_iam_member" "kubernetes_developer" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = var.sa_gke_member
}

resource "google_artifact_registry_repository_iam_member" "artreg_member" {
  for_each   = var.artreg
  project    = var.project_id
  location   = each.value.region
  repository = each.value.name_artreg
  role       = "roles/artifactregistry.reader"
  member     = var.sa_gke_member
}

resource "google_storage_bucket_iam_member" "bucket_user" {
  for_each = var.buckets
  role     = "roles/storage.objectUser"
  member   = var.sa_gke_member
  bucket   = each.value.bucket_name
}

resource "google_secret_manager_secret_iam_member" "secret_member" {
  for_each  = var.secrets
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = var.sa_gke_member
}

locals {
  namespace_name = {
    ngo-service       = "ngo-ns"
    donation-service  = "donation-ns"
    volunteer-service = "volunteer-ns"
    job-service       = "job-ns"
    argocd            = "argocd"
    loki              = "monitoring-ns"
    velero            = "velero"
    aiops             = "aiops"
  }
}

resource "google_service_account_iam_member" "sa_identity_gke" {
  for_each           = local.namespace_name
  service_account_id = var.sa_gke_name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${each.value}/${var.sa_inside_gke}]"
}

resource "google_service_account_iam_member" "sa_identity_gke_monitoring" {
  service_account_id = var.sa_gke_name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[keda/keda-operator]"
}

resource "google_project_iam_member" "sa_identity_gke_keda" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${var.project_id}.svc.id.goog[keda/keda-operator]"
}

resource "google_project_iam_member" "sa_identity_gke_loki_bucket" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${var.project_id}.svc.id.goog[monitoring-ns/sa-gke]"
}
