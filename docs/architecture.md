# Architecture

How the platform is built and why. What it must do is in [`requirements.md`](requirements.md); the data itself is in [`data-sources.md`](data-sources.md).
Decisions are recorded in §6 with their status.

---

## 1. Overview

```
 GA4 sample (public, read in place)        Synthetic ad costs (generator)
              │                                       │
              │                                       ▼
              │                               raw.ad_spend
              ▼                                       ▼
 ┌──────────────────────────── BigQuery ─────────────────────────────┐
 │  raw  ──dbt──▶  staging  ──dbt──▶  intermediate  ──dbt──▶  marts  │
 └───────────────────────────────────────────────────────────────────┘
                                                              │
                                                              ▼
                                                 FastAPI on Cloud Run
                                           /kpi  /funnel  (/insights ──▶ LLM: v2)

 Terraform provisions the GCP resources; GitHub Actions runs CI.
```

| Component | Role | MVP |
|---|---|---|
| GA4 public sample | Real traffic and sales data, read where it is | ✅ |
| Cost generator (Python) | Writes synthetic ad costs to `raw.ad_spend` | ✅ run locally ([`pipeline/`](../pipeline/)) |
| BigQuery | Stores every layer | ✅ |
| dbt | Transforms raw → staging → intermediate → marts, and tests the data | ✅ run locally ([`pipeline/dbt/`](../pipeline/dbt/)) |
| FastAPI on Cloud Run | Serves KPIs and the funnel from the marts | ✅ deployed ([`api/`](../api/)) |
| LLM (Vertex AI or another provider) | Writes the commentary (`/insights`) | v2 (D31) |
| Terraform | Creates all GCP resources | ✅ |
| GitHub Actions | CI (lint, tests, validate); deploys later | ✅ CI only |
| Cloud Run job + Cloud Scheduler | Nightly run of generator + dbt on GCP | Planned |

---

## 2. Data layers

The data moves through layers, from "as delivered" to "ready to use". Each layer is a BigQuery dataset. dbt is not a layer: it's the tool that builds each layer from the previous one, by running SQL inside BigQuery.

| Layer | Contains | Materialised as | Models |
|---|---|---|---|
| **raw** | Data exactly as the source delivered it, and the hand-kept rule tables. Never edited by dbt models. | Tables, written by the generator and `dbt seed` | `raw.ad_spend` (generator); seeds `channels`, `channel_rules`, `tracking_gaps`; GA4 is read in place from the public dataset |
| **staging** | One cleaned model per source table: flattened, typed, renamed. **No business logic.** | Views | `stg_ga4__events` (the data range, with the lookback window before it and one day after, D39), `stg_ads__spend` |
| **intermediate** | Reusable building blocks: joins and aggregations | Tables (D37) | `int_ga4__orders` (one row per order, D17), `int_ga4__sessions` (one row per session, with its own and its attributed channel, D16, orders and funnel steps) |
| **marts** | Answers to business questions, one table per question: the additive parts of the KPIs (ratios are computed on request) | Tables | `mart_channel_daily` (grain: day × channel), `mart_funnel_daily` (grain: day × channel × funnel step) |

The marts have no campaign level: the GA4 sample hides campaign names, so there is nothing to join costs on below the channel (D15).

### The same purchase, layer by layer

**raw** (GA4 sample): the date is text, values are nested, there is no channel.
```
event_date  user_pseudo_id  event_name  event_params                    traffic_source
"20201201"  u1              purchase    [{key:ga_session_id, 111}, …]   {source:google, medium:cpc}
```

**staging** (`stg_ga4__events`): flat, typed, with a session key.
```
event_date  session_key  event_name  source  medium  revenue
2020-12-01  u1-111       purchase    google  cpc     25.00
```

**intermediate** (`int_ga4__sessions`): one row per session, channel assigned (last non-direct click, D16).
```
session_date  session_key  own_channel  channel      orders  revenue
2020-12-01    u1-111       Paid Search  Paid Search  1       25.00
```

**marts** (`mart_channel_daily`): grain = one day × one channel, joined with costs. ROAS (3,000 ÷ 440 = 6.8) is computed on request, not stored.
```
date        channel      is_paid  sessions  orders  revenue  clicks  impressions  spend
2020-12-01  Paid Search  true     500       30      3000.00  550     20000        440.00
```

### Why it's organised like this
| Reason | What it means here |
|---|---|
| **Separation of concerns** | Source quirks are handled in staging, business rules in intermediate and marts. Each fix has one place. |
| **Swappable sources** | Replacing synthetic costs with a real Google Ads connector changes `stg_ads__spend` only. |
| **Reprocessing** | Raw is never modified, so staging, intermediate and marts can always be rebuilt (FR-5). |
| **One version of the numbers** | Channel mapping and metric formulas are defined once (goal G2). |
| **Cost and speed** | The API reads only the small marts, never the GA4 events. |
| **Testing per layer** | Unique session keys in intermediate; one row per date + channel in marts; revenue and spend ≥ 0. |

