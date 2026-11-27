# Exact versions (rule: pin everything). The provider's checksums are in
# .terraform.lock.hcl, which is committed.
terraform {
  required_version = "= 1.17.2"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "= 8.12.0"
    }
  }
}
