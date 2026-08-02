terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.42.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.42.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.57.1"
    }
  }
  backend "gcs" {
    bucket = "gcs-terraform-image-process"
    prefix = "terraform/state"
  }
}

provider "aws" {
  region = "us-east-1"
}
