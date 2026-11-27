# Running costs

The platform runs within the **GCP Free Tier** (D14): at this data size, every service it uses stays inside its free monthly allowance. This document lists those allowances, the expected use, and the guardrails that keep it there.

---

## 1. Guardrails

1. **Free first.** When a design has a free option and a paid one, the free one is chosen unless there's a stated reason.
2. **Cap what can be capped.** Every BigQuery query carries a byte cap: dbt in its profile (3 GB, `pipeline/dbt/profiles.yml`), the cost generator in its query (100 MB) and the API in every query (100 MB, `MDP_BQ_MAX_BYTES_BILLED`). Ad hoc queries use `--maximum_bytes_billed`. Cloud Run keeps `min-instances = 0` and at most 2 instances.
3. **Budget alert.** A budget of €5 a month on the billing account, covering all projects and services, emails at 50%, 90% and 100% of actual cost. It only notifies; it doesn't stop spending.

## 2. Free Tier usage per service

Limits are **per month and per billing account**, shared by every project on that account: a prod environment would share the same allowance. Google can change them with 30 days' notice.

| Service | Free each month | Expected use | How it stays free |
|---|---|---|---|
| BigQuery queries | 1 TiB scanned (on-demand pricing) | About 4 GB per full pipeline run: two scans of the GA4 sample (about 1.5 GB each) plus about 90 small queries at the 10 MB minimum. The API: one query per request, 10.5 MB billed (the minimum for one table), plus about 31 MB every 10 minutes for the cached data range and channels while an instance is busy; about 100,000 requests a month would fit | Byte cap on every query; GA4 scanned only by the two intermediate tables, no tests on its view (D37); the API reads only marts (D8) and caches what every request needs (D44) |
| BigQuery storage | 10 GiB | About 50 MB: `int_ga4__sessions` 48 MB; marts, orders, seeds and `raw.ad_spend` under 1 MB | GA4 is read in place, not copied (D2) |
| BigQuery load jobs | Free (batch loading, shared slots) | One per generator run, 85 rows | Load job, not streaming inserts, which are billed (D41) |
| Cloud Storage | 5 GB-months Standard, **only in `us-east1`, `us-west1`, `us-central1`** | Terraform state: a few KB. Build sources: about 40 KB per build, kept 7 days | State bucket `<project-id>-tfstate` and build bucket `<project-id>-cloudbuild` in `us-central1`, not the `US` multi-region; 5 versions kept per state file; build sources deleted after 7 days. The default Cloud Build bucket `<project>_cloudbuild` is never used (D47) |
| Cloud Run (service) | 2M requests, 180,000 vCPU-s, 360,000 GiB-s, 1 GB egress from North America | A handful of calls; under 1 s each once warm | `us-central1`; 0–2 instances; 1 vCPU and 512 MiB, CPU only during requests (request-based billing); 60 s timeout. Calls without a token are rejected by Cloud Run before an instance starts (D50, D51) |
| Artifact Registry | **0.5 GB** storage | The API image is 68.5 MB compressed; images share layers; at most 4 kept (the 3 newest and the deployed one), under 280 MB | Slim two-stage image; cleanup policy keeps the 3 newest versions and the one tagged `live` (D49); repository in `us-central1` with Cloud Run, so pulls are free |
| Cloud Build | 2,500 build-minutes (e2-standard-2) | Under 1 minute per build | Default pool in `us-central1`; source staged in our own `us-central1` bucket, logs in Cloud Logging only (D47) |
| Cloud Logging | **50 GiB** of logs ingested per project | Cloud Run request logs, uvicorn logs and build logs: a few KB per call or build | Default log level; no debug logging in Cloud Run; 30-day default retention (no retention charge) |
| APIs, IAM, service accounts, budgets | Always free | — | — |
| GitHub Actions | Free on public repositories (standard runners) | About 3 billed minutes per run (three jobs of under a minute each) | Three short jobs, each stopped after 10 minutes; a new push cancels the pull request's run in progress (D53) |
| **Vertex AI (Gemini)** | **None** | A few thousand tokens per `/insights` call (v2) | Not used yet (D31). Before v2: estimate the cost per call, consider a free-tier provider (D10), and set a spending limit on the service |

## 3. Sources
- [Free Google Cloud features and trial offer](https://docs.cloud.google.com/free/docs/free-cloud-features)
- [Free Trial and Free Tier products](https://cloud.google.com/free)
- [BigQuery pricing](https://cloud.google.com/bigquery/pricing) · [Cloud Storage pricing](https://cloud.google.com/storage/pricing) · [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing)
- [Google Cloud Observability pricing](https://cloud.google.com/products/observability/pricing) (Cloud Logging) · [Cloud Build with a user-managed service account](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts) (logs must go to Cloud Logging or a bucket you own)