### The dbt project
Code in [`pipeline/dbt/`](../pipeline/dbt/); how to run it: [`pipeline/README.md`](../pipeline/README.md).
- **Datasets:** models go to the Terraform datasets by exact name (`generate_schema_name` override, D37); seeds go to `raw`.
- **Rules as data** (D38): seeds for the channel list, the ordered channel rules (RE2 patterns on source and medium, ignoring case, first match wins) and the tracking gaps; dbt variables for the data range, the shop's own domains and the 90-day lookback.
- **Tests:** 76 data tests and 2 unit tests, all run by `dbt build`:
  - keys: unique and not null for orders, sessions, both mart grains (D43) and the ad rows;
  - values: channels from the seed, money and counts ≥ 0, zero cost on unpaid channels, `is_tracked` false exactly when `sessions` is NULL;
  - across models: mart row counts (days × channels × steps), mart totals equal to the sessions and ad-cost totals, funnel visits equal to KPI sessions, some spend on every paid channel;
  - unit tests on hand-made rows, with their own rule rows and settings, for D16 (self-referrals, first touch, Direct inheriting within the lookback, also from before the range, channel rules in any case, sessions after midnight, sessions outside the range) and D17 (duplicates, colliding IDs, purchases without ID or amount).
- **Cost:** every query is capped at 3 GB (`profiles.yml`). A full build scans GA4 twice (orders and sessions, about 1.5 GB each) and bills about 4 GB with the tests (BigQuery bills at least 10 MB per query).

### Metric rules
- Marts store **additive components** (sessions, orders, revenue, clicks, impressions, spend) per day and channel.
- **Ratios** (ROAS, CPA, conversion rate) are recomputed from the summed components for any period: period ROAS = Σ revenue ÷ Σ spend. Daily ratios are never averaged.
- ROAS and CPA are `NULL` when spend is 0.
- **Sessions, not users, are the volume metric** (D11). Unique users aren't additive across days, so they can't be stored per day and summed.
- **Zero-filled:** the marts have one row for every date × channel (and step), even with no activity. A date spine is crossed with the channel list (D13).
- **Funnel** (D12): for each day, channel and step, the number of sessions that reached that step (open funnel). A step that wasn't recorded on a day is `NULL`, not 0 (D20).

### Mart schema (contract)
Fixed by D22. It's the contract between dbt and the API: the API is built and tested against it.

**Common to both marts**
- **Date range:** 2020-11-01 to 2021-01-24, 85 days (D18). `date` is the day the session started.
- **Channels:** the nine of D19 (`data-sources.md` §5). Every date × channel (× step) has a row, zero-filled (D13).
- **Money:** `NUMERIC` (exact decimals), USD, rounded to cents. Revenue is without tax and before refunds (D17).
- **No ratios stored.** ROAS, CPA, conversion rate and AOV are computed from the sums for the requested period (FR-7).
- **Table settings:** partitioned by `date`, clustered by `channel`. Free at this size, and the right setup for years of client data.

**`mart_channel_daily`**: one row per date × channel (765 rows)

| Column | Type | Meaning |
|---|---|---|
| `date` | DATE | Day |
| `channel` | STRING | Channel (D19) |
| `is_paid` | BOOL | `true` for paid channels (here only Paid Search) |
| `sessions` | INT64 | Sessions credited to the channel (D16) |
| `orders` | INT64 | Unique orders (D17) |
| `revenue` | NUMERIC | Order revenue in USD |
| `clicks` | INT64 | Ad clicks; 0 for channels that aren't paid |
| `impressions` | INT64 | Ad impressions; 0 for channels that aren't paid |
| `spend` | NUMERIC | Ad cost in USD; 0 for channels that aren't paid |

**`mart_funnel_daily`**: one row per date × channel × step (3,825 rows)

| Column | Type | Meaning |
|---|---|---|
| `date` | DATE | Day |
| `channel` | STRING | Channel (D19) |
| `step` | STRING | `visit`, `view_item`, `add_to_cart`, `begin_checkout`, `purchase` |
| `step_number` | INT64 | 1–5, in that order |
| `sessions` | INT64 | Sessions that reached the step that day (open funnel, D12); `NULL` when the step wasn't recorded |
| `is_tracked` | BOOL | `false` when the step wasn't recorded that day (D20): `add_to_cart` before 2020-11-26 |

---

## 3. Data flow (one run)

1. **dbt: seeds, GA4 staging, intermediate.** `dbt build --select resource_type:seed +int_ga4__sessions`, with their tests.
2. **Generator.** Read paid sessions per day from `int_ga4__sessions` (by `own_channel`: the visits ads actually brought, not the attributed ones) and replace `raw.ad_spend`: idempotent, fixed seed (D41).
3. **dbt: cost staging + marts + tests.** `dbt build --select source:ads+ path:models/marts`, with every remaining test.
4. **API.** Reads the marts on request.

The generator sits between two dbt steps because it needs real paid traffic to generate costs that follow it.
Both dbt steps use `--indirect-selection buildable`, so a step never runs a test on a model the other step builds (D42).
Today `uv run mdp-pipeline` runs steps 1–3 from a laptop. Planned: the same command in one Cloud Run job, triggered nightly by Cloud Scheduler.

---

## 4. API

