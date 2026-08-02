variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "vpc_name" {
  type        = string
  description = "The name of the VPC Network."
}

variable "subnet_name" {
  type        = string
  description = "The name of the Subnetwork."
}

variable "region" {
  type        = string
  description = "The region where the Subnetwork will be created."
}

variable "ip_cidr_range_subnet_gke" {
  type        = string
  description = "The IP CIDR range for the GKE Subnetwork."
}

variable "range_name_pods" {
  type        = string
  description = "The name of the secondary IP range for Pods."
}

variable "ip_cidr_range_pods" {
  type        = string
  description = "The IP CIDR range for the Pods secondary IP range."
}

variable "range_name_services" {
  type        = string
  description = "The name of the secondary IP range for Services."
}

variable "ip_cidr_range_services" {
  type        = string
  description = "The IP CIDR range for the Services secondary IP range."
}

variable "router_name" {
  type        = string
  description = "The name of the Cloud Router."
}

variable "nat_name" {
  type        = string
  description = "The name of the Cloud NAT."
}

variable "psa_name" {
  type        = string
  description = "The name of the PSA IP Range."
}

variable "sa_gke_email" {
  type = string
}
