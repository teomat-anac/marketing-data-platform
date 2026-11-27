variable "project_id" {
  description = "GCP project that holds the environment (created by hand, with billing)."
  type        = string
}

variable "environment" {
  description = "Environment name, used in labels."
  type        = string
}

variable "region" {
  description = "Default region for regional resources (Cloud Run). us-central1 is in the Free Tier."
  type        = string
}

variable "bq_location" {
  description = "Location of the BigQuery datasets. Must be US, where the public GA4 sample lives (D7)."
  type        = string

  validation {
    condition     = var.bq_location == "US"
    error_message = "bq_location must be US: queries can't join the GA4 public sample (US) with datasets elsewhere (D7)."
  }
}
