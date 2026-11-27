# Bootstrap: creates the bucket that holds the Terraform state of every
# environment (like the S3 bucket behind an S3 backend). It must exist before
# envs/dev can use it, so this root keeps its own state locally
# (terraform.tfstate, gitignored). See terraform/README.md.

# The Cloud Storage API. It is on by default in new projects; managing it here
# makes the bootstrap work on an empty project too. `disable_on_destroy = false`:
# a destroy only stops tracking it, it never switches the API off.
resource "google_project_service" "storage" {
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

# The state bucket.
resource "google_storage_bucket" "tfstate" {
  name     = "${var.project_id}-tfstate"
  location = var.region # one region, not the US multi-region: Free Tier (W4)

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true       # IAM only, no per-object ACLs
  public_access_prevention    = "enforced" # never public, whatever IAM says

  # The state must outlive any mistake: a destroy fails instead of deleting the
  # bucket (deletion_policy), and a non-empty bucket is never emptied first
  # (force_destroy). Deleting it is a deliberate, manual step.
  deletion_policy = "PREVENT"
  force_destroy   = false

  # Every state write keeps the previous version, so a broken state can be
  # rolled back (like S3 versioning on a state bucket).
  versioning {
    enabled = true
  }

  # Keep the 5 latest versions of each state file (the live one and 4 old
  # ones; GCS counts the live version as newer) and delete the rest, so the
  # bucket stays a few KB.
  lifecycle_rule {
    condition {
      with_state         = "ARCHIVED" # old (noncurrent) versions only
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.storage]
}
