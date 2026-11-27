# The KPI API on Cloud Run (like a container on Fargate behind a Lambda
# function URL with AWS_IAM auth): scales to zero, billed per request.
#
# Who can call it: only identities with `run.routes.invoke` on the service, e.g.
# roles/run.invoker, or a project Owner. Cloud Run checks the Google identity
# token before a request reaches the container (D29); no `allUsers` grant, so
# the service is never public. The URL is reachable from the internet (ingress
# ALL) so it can be called from a laptop, but without a valid token the call
# stops at Cloud Run.
#
# The image: Terraform creates the service with Google's public placeholder,
# then ignores the image. Each release builds an image with Cloud Build and
# deploys it with `gcloud run deploy` (api/README.md). This avoids needing an
# image before the first apply, and Terraform never rolls a release back.

locals {
  # Pinned by digest like every other image (it only matters on the first apply).
  placeholder_image = "us-docker.pkg.dev/cloudrun/container/hello@sha256:9654ebfdd31387ad4c1b79ca025ce55ed157d55abb29bdd6ec2231f754d8da0e"
}

resource "google_cloud_run_v2_service" "api" {
  name        = "mdp-api"
  location    = var.region
  description = "KPI API: KPIs per channel, daily trends and the funnel, read from the marts."

  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false # every caller needs the invoker permission (D29)

  # Teardown is one step (US-6); the service holds no data.
  deletion_protection = false

  template {
    service_account = google_service_account.api.email
    timeout         = "60s" # a request reads one small mart; give up well before the 300s default

    # Free Tier: no idle instance (min 0); max 2 caps cost if something loops.
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.placeholder_image

      ports {
        container_port = 8080
      }

      # CPU only while a request is handled (request-based billing); the
      # smallest CPU, and enough memory for Python and the BigQuery client.
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = false
      }

      # The API's settings (api/README.md). Not secrets: IDs and names.
      env {
        name  = "MDP_DATA_BACKEND"
        value = "bigquery"
      }
      env {
        name  = "MDP_BQ_PROJECT"
        value = var.project_id
      }
      env {
        name  = "MDP_BQ_DATASET"
        value = google_bigquery_dataset.layer["marts"].dataset_id
      }
      env {
        name  = "MDP_BQ_LOCATION"
        value = var.bq_location
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image, # set by each `gcloud run deploy`
      client,                          # gcloud records itself as the last client
      client_version,
    ]
  }

  depends_on = [
    google_project_service.this,
    # The API can read the marts as soon as it starts.
    google_bigquery_dataset_iam_member.api_reads_marts,
    google_project_iam_member.api_runs_queries,
  ]
}
