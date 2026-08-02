variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "region" {
  type        = string
  description = "The region where the Subnetwork will be created."
}

variable "gke_cluster_name" {
  type        = string
  description = "The name of the GKE Cluster."
}

variable "gke_resource_labels" {
  type        = map(string)
  description = "A set of key/value label pairs to assign to the GKE Cluster."
}

variable "vpc_self_link" {
  type        = string
  description = "The self link of the VPC Network."
}

variable "subnet_self_link" {
  type        = string
  description = "The self link of the Subnetwork."
}

variable "range_name_pods" {
  type        = string
  description = "The name of the secondary IP range for Pods."
}

variable "range_name_services" {
  type        = string
  description = "The name of the secondary IP range for Services."
}

variable "sa_gke_member" {
  type        = string
  description = "The email of the GKE Service Account."
}
