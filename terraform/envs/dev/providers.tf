# Credentials come from ADC (`gcloud auth application-default login`), the
# equivalent of an AWS profile: nothing secret lives in the repo.
provider "google" {
  project = var.project_id
  region  = var.region

  # Added to every resource that supports labels (datasets, buckets...), like
  # AWS provider `default_tags`. Used to filter billing reports.
  default_labels = {
    app        = "mdp"
    env        = var.environment
    managed_by = "terraform"
  }
}