Built against the mart schema (§2) and tested on simulated data; it reads the real marts and runs on Cloud Run. Code, settings and the release commands: [`api/`](../api/).

### Endpoints
Every endpoint is `GET`. `start` and `end` are days, both included; `channel` is optional (any case, spaces ignored; all channels if omitted or empty). The interactive docs are at `/docs`.

| Endpoint | Returns | Requirements |
|---|---|---|
| `/health` | `{"status": "ok"}`; it doesn't read data, so it costs nothing | — |
| `/kpi` | Per channel (sorted by revenue) and in total: sessions, orders, revenue, spend, clicks, impressions, ROAS, CPA, conversion rate, AOV. Each KPI comes with the previous period: value, previous, change, % change | US-1, US-4, FR-10, FR-13 |
| `/kpi/daily` | One row per day × channel, zeros included, with that day's ratios | US-2, FR-11 |
| `/funnel` | Sessions reaching each step, and the rate from the previous step | US-3, FR-12 |

### Code layout
```
api/src/mdp_api/
  api.py         HTTP: checks dates and channel (FR-15), then calls service
  service.py     builds each response: reads rows, runs metrics, rounds for display
  metrics.py     the KPI rules, plain Python with exact decimals: totals, ratios, comparison, funnel
  periods.py     date ranges and the previous period
  marts.py       the mart rows (the §2 contract)
  repository/    MartRepository: reads and filters mart rows, calculates nothing
    bigquery.py  the real marts: parameterised, capped queries
    memory.py    rows held in memory: tests and local runs
    fake.py      seeded simulated marts (85 days × 9 channels, with the add_to_cart gap)
```
Only `repository/` knows where the data lives; the setting `MDP_DATA_BACKEND` (required, D45) picks `bigquery` or `fake`. `service` is kept apart from HTTP so that `/insights` (v2, D31) gets the same numbers.

### Rules
- **Ratios** come from period totals (FR-7) and are `null` when the denominator is 0. CPA is also `null` when there's spend but no order.
- **Total row:** all channels together; its ROAS and CPA are *blended* (all revenue or orders against all ad spend). Every channel in scope is listed, even one without rows, so the channels always add up to the total.
- **Previous period** (US-4): the same number of days, ending the day before `start`. It's compared only when it lies entirely inside the data; otherwise every `previous` is `null` and `previous_period.reason` says why.
- **Funnel gaps** (D20): a step not recorded on at least one day of the period is not recorded for the whole period (`sessions` `null`, `untracked_days` > 0), and the rates into and out of it are `null`. Every day × channel in scope needs a recorded row: a missing row makes that day not recorded for the step, never 0. All five steps are always listed.
- **Daily rows** (US-2, D13): every day × channel in scope has a row; one missing from the mart is filled with zeros.
- **Duplicate rows** (D43): each mart key appears once. A repository that finds two rows for the same day × channel (× step) raises an error instead of adding them up or keeping one.
- **Validation** (FR-15): the data range (the days present in both marts) and the channel list come from the data, not from code. Problems with the dates and the channel come back together in one 422 response, in the same shape as FastAPI's own validation errors. A malformed date is rejected by FastAPI first, on its own.
- **Numbers:** money, ROAS, CPA and AOV have 2 decimals (rounded half up); conversion rates and % changes are fractions with 4 decimals; counts are integers. `change` and `change_pct` are computed from the values as shown (rounded), so the response always adds up and never shows a huge % next to a previous value shown as 0.
- **Authentication** (FR-16): no code in the app. Cloud Run checks the Google identity token, and that the caller has the invoker permission, before a request reaches the container (D29, D51). Without a token the answer is 403, with an invalid one 401.

### BigQuery backend (D44)
- Four queries, all with parameters (no values pasted into SQL), a 100 MB byte cap and the job labels `app=mdp`, `component=api`: the data range (first and last day of each mart), the channel list, and the rows of each mart for a period and an optional channel. The date filter is on the partition column.
- The data range and the channel list are cached for 10 minutes per instance, so a request costs one query on one mart: 10.5 MB billed, BigQuery's minimum per table. `/kpi` reads the period and the previous one in that same query.
- Each request reads the data range and the channel list once (`RequestView` in `api.py`), so a cache refresh in the middle of a request can't make the checks and the response disagree.
- No wait is left open: BigQuery cancels a query after 15 seconds; every HTTP call to BigQuery waits at most 15 seconds, retries stop after 15 seconds and a failed job isn't re-run (the library's defaults are no HTTP timeout, 10 minutes of retries and 40 minutes of job retries).
- The cache never makes requests queue. One request at a time reloads an expired value, outside the lock, while the others keep using the value held. On a new instance, requests arriving together each run the first load (a few extra queries of 10.5 MB). If the reload fails, the old value is kept and served and the next request tries again; the error reaches a caller only on the very first load. So a slow or failing BigQuery delays one request, not all of them.
- Duplicate keys in the rows read are an error (D43), with the same check as the in-memory repository.
- Tests (D46): the repository runs on a simulated BigQuery client and must give the same responses as the in-memory repository; an opt-in live test (`-m bigquery`) checks the real marts against the figures in `data-sources.md` §5.

