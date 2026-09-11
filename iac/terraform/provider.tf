terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.2.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 8.2.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.64.0"
    }
  }
  backend "gcs" {
    bucket = "gcs-naconfeitaria"
    prefix = "terraform-fiap/state"
  }
}

provider "aws" {
  region = "us-east-1"
}
