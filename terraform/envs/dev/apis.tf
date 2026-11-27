# APIs the dev environment needs (on AWS, services are always on; on GCP each
# API is switched on per project).
#
# `disable_on_destroy = false`: a destroy only stops tracking an API, it never
# switches it off, since other resources or tools may still rely on it.
locals {
  apis = toset([
    "bigquery.googleapis.com",             # datasets and queries
    "iam.googleapis.com",                  # service accounts
    "cloudresourcemanager.googleapis.com", # project-level IAM grants
    "run.googleapis.com",                  # the API service
    "artifactregistry.googleapis.com",     # its container images
    "cloudbuild.googleapis.com",           # builds the images (D30)
    "logging.googleapis.com",              # build and request logs; on by default, listed to be sure
  ])
}

resource "google_project_service" "this" {
  for_each = local.apis

  service            = each.value
  disable_on_destroy = false
}
