# Terraform

Creates every GCP resource of the platform (US-6). Design: [`docs/architecture.md`](../docs/architecture.md) §5; costs: [`docs/costs.md`](../docs/costs.md).

```
terraform/
  bootstrap/   the state bucket; its own state stays local (terraform.tfstate, gitignored)
  envs/dev/    the dev environment; state in gs://<project-id>-tfstate/envs/dev
```

Versions are pinned exactly: Terraform `1.17.2`, provider `hashicorp/google` `8.12.0`. `.terraform.lock.hcl` is committed, with checksums for `darwin_arm64` and `linux_amd64` (CI).

CI checks every pull request to `main` with `terraform fmt -check -recursive`, then `init -backend=false -lockfile=readonly` and `validate` on both roots; no credentials, no state (`architecture.md` §5 CI). To check locally without touching your initialised `.terraform/` folders, run `terraform fmt -check -recursive` here, and `terraform validate` in each root you have initialised.

## One-off manual steps
These are the only clicks, done once per project:
1. Create the GCP project and link it to a billing account; set a budget alert.
2. `gcloud auth login` and `gcloud auth application-default login`. Terraform uses these ADC credentials; the ADC quota project must be the project.

## Configure your project
The project ID is not in the repo. Each root reads it from a local, gitignored `terraform.tfvars`; the dev environment also reads its state bucket from a gitignored `backend.hcl` (Terraform allows no variables in a backend block). Copy the examples and set your project ID:
```sh
cp terraform/bootstrap/terraform.tfvars.example terraform/bootstrap/terraform.tfvars
cp terraform/envs/dev/terraform.tfvars.example  terraform/envs/dev/terraform.tfvars
cp terraform/envs/dev/backend.hcl.example       terraform/envs/dev/backend.hcl   # bucket = "<project-id>-tfstate"
```

## Create an environment from an empty project
```sh
cd terraform/bootstrap
terraform init
terraform apply          # the state bucket

cd ../envs/dev
terraform init -backend-config=backend.hcl
terraform apply          # APIs, datasets, service accounts, IAM, image repository, build bucket, Cloud Run service
```
Running `apply` again changes nothing.

The Cloud Run service starts on Google's public placeholder image (it answers with a "hello" page). Terraform ignores the image from then on: build and deploy the API with the three commands in [`api/README.md`](../api/README.md) ("Build and deploy"). After a deploy, `plan` still shows no changes.

On a brand-new project the first `apply` in `envs/dev` can stop with "API has not been used in project … or it is disabled": an API just switched on takes a minute to be usable. Wait a minute and run `apply` again; it picks up where it stopped.

## Tear down dev
```sh
cd terraform/envs/dev
terraform destroy
```
This deletes the datasets (with their tables), the Cloud Run service, the image repository (with its images), the build bucket (with the staged sources) and the service accounts and their grants. The APIs stay on (`disable_on_destroy = false`). The state bucket stays too: it holds the state, and `deletion_policy = "PREVENT"` makes a destroy of it fail. To remove it on purpose, after destroying every environment: set `deletion_policy = "DELETE"` in `bootstrap/main.tf` and `apply`; delete every object version (the bucket is versioned, so a plain delete leaves old versions behind) with `gcloud storage rm --all-versions "gs://<project-id>-tfstate/**"`; then `terraform destroy` in `bootstrap/`.

## If the bootstrap state is lost
The bucket still exists; only the local file that tracks it is gone. Bring it back under Terraform:
```sh
cd terraform/bootstrap
terraform init
terraform import google_project_service.storage <project-id>/storage.googleapis.com
terraform import google_storage_bucket.tfstate <project-id>-tfstate
terraform plan           # expect one in-place update: deletion_policy "DELETE" -> "PREVENT"
terraform apply          # required: restores the protection
```
`deletion_policy` exists only in Terraform's state, not in GCP, so the import sets it to its default, `DELETE`. Until the `apply`, Terraform won't refuse a destroy; only `force_destroy = false` (which the import sets as the code does) makes it fail, and only while the bucket still holds files. After the `apply`, `plan` shows no changes.

## Checking attribute names
Attribute names come from the provider schema, not from memory:
```sh
terraform providers schema -json > /tmp/google-schema.json   # after terraform init; ~10 MB, keep it out of the repo
```
