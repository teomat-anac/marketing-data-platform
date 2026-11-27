output "state_bucket" {
  description = "Bucket for remote state; each envs/*/backend.hcl points at it."
  value       = google_storage_bucket.tfstate.name
}
