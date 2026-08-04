variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "vpc_name" {
  type        = string
  description = "The name of the VPC Network."
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
