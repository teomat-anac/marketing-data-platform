# Building and storing container images (like ECR plus CodeBuild on AWS).
# Images are built by Cloud Build from api/cloudbuild.yaml and pushed here; how
# to run a build: api/README.md. The build's service account and its grants
# are in service_accounts.tf.

# --- Artifact Registry: the image repository ----------------------------------
# Same region as Cloud Run: pulling an image within a region is free.
# Free Tier: 0.5 GB of storage (W3). One image is about 70 MB compressed and
# builds share some layers, so a cleanup policy keeps only the images needed.

resource "google_artifact_registry_repository" "images" {
  repository_id = "mdp"
  location      = var.region
  format        = "DOCKER"
  description   = "Container images of the platform: the KPI API."

  # Cleanup runs in the background (not at push time). KEEP wins over DELETE:
  # the 3 newest versions and the deployed one stay, everything else goes,
  # tagged or not.
  #
  # Why keep the deployed image: the running revision has its own copy (Cloud
  # Run imports the image at deploy), but a new revision made without a new
  # image (a settings change from Terraform, which ignores the image, or from
  # `gcloud run services update`) pulls it again by its tag. Each release moves
  # the `live` tag to the image it deploys (api/README.md), and that image is
  # never deleted, even after 3 newer builds that weren't deployed.
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-3-newest"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  cleanup_policies {
    id     = "keep-live"
    action = "KEEP"
    condition {
      tag_state    = "TAGGED"
      tag_prefixes = ["live"] # commit tags are hex, so never start with "live"
    }
  }

  cleanup_policies {
    id     = "delete-the-rest"
    action = "DELETE"
    condition {
      tag_state = "ANY"
    }
  }

  depends_on = [google_project_service.this]
}

# --- Cloud Build source staging bucket ----------------------------------------
# `gcloud builds submit` uploads the source to a bucket before building. Its
# default bucket (<project>_cloudbuild) isn't ours to place; this one is in
# us-central1, inside the Cloud Storage Free Tier (W4). Builds pass it with
# --gcs-source-staging-dir. Sources are about 40 KB and deleted after 7 days.
# No depends_on for the Cloud Storage API: terraform/bootstrap switches it on,
# and this environment can't exist without the bootstrap's state bucket.

resource "google_storage_bucket" "cloudbuild" {
  name     = "${var.project_id}-cloudbuild"
  location = var.region

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true       # IAM only, no per-object ACLs
  public_access_prevention    = "enforced" # never public, whatever IAM says

  # Only copies of the source live here: a destroy may empty it (US-6).
  force_destroy = true

  lifecycle_rule {
    condition {
      age = 7 # days
    }
    action {
      type = "Delete"
    }
  }
}
