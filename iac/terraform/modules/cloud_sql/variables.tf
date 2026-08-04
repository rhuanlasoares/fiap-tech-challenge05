variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "region" {
  type        = string
  description = "The region where the Subnetwork will be created."
}

variable "vpc_self_link" {
  type        = string
  description = "The self link of the VPC Network."
}

variable "database_version" {
  type        = string
  description = "Version of the Database Instance."
  default     = "POSTGRES_14"
}

variable "cloud_sql_instance_name" {
  type        = string
  description = "The name of the Cloud SQL Instance."
}

variable "instance_tier" {
  type        = string
  description = "The machine type to use for the Cloud SQL Instance."
}

variable "instance_labels" {
  type        = map(string)
  description = "A map of labels to assign to the Cloud SQL Instance."
  default     = {}
}

variable "psa_name" {
  type        = string
  description = "The name of the PSA IP Range."
}

variable "sa_gke_email" {
  type = string
}

variable "database_name" {
  type = string
}

variable "username" {
  type = string
}

variable "password" {
  type = object({
    secret_id   = string
    secret_data = string
  })
}

variable "enable_cross_region_replica" {
  type        = bool
  description = "Enable cross-region read replica for disaster recovery"
  default     = false
}

variable "replica_region" {
  type        = string
  description = "Secondary region for the cross-region replica"
  default     = "us-east1"
}
