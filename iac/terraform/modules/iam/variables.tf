variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "project_number" {
  type        = string
  description = "The Project number of the project where the resource will be created."
}

variable "subnets" {
  type = map(object({
    name                   = string
    region                 = string
    ip_cidr_range          = string
    range_name_pods        = string
    ip_cidr_range_pods     = string
    range_name_services    = string
    ip_cidr_range_services = string
  }))
  description = "Map of subnet configurations to create in the VPC."
}

variable "sa_gke_member" {
  type        = string
  description = "The email of the GKE Service Account."
}

variable "sa_gke_name" {
  type        = string
  description = "The name of the GKE Service Account."
}

variable "artreg" {
  type = map(object({
    name_artreg = string
    description = string
    region      = string
  }))
}

variable "sa_inside_gke" {
  type = string
}

variable "secrets" {
  type = map(object({
    secret_id   = string
    secret_data = string
  }))
}

variable "buckets" {
  type = map(object({
    bucket_name     = string
    labels_bucket = map(string)
  }))
}