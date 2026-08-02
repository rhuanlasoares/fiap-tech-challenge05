variable "project_id" {
  description = "ID do projeto utilizado na plataforma."
  type        = string
}

variable "workload_identity_pool_id" {
  type        = string
  description = "The ID used for the pool, which is the final component of the pool resource name"
}

variable "display_name_wip" {
  type        = string
  description = "Display name of the Workload Identity Pool"
}

variable "workload_identity_pool_provider_id" {
  type        = string
  description = "The ID used for the provider, which is the final component of the pool resource name"
}

variable "display_name_wip_provider" {
  type        = string
  description = "Display name of the Workload Identity Provider"
}

variable "owner_and_repository" {
  type        = string
  description = "Owner and the name of the repository. Example: owner/repository."
}

variable "sa_wifederation_email" {
  type        = string
  description = "Email of the Service Account used for Workload Identity Federation."
}