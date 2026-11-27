variable "project_id" {
  description = "GCP project that holds the environment (created by hand, with billing)."
  type        = string
}

variable "environment" {
  description = "Environment name, used in labels."
  type        = string
}

variable "region" {
  description = "Region of the state bucket. us-central1 keeps it in the Cloud Storage Free Tier (docs/costs.md)."
  type        = string

  validation {
    condition     = contains(["us-central1", "us-east1", "us-west1"], var.region)
    error_message = "region must be us-central1, us-east1 or us-west1: Cloud Storage is free only there (docs/costs.md)."
  }
}
