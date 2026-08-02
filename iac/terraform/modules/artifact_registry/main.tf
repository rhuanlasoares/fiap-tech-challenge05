resource "google_artifact_registry_repository" "artreg" {

  project       = var.project_id
  location      = var.region
  repository_id = var.name_artreg
  format        = "DOCKER"

  description = "Docker image repository"
}
