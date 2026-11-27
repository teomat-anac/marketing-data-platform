# KPI API

FastAPI service that serves KPIs per channel, daily trends and the purchase funnel from the BigQuery marts.
Design, endpoints and rules: [`docs/architecture.md`](../docs/architecture.md) §4.

It runs on Cloud Run and reads the real marts built by [`pipeline/`](../pipeline/). Locally, it can read the same marts or serve **seeded simulated data** with the same schema (plausible numbers, not the real ones).

## Run locally
```sh
cd api
uv sync
MDP_DATA_BACKEND=fake uv run uvicorn mdp_api.main:create_app --factory --reload
```
On the real marts instead (your ADC credentials; each request is one query of about 10 MB):
```sh
MDP_DATA_BACKEND=bigquery MDP_BQ_PROJECT=<project-id> uv run uvicorn mdp_api.main:create_app --factory --reload
```
Then open http://localhost:8000/docs, or call it directly:
```sh
curl "localhost:8000/kpi?start=2020-12-01&end=2020-12-07&channel=Paid%20Search"
curl "localhost:8000/kpi/daily?start=2020-11-25&end=2020-11-30"
curl "localhost:8000/funnel?start=2020-11-01&end=2020-11-30"
```
Data runs from 2020-11-01 to 2021-01-24.

## Settings
Environment variables with the `MDP_` prefix. On Cloud Run, Terraform sets them (`terraform/envs/dev/cloud_run.tf`).

| Variable | Default | Meaning |
|---|---|---|
| `MDP_DATA_BACKEND` | **required** | `bigquery` (the real marts) or `fake` (simulated). No default, so a deploy that forgets it fails at startup instead of serving simulated numbers. |
| `MDP_FAKE_SEED` | `42` | Seed of the simulated data. |
| `MDP_BQ_PROJECT` | required for `bigquery` | Project of the marts dataset; queries run and are billed there. |
| `MDP_BQ_DATASET` | `marts` | Dataset of `mart_channel_daily` and `mart_funnel_daily`. |
| `MDP_BQ_LOCATION` | `US` | BigQuery location of the dataset (D7). |
| `MDP_BQ_MAX_BYTES_BILLED` | `100000000` | Byte cap on every query (100 MB); a query that would bill more fails. |
| `MDP_BQ_CACHE_SECONDS` | `600` | How long the data range and the channel list are kept before they're read again. |

## Checks
```sh
uv run --locked pytest            # unit tests; no GCP access needed
uv run --locked ruff check        # --locked: fail on a stale uv.lock, as CI does
uv run --locked ruff format --check
```
The tests marked `bigquery` read the real marts and are skipped by default. Run them after a pipeline run or a change to the BigQuery repository (about 5 queries, 50 MB billed):
```sh
MDP_BQ_PROJECT=<project-id> uv run pytest -m bigquery
```

## Build and deploy
The image is built by **Cloud Build** from [`Dockerfile`](Dockerfile) and [`cloudbuild.yaml`](cloudbuild.yaml), so no local Docker is needed. Terraform creates the repository, the build's service account and the Cloud Run service ([`terraform/`](../terraform/)). Each release is three commands, from the repo root, on a clean, committed tree (the image is tagged with the commit). Set `PROJECT` to your project ID first:
```sh
PROJECT=<project-id>
TAG=$(git rev-parse --short HEAD)

gcloud builds submit api --project=$PROJECT --region=us-central1 --config=api/cloudbuild.yaml \
  --substitutions=_TAG=$TAG \
  --service-account=projects/$PROJECT/serviceAccounts/mdp-build@$PROJECT.iam.gserviceaccount.com \
  --gcs-source-staging-dir=gs://$PROJECT-cloudbuild/source

gcloud run deploy mdp-api --project=$PROJECT --region=us-central1 --quiet \
  --image=us-central1-docker.pkg.dev/$PROJECT/mdp/api:$TAG

gcloud artifacts docker tags add us-central1-docker.pkg.dev/$PROJECT/mdp/api:$TAG \
  us-central1-docker.pkg.dev/$PROJECT/mdp/api:live
```
- The build runs as `mdp-build` and uploads the source to our `us-central1` bucket, never to the default `<project>_cloudbuild` one (`docs/costs.md`).
- Its logs go to Cloud Logging only, so `gcloud builds submit` shows no log lines. Read them in the console (the link it prints) or with `gcloud builds log <BUILD_ID> --region=us-central1`.
- The deploy changes only the image. Every other setting stays as Terraform set it, and `terraform plan` still shows no changes.
- Artifact Registry keeps the 3 newest images and the one tagged `live`, and deletes the others in the background. The `live` tag matters: a settings change (from Terraform or `gcloud run services update`) makes a new revision that pulls the deployed image again, so it must still exist.

## Call the deployed API
The service accepts only callers with the invoker permission (D29): today, project Owners. Without a token Cloud Run answers 403 before the app runs.
```sh
URL=$(terraform -chdir=terraform/envs/dev output -raw api_url)
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$URL/kpi?start=2020-12-08&end=2020-12-14&channel=Paid%20Search"
```
Or open it in a browser through a local proxy that adds your token: `gcloud run services proxy mdp-api --region=us-central1`, then http://localhost:8080/docs.
