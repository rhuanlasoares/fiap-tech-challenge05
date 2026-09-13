variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "region" {
  type        = string
  description = "The region where the Subnetwork will be created."
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


variable "donation_secret" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
}

variable "ngo_secret" {
  type = object({
    secret_id   = string
    secret_data = string
  })
  sensitive = true
}

variable "sm_sqs_queue_url" {
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