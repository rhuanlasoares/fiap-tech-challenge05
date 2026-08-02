variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "project_number" {
  type        = string
  description = "The Project number of the project where the resource will be created."
}

variable "region" {
  type        = string
  description = "The region where the Subnetwork will be created."
}

variable "subnet_name" {
  type        = string
  description = "The name of the Subnetwork."
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
