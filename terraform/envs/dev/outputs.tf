output "datasets" {
  description = "BigQuery datasets, one per data layer."
  value       = { for name, ds in google_bigquery_dataset.layer : name => ds.id }
}

output "api_service_account" {
  description = "Identity of the KPI API on Cloud Run."
  value       = google_service_account.api.email
}

output "api_url" {
  description = "URL of the KPI API. Calls need an identity token (api/README.md)."
  value       = google_cloud_run_v2_service.api.uri
}

output "image_repository" {
  description = "Artifact Registry path of the images; the API image is <this>/api:<commit>."
  value       = google_artifact_registry_repository.images.registry_uri
}

output "build_service_account" {
  description = "Identity Cloud Build runs as (gcloud builds submit --service-account)."
  value       = google_service_account.build.email
}

output "build_staging_bucket" {
  description = "Where gcloud builds submit uploads the source (--gcs-source-staging-dir)."
  value       = google_storage_bucket.cloudbuild.url
}

output "pipeline_service_account" {
  description = "Identity of the cost generator and dbt when they run on GCP."
  value       = google_service_account.pipeline.email
}