### Deployment
```
 laptop ──gcloud builds submit──▶ gs://<project>-cloudbuild (us-central1)
                                        │
                                        ▼
                           Cloud Build (runs as mdp-build)
                                        │ docker build, push api:<commit>
                                        ▼
                           Artifact Registry  mdp  (us-central1, 3 newest + live kept)
                                        │
 laptop ──gcloud run deploy────────────▶▼
                           Cloud Run  mdp-api  (runs as mdp-api) ──reads──▶ BigQuery marts
                                        ▲
 caller with identity token ────────────┘   (no token: 403 from Cloud Run)
```
- **Image** (D47): two stages; uv installs the locked runtime dependencies into a venv, which is copied into `python:3.12.16-slim-trixie`, pinned by digest, and runs as a non-root user. 68.5 MB compressed. Tagged with the commit.
- **Release:** three commands: build, deploy, then move the `live` tag to the deployed image ([`api/README.md`](../api/README.md)). Terraform created the service on a placeholder image and ignores the image (and gcloud's `client` fields) from then on (D50), so `plan` stays clean after a deploy and never rolls a release back.
- **Service** (D50): `us-central1`; 0–2 instances; 1 vCPU and 512 MiB, CPU only during requests; 60 s request timeout; settings as env vars set by Terraform.

---

## 5. Infrastructure (Terraform) and CI

Terraform code is in [`terraform/`](../terraform/); how to run, tear down and recover: [`terraform/README.md`](../terraform/README.md). CI is at the end of this section.

### Layout and state (D32)
| Root | Creates | State |
|---|---|---|
| `terraform/bootstrap/` | The Cloud Storage API and the state bucket `<project-id>-tfstate` (`us-central1`, versioned, the 5 latest versions kept, public access blocked, `deletion_policy = "PREVENT"`) | Local, gitignored; re-importable if lost |
| `terraform/envs/dev/` | APIs, BigQuery datasets, service accounts, IAM, image repository, build bucket, Cloud Run service | `gs://<project-id>-tfstate/envs/dev` (GCS locks it during each run) |

- Plain files, no modules: there is one environment (D9). A prod environment would be a second folder under `envs/`, at which point shared parts become a module.
- Versions pinned exactly (Terraform `1.17.2`, `hashicorp/google` `8.12.0`); lock files committed with `darwin_arm64` and `linux_amd64` checksums.
- Credentials: the operator's ADC. No Terraform service account until CI deploys (WIF, planned).
- Labels on every resource that takes them, through the provider's `default_labels`: `app=mdp`, `env=dev`, `managed_by=terraform` (plus the provider's own `goog-terraform-provisioned=true`).
- Values in a local, gitignored `terraform.tfvars`, and the dev state bucket in a gitignored `backend.hcl` (Terraform allows no variables in a backend block), each copied from a committed `.example` file: the repo names no GCP project (D56).

### What dev contains
| Resource | Settings | Why |
|---|---|---|
| APIs: BigQuery, IAM, Cloud Resource Manager, Cloud Run, Artifact Registry, Cloud Build, Logging | `disable_on_destroy = false` | A destroy never switches an API off |
| Datasets `raw`, `staging`, `intermediate`, `marts` | Location `US` (D7); `delete_contents_on_destroy = true` | One dataset per layer (§2). Teardown is one step (US-6); every table can be rebuilt |
| Service account `mdp-api` | `bigquery.dataViewer` on `marts`; `bigquery.jobUser` on the project | The API reads only the marts (D8). Running a query also needs the right to create a job in the project |
| Service account `mdp-pipeline` | `bigquery.dataEditor` on the four datasets; `bigquery.jobUser` on the project | For the generator and dbt when they run on GCP (planned). Today they run locally with the operator's credentials |
| Service account `mdp-build` | `storage.objectViewer` on the build bucket; `artifactregistry.writer` on the `mdp` repository; `logging.logWriter` on the project | Cloud Build runs as it instead of Google's default build account (D48) |
| Artifact Registry repository `mdp` | Docker, `us-central1`; cleanup keeps the 3 newest versions and the one tagged `live`, deletes the rest | Images next to Cloud Run (free pulls); 0.5 GB free (D49) |
| Bucket `<project-id>-cloudbuild` | `us-central1`, public access blocked, objects deleted after 7 days, `force_destroy = true` | Where builds stage the source, instead of the default `<project>_cloudbuild` bucket (D47) |
| Cloud Run service `mdp-api` | Runs as `mdp-api`; ingress all, invoker check on, no public grant; `deletion_protection = false`; image ignored after creation | §4 Deployment; D50, D51 |

Dataset names have no prefix: the project is the namespace. dbt must write to these exact names, so the dbt project overrides `generate_schema_name` (by default dbt prefixes the target schema).

### CI
One GitHub Actions workflow, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), runs on every pull request to `main`, on every push to `main` (each merge) and by hand. It has three jobs, which run in parallel and show as three checks (D52):

