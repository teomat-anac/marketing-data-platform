# Service accounts: identities for code, like IAM roles assumed by AWS
# services. Grants are least privilege and additive: `*_iam_member` adds one
# member to one role and leaves every other grant alone. `*_iam_binding` and
# `*_iam_policy` would replace the whole list and could remove the owner's or
# Google's own grants, so they are not used.
#
# Caveat for datasets: `google_bigquery_dataset_iam_member` rewrites the
# dataset's access list and drops any authorized-view entries (views allowed to
# read the dataset). No authorized views exist today; if authorized views are
# added, switch these grants to `google_bigquery_dataset_access` (D34).
#
# Running queries takes two permissions in BigQuery: access to the data
# (granted per dataset) and the right to run query jobs (granted on the project,
# roles/bigquery.jobUser), because the job belongs to the project.

# --- API (Cloud Run service) -----------------------------------------
# Reads the marts and nothing else (D8).

resource "google_service_account" "api" {
  account_id   = "mdp-api"
  display_name = "MDP KPI API"
  description  = "Runs the KPI API on Cloud Run; reads the marts dataset only."

  depends_on = [google_project_service.this]
}

resource "google_bigquery_dataset_iam_member" "api_reads_marts" {
  dataset_id = google_bigquery_dataset.layer["marts"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = google_service_account.api.member
}

resource "google_project_iam_member" "api_runs_queries" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.api.member
}

# --- Build (Cloud Build) ---------------------------------------------
# Builds run as this account instead of Google's default build account: it
# reads the uploaded source, pushes images to one repository and writes its
# logs, nothing else. The user who starts a build needs permission to act as
# it (iam.serviceAccounts.actAs); a project Owner has it.

resource "google_service_account" "build" {
  account_id   = "mdp-build"
  display_name = "MDP image builds"
  description  = "Runs Cloud Build: reads the staged source, pushes images to the mdp repository, writes build logs."

  depends_on = [google_project_service.this]
}

resource "google_storage_bucket_iam_member" "build_reads_sources" {
  bucket = google_storage_bucket.cloudbuild.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.build.member
}

resource "google_artifact_registry_repository_iam_member" "build_pushes_images" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.build.member
}

# Build logs go to Cloud Logging only (api/cloudbuild.yaml): a build with its
# own service account can't use Google's default logs bucket.
resource "google_project_iam_member" "build_writes_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = google_service_account.build.member
}

# --- Pipeline (cost generator + dbt; the nightly Cloud Run job, planned) ------
# Writes every layer. Reading the public GA4 sample needs no grant. Today
# the pipeline runs on a laptop with the operator's own credentials; this account is
# ready for when it runs on GCP.

resource "google_service_account" "pipeline" {
  account_id   = "mdp-pipeline"
  display_name = "MDP data pipeline"
  description  = "Runs the cost generator and dbt; writes the raw, staging, intermediate and marts datasets."

  depends_on = [google_project_service.this]
}

resource "google_bigquery_dataset_iam_member" "pipeline_writes_layers" {
  for_each = google_bigquery_dataset.layer

  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.pipeline.member
}

resource "google_project_iam_member" "pipeline_runs_queries" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.pipeline.member
}
