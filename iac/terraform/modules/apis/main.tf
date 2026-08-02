resource "google_project_service" "api" {
  for_each           = var.services_apis_list
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
