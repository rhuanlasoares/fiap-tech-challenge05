variable "project_id" {
  type        = string
  description = "The Project ID of the project where the resource will be created."
}

variable "service_accounts" {
  type        = map(string)
  description = "The Account ID and the Display Name of the Service Accounts."
}