| Check | Runs | Catches |
|---|---|---|
| `api (ruff, pytest)` | The Python version agrees in `api/.python-version`, `pipeline/.python-version` and the Dockerfile's `FROM` lines; `uv sync` (lock must match), `ruff check`, `ruff format --check`, `pytest` (the live tests `-m bigquery` are left out, D46) | Lint and format errors, failing tests, a `uv.lock` out of date, a Python version bumped in one place only |
| `pipeline (ruff, pytest, dbt parse)` | The same four steps, then `dbt deps` (the committed `package-lock.yml` must stay unchanged) and `dbt parse --warn-error` in `pipeline/dbt/` | The above, plus a stale dbt lock file, broken refs, YAML, Jinja and dbt warnings. Parsing needs no connection, so no credentials |
| `terraform (fmt, validate)` | `terraform fmt -check -recursive`; then, in `bootstrap/` and `envs/dev/`, `init -backend=false -lockfile=readonly` and `validate` | Unformatted files, invalid configuration, wrong attribute names, a provider that doesn't match the lock file |

- **No GCP access** (D53): no secrets, no credentials, no WIF. The workflow's token can only read the code, and checkout doesn't keep it. CI can't change or bill anything on GCP. `terraform plan` and deploys need credentials, so they come with WIF (planned).
- **Pinned** (D54): actions by full commit SHA, with the release in a comment; runner `ubuntu-24.04`; uv `0.13.9`, whose download must match the checksum bundled with `setup-uv`; Python `3.12.16`, read by uv from each project's `.python-version` (uv doesn't look in parent folders) and checked against the API image's `FROM` lines, which can't read a file; Terraform `1.17.2`, with the committed lock file read-only.
- **Bounded:** each job stops after 10 minutes; a new push to a pull request cancels that pull request's run in progress. Every other run has a concurrency group of its own, so no merge's run on `main` is cancelled or dropped (GitHub keeps only one pending run per group). The uv download cache is kept between runs (keyed on each `uv.lock`). A run takes about 1–2 minutes and is billed about 3 (each job is rounded up to a whole minute); [`costs.md`](costs.md) §2.
- **Required** (D57): a ruleset on `main` requires all three checks to pass before a merge, and blocks force pushes and deleting `main`.
- **Run the same checks locally:** the commands above, from each folder (`api/README.md`, `pipeline/README.md`, `terraform/README.md`).

---

