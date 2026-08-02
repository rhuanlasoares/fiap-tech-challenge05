resource "google_storage_bucket" "bucket_output" {
  name          = var.bucket_name
  project       = var.project_id
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = false
  public_access_prevention    = "enforced"
}