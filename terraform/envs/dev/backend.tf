# Remote state in the bucket created by terraform/bootstrap (like an S3
# backend). Terraform doesn't allow variables in this block, so the bucket name
# comes from a local, gitignored file at init time:
#   terraform init -backend-config=backend.hcl
# (copy backend.hcl.example). GCS locks the state during each run on its own: no
# extra lock table is needed (unlike DynamoDB for S3).
terraform {
  backend "gcs" {
    prefix = "envs/dev"
  }
}