## 6. Decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | ELT with layers raw → staging → intermediate → marts | Accepted | See §2 |
| D2 | Read the GA4 sample in place instead of copying it into raw | Accepted | It's already in BigQuery and never changes; copying it adds cost and nothing else |
| D3 | Synthetic costs follow paid traffic (clicks × CPC) | Accepted | ROAS must change with real sales (FR-2); see `data-sources.md` |
| D4 | All money in USD | Accepted | The source revenue is USD (FR-8) |
| D5 | An intermediate layer for sessions, instead of the original plan's `stg_ga4__sessions` | Accepted | Staging stays 1:1 with sources, following dbt convention |
| D6 | Staging as views, marts as tables | Accepted | Views cost nothing to store and are always current; tables make API reads fast and cheap |
| D7 | BigQuery datasets in location `US` | Accepted | Required to query the public GA4 dataset, which is in `US` |
| D8 | The API reads only from marts | Accepted | Cost, speed, one version of the numbers |
| D9 | MVP uses one `dev` environment in one GCP project | Accepted | Fastest path to a working MVP; prod comes later |
| D10 | Commentary language is a setting, default Italian | Planned (v2, D31) | The target user is an Italian marketing manager; other clients may differ |
| D11 | Sessions instead of unique users in the MVP | Accepted | Users can't be summed across days. Later option: store a HyperLogLog sketch per day (`HLL_COUNT.INIT`) and merge sketches for any period (`HLL_COUNT.MERGE`), giving approximate unique users cheaply |
| D12 | Session-based open funnel with a channel filter | Accepted | Sessions are additive and already have a channel, so the funnel lines up with the KPIs |
| D13 | Marts zero-filled for every date × channel | Accepted | No gaps in daily series or comparisons (US-2) |
| D14 | Stay within the GCP Free Tier wherever possible; anything that could leave it is flagged and approved before it happens | Accepted | The platform should cost nothing to run at this size. Limits and guardrails: [`costs.md`](costs.md) |
| D15 | Paid Search is the only paid channel; marts stay at day × channel, with no campaign level | Accepted | The GA4 sample has one paid channel with sales; affiliates and display have almost none, and campaign names are hidden. The platform still handles any number of paid channels. Evidence and rejected options: [`data-sources.md`](data-sources.md) §5 |
| D16 | Attribution: last non-direct click on sessions. A session's source is its first source, ignoring self-referrals; a first session without one takes `traffic_source`; direct sessions inherit the user's last non-direct channel within 90 days. Sessions keep `own_channel` and `channel`. | Accepted | GA4's own rule for session sources (precomputed in exports since 2024 as `session_traffic_source_last_click`). Self-referrals would otherwise take 32% of revenue. Rules and evidence: [`data-sources.md`](data-sources.md) §5 |
| D17 | Orders and revenue. An order is one (`transaction_id`, `user_pseudo_id`), first event kept; a purchase without an ID is an order unless its session already has one with an ID; an order without a recorded amount counts with revenue $0. Revenue = `purchase_revenue_in_usd`: without tax, before refunds. | Accepted | Removes duplicate purchase events without merging orders whose obfuscated IDs collide; purchases without ID or amount are real (their sessions went through checkout); tax isn't the shop's money; the sample has no refunds. Evidence: [`data-sources.md`](data-sources.md) §5 |
| D18 | Data range: 2020-11-01 to 2021-01-24 (85 days) | Accepted | In 25–31 Jan 2021, 70% of purchases have no amount; keeping that week would show a false collapse in revenue |
| D19 | Channel list: GA4's default channel names, nine found in the data (Direct, Paid Search, Organic Search, Organic Social, Organic Video, Referral, Email, Affiliates, Unassigned), with ordered rules in a dbt seed | Accepted | Names marketers know from GA4; a seed lets a client change rules without code (US-7). Rules: [`data-sources.md`](data-sources.md) §5 |
| D20 | Known tracking gaps are listed in a dbt seed; the funnel marks a step on those days as not recorded (`is_tracked = false`, `sessions` null) | Accepted | `add_to_cart` wasn't recorded 1–25 Nov 2020; a zero would read as "nobody added to cart" |
| D21 | Generator settings: one Paid Search campaign; clicks = own-source paid sessions × 1.05–1.15; CPC $1.00 ± 15%; CTR 3% ± 10%; fixed seed | Accepted | Inputs from public benchmarks, not tuned to a target ROAS. Result: Paid Search ROAS about 0.5, because paid visits convert at 0.6% vs 1.5% site-wide |
| D22 | Mart schema fixed (§2 Mart schema): additive columns only, `NUMERIC` money, zero-filled, partitioned by date and clustered by channel | Accepted | It's the contract between dbt and the API; storing no ratios prevents averaging daily ratios (FR-7) |
| D23 | The API is its own uv project in `api/`; direct dependencies pinned exactly, `uv.lock` committed | Accepted | The API image needs only the API's libraries; the generator and dbt get their own projects |
| D24 | The API reads mart rows through a `MartRepository` interface that only filters; all KPI calculations are plain Python | Accepted | The rules are tested without BigQuery; even years of data are about 10k rows per request |
| D25 | `/kpi` returns one row per channel plus a total row, and always includes the previous-period comparison; the comparison is shown only when the previous period is entirely inside the data | Accepted | The manager's main question is "what changed"; a partial previous period would mislead (US-4) |
| D26 | A funnel step not recorded on at least one day of the period is not recorded for the whole period, with the rates next to it empty | Accepted | Counting only the recorded days would make the step-to-step rates wrong. Rejected: summing the recorded days and flagging the step as partial |
| D27 | Dates and channels are checked against the data (range and channel list read from it); errors are 422, in FastAPI's error format | Accepted | Works for any client's data without code changes; one error format for every bad request |
| D28 | JSON numbers: money and ROAS to 2 decimals, rates as fractions to 4 decimals, `null` for ratios that can't be computed | Accepted | Readable values; `null` is never mistaken for a real zero |
| D29 | No authentication code in the app: Cloud Run accepts only callers with a valid Google identity token and the invoker role | Accepted | The platform rejects unauthenticated calls before the code runs; nothing to get wrong in the app |
| D30 | Delivery: an AI coding agent implements; every design decision and every apply, deploy, IAM change and billable step is approved by a person; each change is reviewed before merge. Images are built with Cloud Build | Accepted | Fast delivery with human control over design, cost and access. Cloud Build needs no local Docker |
| D31 | The LLM commentary (`/insights`, US-5, FR-14) moves to v2 | Accepted | Vertex AI is billed from the first call; it also keeps the MVP small. `service` already separates the numbers from HTTP, so `/insights` can be added later without rework |
| D32 | Terraform in two roots: `bootstrap/` (local state) creates the state bucket; `envs/dev/` keeps its state in it. No modules; versions pinned exactly; lock files committed | Accepted | The bucket must exist before any remote state can live in it. One environment doesn't need modules yet. Details: §5 |
| D33 | The state bucket can't be destroyed by Terraform (`deletion_policy = "PREVENT"`, no `force_destroy`) and keeps the 5 latest versions of the state; datasets are destroyed with their contents | Accepted | Losing the state is the one mistake that is hard to undo; the datasets hold nothing that can't be rebuilt, and teardown must be one step (US-6) |
| D34 | One service account per component, granted per dataset where possible; IAM only through additive `*_iam_member` resources | Accepted | Least privilege. `*_iam_binding` and `*_iam_policy` replace a whole member list and could remove the owner's or Google's own grants. **Caveat:** on datasets, `*_iam_member` still rewrites the access list and removes authorized-view entries (provider docs). None exist today; if authorized views are added (e.g. dbt `grant_access_to`), move the dataset grants to `google_bigquery_dataset_access` |
| D35 | Provider attribute names are read from `terraform providers schema -json`, not from the Terraform MCP server. Terraform doesn't manage the GCP project itself | Accepted | The schema comes from the pinned provider itself; the MCP server would need Docker or a separate binary. Managing the project (e.g. for the `environment` tag gcloud suggests) would let a destroy delete it; labels cover billing reports |
| D36 | The pipeline (dbt project and cost generator) is one uv project in `pipeline/`: dbt Core 1.12.7, dbt-bigquery 1.12.4, dbt_utils 1.4.1, google-cloud-bigquery 3.47.0, pinned | Accepted | They always run together, later as one nightly job and one image; the API stays separate (D23). Not chosen: dbt v2, a Rust rewrite that dbt calls the default for new installs. v1 "remains fully supported", is Apache 2.0, and its Python API lets `mdp-pipeline` call dbt in-process |
| D37 | dbt writes to the Terraform datasets by exact name (`generate_schema_name`); seeds go to `raw`; intermediate models are tables; no data tests on the GA4 staging view; every dbt query is capped at 3 GB | Accepted | Terraform owns the datasets (§5). Seeds are hand-kept inputs. As tables, GA4 (about 1.5 GB per scan) is read twice per build instead of by every mart and test; a test on the view would scan it each time |
| D38 | Channel list, channel rules and tracking gaps are seeds; the data range, the shop's own domains and the lookback window are dbt variables. Rule patterns are RE2 regexes written with classes (`[.]`, `[(]`), not backslashes, and match ignoring case; self-referral domains match ignoring case too. The variables are checked: the domains must be a list (`[]` means none), the lookback a whole number of days (0 or more), and dates may be quoted or not. The unit tests bring their own rule rows and settings, so a wrong edit to the rules seed is caught by the data tests only | Accepted | A client changes rules without code (US-7), and those changes must not break the unit tests or pass silently (a string of domains would make nearly every visit a self-referral; Jinja's `int` filter would read a mistyped lookback as 0 and shift credit to Direct). GA4: "Channel definitions aren't case sensitive", so `CPC` is Paid Search. Backslashes break in BigQuery string literals |
| D39 | GA4 events are read from `attribution_lookback_days` before the data range to one day after it; sessions are kept by the day they started, after attribution | Accepted | Orders placed after midnight in sessions that started on the last day stay with them; with a later start date, Direct sessions still inherit from earlier visits and a session from the day before isn't cut in two. The sample has no tables before 2020-11-01, so the earlier days cost nothing. Effect against the exploration figures: +5 orders, +$368 ([`data-sources.md`](data-sources.md) §5) |
| D40 | Funnel steps: `visit` is every session; `purchase` is a session with at least one order (D17) | Accepted | The funnel agrees with the KPI mart (a test checks visits = sessions), and duplicate purchase events don't count |
| D41 | Generator: each row draws from its own random generator, seeded with (seed, day, channel, campaign). One load job with `WRITE_TRUNCATE` replaces `raw.ad_spend`, which the generator creates (partitioned by day), not Terraform. Two runs give identical rows except `loaded_at` | Accepted | Identical output on every run, and a row doesn't change when the range does (FR-5). Load jobs are free and all-or-nothing. The table's schema belongs to its writer, as with a connector. `loaded_at` stays the real write time, as a real export's would |
| D42 | One command, `mdp-pipeline`, runs dbt (seeds, GA4 staging, intermediate), then the generator, then dbt (cost staging, marts); both dbt steps with `--indirect-selection buildable` and `--no-partial-parse`. The dbt folder comes from `--dbt-dir`, else `MDP_DBT_DIR`, else `pipeline/dbt` in the checkout | Accepted | The data fixes the order (§3). `buildable` keeps a step from testing a model built by the other one. A full parse costs seconds and never misses an edited seed. The command becomes the nightly job's entry point; in a container image, `MDP_DBT_DIR` points at the copied dbt project |
| D43 | Each mart key appears once: dbt tests it, and an API repository that finds a duplicate raises an error | Accepted | Otherwise `/kpi` would add duplicate rows up while `/kpi/daily` and `/funnel` kept one, and the endpoints would disagree |
| D44 | The BigQuery repository runs parameterised queries, each capped at 100 MB, limited to 15 seconds and labelled `app=mdp`, `component=api`; the data range and channel list are cached for 10 minutes per instance and read once per request; duplicate keys in the rows read are an error | Accepted | Parameters keep values out of SQL; the cap follows the cost rules. With the cache, a request costs one query on one mart (10.5 MB, the minimum), and a pipeline re-run shows up without a redeploy. Every wait is bounded, and an expired value is reloaded by one request while the others keep using it, falling back to it if the reload fails: a slow or failing BigQuery can't make every request queue behind the cache. Reading once per request keeps a refresh from turning a valid channel into a 500. Labels make the API's queries easy to find in `INFORMATION_SCHEMA.JOBS`. Details: §4 |
| D45 | `MDP_DATA_BACKEND` is required (`bigquery` or `fake`, no default); `MDP_BQ_PROJECT` is required for `bigquery` | Accepted | A deploy that forgets the setting fails at startup instead of serving believable simulated numbers |
| D46 | The BigQuery repository is tested on a simulated BigQuery client that must give the same responses as the in-memory repository; a live test on the real marts runs only on request (`pytest -m bigquery`) | Accepted | CI needs no GCP access; the live test checks the real data for about 50 MB |
| D47 | The API image: two-stage Dockerfile (uv, then `python:3.12.16-slim-trixie`), base images and the Cloud Build docker builder pinned by digest, non-root user. Built by Cloud Build in `us-central1` from `api/cloudbuild.yaml`, tagged with the commit; the source is staged in our own `us-central1` bucket (objects deleted after 7 days), logs go to Cloud Logging only | Accepted | Small image (68.5 MB), within the Artifact Registry free storage; same versions as the lock file. The default staging bucket `<project>_cloudbuild` is never used, so its location doesn't matter |
| D48 | Cloud Build runs as its own service account `mdp-build`, granted only what a build needs: read the staging bucket, write to the `mdp` repository, write logs | Accepted | Least privilege (D34) instead of Google's default build account |
| D49 | Artifact Registry repository `mdp` in `us-central1`, with a cleanup policy that keeps the 3 newest versions and the deployed one (tagged `live` by each release) and deletes the rest | Accepted | 0.5 GB free; at most 4 images, under 280 MB. Same region as Cloud Run, so pulls are free. Cleanup runs in the background, not at push time. The running revision has its own copy of the image (Cloud Run imports it at deploy), but a new revision made without a new image, by a Terraform or `gcloud run services update` settings change, pulls it again by tag: after 3 builds that weren't deployed, the deployed image would be gone and that change would fail |
| D50 | Terraform creates the Cloud Run service on Google's placeholder image and ignores the image and gcloud's `client` fields; each release is `gcloud builds submit`, `gcloud run deploy --image`, then the `live` tag moved to that image (D49). The service: `us-central1`, 0–2 instances, 1 vCPU, 512 MiB, CPU only during requests, 60 s timeout, `deletion_protection = false` | Accepted | One apply, with no image needed first; Terraform never rolls a release back, and `plan` stays clean after a deploy. Free Tier (no idle instance, request-based billing); max 2 caps cost. Teardown stays one step (US-6). Deploy on merge comes with WIF (planned) |
| D51 | Who can call the API: identities with `run.routes.invoke`; today only project Owners, with no extra IAM grant. Ingress is open to the internet, the invoker check stays on, no `allUsers` | Accepted | Cloud Run rejects calls without a valid token (403) or with an invalid one (401) before the container runs (D29). No email in the repo and nothing to remove later. Other callers get `roles/run.invoker` on the service when needed |
| D52 | CI is one GitHub Actions workflow with three parallel jobs (`api`, `pipeline`, `terraform`), run on every pull request to `main`, every push to `main` and by hand, with no path filters. It runs ruff (lint and format), pytest without the live tests, `uv sync` with the lock checked, `dbt deps` with the lock checked + `dbt parse --warn-error`, a check that the Python version agrees across the projects and the API image, and `terraform fmt -check` + `init -backend=false -lockfile=readonly` + `validate` on both roots | Accepted | Each part fails on its own and shows as its own check. Every check runs every time, which is cheap (about 3 billed minutes) and never skips one by mistake. Versions are pinned, so a new dbt warning means the project changed. Details: §5 CI |
| D53 | CI has no GCP access: no secrets, no credentials, no WIF. The workflow token is read-only, checkout doesn't keep it, each job stops after 10 minutes, and a new push cancels the pull request's run in progress | Accepted | Least privilege: nothing in CI can change or bill GCP. Every check works offline from GCP (D46; parse and validate need no connection). `plan` on pull requests and deploys need credentials, so they come with WIF (planned) |
| D54 | Every CI version is pinned: actions by full commit SHA with the release in a comment (checkout v7.0.1, setup-uv v10.4.0, setup-terraform v4.0.1), runner `ubuntu-24.04`, uv 0.13.9 with its checksum required, Python 3.12.16 from each uv project's `.python-version`, Terraform 1.17.2 | Accepted | The pin-everything rule. A tag can be moved to other code, but a commit SHA can't, so a compromised action release can't reach our runs. CI runs the same Python as the API image and the same tools as the laptop. The version is written in three places (two `.python-version` files, the Dockerfile's `FROM`), since neither uv nor Docker can read one shared file, so CI fails when they disagree |
| D55 | While the repo is private, the checks aren't enforced: merge only when all three are green | Superseded by D57 | GitHub Free refuses branch protection and rulesets on private repositories |
| D56 | The repo names no GCP project: each Terraform root's `terraform.tfvars` and the dev backend's `backend.hcl` are local and gitignored, copied from committed `.example` files; the generator and the dbt profile require `MDP_GCP_PROJECT` (no default), like the API's `MDP_BQ_PROJECT` (D45); docs write `<project-id>`. CI's `dbt parse` sets a placeholder project, since parsing never connects | Accepted | The repo is public: it links to no cloud account, and nobody's run lands in a project by default |
| D57 | The repo is public, starting from one fresh commit. A ruleset on `main` requires the three CI checks and blocks force pushes and deleting `main` | Accepted | The public history starts clean, with no working notes or account details. Public repositories allow rulesets on GitHub Free, which closes D55 |

*Still to design (technical plan):* LLM integration: v2 (D31).
