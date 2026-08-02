variable "project_id" {
  type = string
}

variable "services_apis_list" {
  type        = set(string)
  description = "List of services to be enabled in this project before creating resources"
}
