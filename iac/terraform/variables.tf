### General Variables
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

variable "zone" {
  type = string
}

### APIs Module Variables
variable "services_apis_list" {
  type        = set(string)
  description = "List of services to be enabled in this project before creating resources"
}

### Bucket
variable "buckets" {
  type = map(object({
    bucket_name   = string
    labels_bucket = map(string)
  }))
}

### Service Account Module Variables
variable "service_accounts" {
  type        = map(string)
  description = "The Account ID and the Display Name of the Service Accounts."
}

variable "sa_wifederation_email" {
  type        = string
  description = "Email of the Service Account used for Workload Identity Federation."
}

### VPC Module Variables

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


### Cloud SQL Module Variables
variable "cloud_sql" {
  type = map(object({
    database_version        = string
    instance_tier           = string
    instance_labels         = map(string)
    cloud_sql_instance_name = string
    database_name           = string
    username                = string
    password = object({
      secret_id   = string
      secret_data = string
    })
  }))
}

variable "database_version" {
  type        = string
  description = "Version of the Database Instance."
  default     = "POSTGRES_14"
}

variable "instance_labels" {
  type        = map(string)
  description = "A map of labels to assign to the Cloud SQL Instance."
  default     = {}
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

### GKE Module Variables
variable "gke" {
  type = map(object({
    cluster_name     = string
    region           = string
    should_be_create = bool
  }))
}

variable "gke_resource_labels" {
  type        = map(string)
  description = "A set of key/value label pairs to assign to the GKE Cluster."
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

variable "aws_access_key_id" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
}

variable "aws_secret_access_key" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
}

variable "aws_session_token" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
}

variable "new_relic_api_key" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
}

variable "gemini_api_key" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
}

variable "webhook_slack" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
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
