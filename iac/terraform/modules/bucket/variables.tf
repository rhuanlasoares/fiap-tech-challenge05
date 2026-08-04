variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "region" {
  type        = string
  description = "The region where the Subnetwork will be created."
}

variable "bucket_name" {
  type        = string
  description = "Bucket for Loki"
}

variable "labels_bucket" {
  type        = map(string)
  description = "Labels for bucket."
}