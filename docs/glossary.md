# Glossary and tools

The metrics, concepts and tools used in the project, with the meaning they have here.
Where the data comes from (GA4, synthetic ad costs) is covered in [`data-sources.md`](data-sources.md).

---

## 1. Marketing metrics

Running example for this section: **Paid Search, one day**

| Data point | Value | Source |
|---|---|---|
| Impressions (ad shown) | 20,000 | ad platform (synthetic) |
| Clicks on the ad | 550 | ad platform (synthetic) |
| Spend | $440 | ad platform (synthetic) |
| Sessions on the site | 500 | GA4 (real) |
| Purchases | 30 | GA4 (real) |
| Revenue | $3,000 | GA4 (real) |

| Acronym | Name | Formula | Example | How to read it |
|---|---|---|---|---|
| **ROAS** | Return On Ad Spend | revenue ÷ spend | 3,000 ÷ 440 = **6.8** | Every dollar spent on ads brought back $6.80 in revenue. Higher is better. **The project's main metric.** |
| **CPA** | Cost Per Acquisition | spend ÷ purchases | 440 ÷ 30 = **$14.67** | Ad cost of one purchase. Lower is better. |
| **CPC** | Cost Per Click | spend ÷ clicks | 440 ÷ 550 = **$0.80** | Average price of one click. |
| **CTR** | Click-Through Rate | clicks ÷ impressions | 550 ÷ 20,000 = **2.75%** | How well the ad gets clicked. |
| **CR** | Conversion Rate | purchases ÷ sessions | 30 ÷ 500 = **6%** | How well the site turns visits into purchases. |
| **AOV** | Average Order Value | revenue ÷ purchases | 3,000 ÷ 30 = **$100** | Average value of an order. |
| **LTV** | Lifetime Value | total revenue from a customer over time | — | Listed as future work, not in the MVP. |
| **KPI** | Key Performance Indicator | — | ROAS, CPA, CR… | Generic term: "the numbers that matter". |

Notes:
- **ROAS ≠ ROI.** ROAS uses *revenue* and only ad spend; ROI uses *margin* and all costs. A ROAS of 3 can still lose money if margins are thin.
- Channels with no spend (Direct, Organic, Referral) have **no** ROAS or CPA (division by zero): in the project they are `NULL`, not 0.
- Clicks and sessions never match exactly: some clicks never become a session (page closed before loading, tracking blocked).
- **Purchases** are unique orders, not raw `purchase` events: GA4 can record the same order twice. Orders whose amount wasn't recorded still count, with revenue $0 (D17).
- **Revenue** is the value of the products sold, without tax and before refunds (D17).
- **Blended ROAS / CPA:** the same formulas over *all* channels: all revenue (or all orders) against all ad spend. The API's `total` row shows them. They describe the business as a whole, not what ads bring: most of that revenue is organic.
- **Previous period:** the period of the same length just before the chosen one (7 days → the 7 days before). The API compares every KPI with it (US-4).

---

## 2. Analytics concepts

| Term | Meaning |
|---|---|
| **Event** | A single action recorded by GA4: `page_view`, `add_to_cart`, `purchase`… The dataset has one row per event. |
| **Session** | A visit: a group of events from the same user, ending after 30 minutes of inactivity. Key: `user_pseudo_id` + `ga_session_id`. |
| **User** (`user_pseudo_id`) | A browser/device identified by a cookie. Not a person. |
| **Source / Medium** | Where traffic comes from. *Source* = the site or engine (`google`, `facebook`); *medium* = the type (`cpc` = paid, `organic`, `referral`, `(none)` = direct). |
| **Channel** (*channel grouping*) | A readable grouping of source/medium: Paid Search, Organic Search, Direct, Referral… We define it with a rule. This project uses nine of GA4's default channel names (D19). |
| **Unassigned** | GA4's name for traffic that matches no channel rule. Here it also holds the sample's hidden sources (`<Other>`, `(data deleted)`). |
| **Tracking gap** | A period when the site didn't record an event, e.g. `add_to_cart` in early November 2020. The data shows zero, but the truth is unknown, so the project marks it as "not recorded" (D20). |
| **Attribution** | The rule that decides which channel gets credit for a purchase. *Last click* = the last channel before the purchase; *first touch* = the channel the user first arrived from. This project uses last non-direct click on sessions (D16). |
| **Last non-direct click** | Last click, but a direct visit doesn't take the credit: it goes to the user's most recent earlier non-direct channel, within the lookback window. GA4 uses it for session traffic sources. |
| **Lookback window** | How far back an earlier visit can still receive credit. Here: 90 days. |
| **Self-referral** | A site showing up as its own traffic source, e.g. when visitors move between two of its domains. It carries no acquisition information, so it is ignored. |
| **Funnel** | The sequence of steps to a purchase (visit → view product → cart → checkout → purchase) and how many visits reach each step. This project counts sessions, not users (D12). |
| **Open funnel** | A session counts at a step if it reached that step, whether or not it went through the earlier steps. A *closed* funnel counts only sessions that took the steps in order. This project uses the open funnel (D12). |
| **UTM** | Parameters added to campaign links (`utm_source`, `utm_medium`, `utm_campaign`) from which GA4 derives source/medium/campaign. |
| **Paid / Organic** | Paid = traffic you pay for (ads, commissions). Organic = free traffic: search results, social posts, videos. In this project `is_paid` is true only for channels with ad cost data, so only for Paid Search. |

### Channels

The nine channels in this project, with GA4's default names (D19). The rules that assign them are in `data-sources.md` §5.

| Channel | Meaning |
|---|---|
| **Direct** | The visitor typed the address, used a bookmark, or the origin was lost (e.g. a link in an app). With last non-direct click, a session stays Direct only if the user had no earlier non-direct visit within the lookback window: it means "not traceable to any marketing". |
| **Paid Search** | Visits from ads on a search engine's results page, bought per click (CPC). In GA4: `google / cpc`. The only paid channel in this project's data. |
| **Organic Search** | Visits from unpaid search results (medium `organic`), earned through SEO. |
| **Organic Social** | Visits from unpaid links on social networks (Facebook, Instagram, LinkedIn, X/Twitter, Reddit…). |
| **Organic Video** | Visits from video platforms without ads; here YouTube. |
| **Referral** | Visits from a link on another website: a blog, a review site, a partner page. |
| **Email** | Visits from a link in an email, e.g. a newsletter. Email tools cost money, but there is no cost data for them, so the channel is unpaid here. |
| **Affiliates** | Visits from partner sites that are usually paid a commission on sales. Unpaid here (`is_paid` false): the sample has no cost for them and only 2 orders, so a ROAS would be noise (`data-sources.md` §5). |
| **Unassigned** | See above: traffic that matches no rule, here mostly the sample's hidden sources. A data-quality signal, not a marketing channel. |

Other GA4 channels not in this data: **Paid Social** (ads on social networks), **Display** (banner ads on other sites, e.g. Google's display network), **Paid Video** and **Paid Shopping**. Adding one is a change to the channel rules (`data-sources.md` §5).

### Analytics tools

| Acronym | Name | What it is |
|---|---|---|
| **GA4** | Google Analytics 4 | Google's tool for measuring what users do on a site or app. It can export every event to BigQuery: this is our source. |
| **UA** | Universal Analytics | GA4's predecessor, switched off by Google in 2023–24. Its BigQuery export has one row per session, with the channel already assigned. Checked as an alternative source and rejected (`data-sources.md` §5). |

---

## 3. Technical acronyms

| Acronym | Name | What it is |
|---|---|---|
| **MDP** | Marketing Data Platform | This project's name, used as the naming prefix of its resources (`mdp-api`, `mdp-build`, …). |
| **GCP** | Google Cloud Platform | Google's cloud. |
| **IaC** | Infrastructure as Code | Describing infrastructure in versioned files instead of clicking through a console. In the project: Terraform. |
| **CI/CD** | Continuous Integration / Continuous Delivery | CI = every change automatically runs lint and tests. CD = approved code is released automatically. |
| **IAM** | Identity and Access Management | Who can do what on which resources. On GCP: *roles* granted to *principals* (users, service accounts). |
| **SA** | Service Account | An identity for a program, not a person (e.g. "the API", "the pipeline"). |
| **WIF** | Workload Identity Federation | Lets GitHub Actions act on GCP without stored keys: GitHub presents a signed token and GCP exchanges it for short-lived credentials. |
| **OIDC** | OpenID Connect | The standard for the signed tokens WIF uses. |
| **ADC** | Application Default Credentials | How Google libraries find credentials by themselves: locally from `gcloud auth application-default login`, on GCP from the service account. |
| **Free Tier** | — | Monthly usage that GCP never bills, per billing account (e.g. 1 TiB of BigQuery queries). It has no end date. The project stays within it: see [`costs.md`](costs.md). |
| **ASGI** | Asynchronous Server Gateway Interface | The standard between a Python web server (uvicorn) and the app (FastAPI); the async successor of WSGI. |
| **ELT** | Extract, Load, Transform | Load raw data into the warehouse first, then transform it there with SQL. This is our pattern (raw → staging → marts). ETL transforms before loading. |
| **DWH** | Data Warehouse | A database built for analytics over large volumes (BigQuery). |
| **Mart** | Data mart | A final table ready for consumers: one row per day and channel with the additive parts of the KPIs (sessions, orders, revenue, spend…). Ratios such as ROAS are computed on request (D22). |
| **LLM** | Large Language Model | Models such as Claude or Gemini. In v2 they write the commentary in `/insights` (D31). |
| **RAG** | Retrieval-Augmented Generation | Search for relevant documents first and put them in the prompt. Not in the MVP. |
| **MCP** | Model Context Protocol | A standard for exposing tools and data to an LLM agent. A possible post-MVP extension. |
| **ADR** | Architecture Decision Record | A short note recording a technical decision and its reason. Here: the D-numbered rows of `architecture.md` §6. |
| **SHA** | — | A Git commit identifier; used as the Docker image tag, and to pin each GitHub Action in CI to one exact commit (D54). |
| **Workflow / job / check (GitHub Actions)** | — | A *workflow* is a YAML file in `.github/workflows/` that runs on events such as a pull request. It has *jobs*, each on a fresh runner (a short-lived VM). Each job shows on the pull request as a *check*, green or red. Here: one workflow, three jobs (D52). |
| **Branch protection / ruleset / required check** | — | GitHub settings that block a merge until named checks are green. Here a ruleset on `main` requires the three CI checks (D57). |
| **Action pinning** | — | Referring to a GitHub Action by its full commit SHA instead of a tag like `v7`. A tag can be moved to other code; a SHA can't (D54). |
| **Concurrency group (GitHub Actions)** | — | A name shared by runs that mustn't overlap. GitHub keeps at most one running and one pending run per group, and a newer pending run cancels the older one; with `cancel-in-progress` it also cancels the one running. Here: one group per pull request, so a new push stops the old run; every run on `main` has its own group, so no merge's run is dropped (`architecture.md` §5). |
| **MVP** | Minimum Viable Product | The smallest version that works end to end. |
| **Terraform state** | — | The file in which Terraform records what it created and each resource's real ID, so the next `plan` can compare code with reality. Here: in a GCS bucket, versioned. |
| **Backend** | — | Where Terraform keeps the state: locally or remotely (`gcs` here). A remote backend also locks the state during a run. |
| **Partial backend configuration** | — | Backend settings given at `terraform init -backend-config=<file>` instead of written in the code. Here the state bucket's name comes from a gitignored `backend.hcl`, so the repo names no GCP project (D56). |
| **Bootstrap** | — | The small Terraform root that creates the state bucket. It keeps its own state locally, since the bucket can't hold the state of its own creation. |
| **Terraform root** | — | A folder Terraform runs in (`init`, `plan`, `apply`), with its own state. Here: `terraform/bootstrap/` and `terraform/envs/dev/`. |
| **Terraform lock file** | — | `.terraform.lock.hcl`: the exact provider version and its checksums, committed so every machine and CI installs the same build (like `uv.lock` or `package-lock.json`). |
| **Provider** | — | The Terraform plugin that talks to a cloud's API (`hashicorp/google`). Its schema lists every resource and attribute. |
| **Label** | — | A key=value pair on a GCP resource (`env=dev`), used to filter billing reports. |
| **dbt seed** | — | A small CSV file in the dbt project, loaded into BigQuery as a table. Used for the channel list, the channel rules (D19) and the tracking gaps (D20). |
| **dbt model** | — | One `SELECT` in a `.sql` file; dbt wraps it in `CREATE VIEW` or `CREATE TABLE` and runs it. Models read other models with `ref()`, which gives dbt the order to build them in. |
| **dbt source** | — | A table dbt reads but doesn't build, declared in YAML and read with `source()`: here the GA4 sample and `raw.ad_spend`. |
| **Materialization** | — | How dbt stores a model: `view` (stores nothing, re-runs on every read), `table` (stores the result), and others such as `incremental`. |
| **Data test (dbt)** | — | A query on built data that returns the rows breaking a rule (`unique`, `not_null`, or custom SQL); the test passes when it returns none. |
| **Unit test (dbt)** | — | Runs a model's SQL on hand-made input rows and compares the output with expected rows, without touching the real data. Here: the attribution and order rules (D16, D17). |
| **dbt package** | — | Reusable dbt macros and tests, installed with `dbt deps` and pinned in `package-lock.yml`. Here: `dbt_utils`, for multi-column unique keys and range checks. |
| **Partitioning / clustering** | — | BigQuery table settings. *Partitioned* by date: a query filtered on dates reads only those days. *Clustered* by channel: rows are sorted by channel within each partition. Both cut the bytes billed. |
| **Load job** | — | BigQuery's batch way to write a file or rows into a table, free of charge; `WRITE_TRUNCATE` replaces the table in one step. Streaming inserts are the billed alternative. |
| **RE2** | — | Google's regular-expression syntax, used by BigQuery's `REGEXP_CONTAINS`. The channel rules are RE2 patterns, matched ignoring case with the `(?i)` flag (D38). It has no look-ahead or back-references. |
| **Indirect selection** (dbt) | — | Which tests `dbt build --select …` runs along with the selected models. `buildable` runs a test only when every model it reads is selected or built before them, so a partial build never tests a model it didn't build (D42). |
| **Wildcard table** | — | `events_*` reads every daily GA4 table at once; `_TABLE_SUFFIX` holds each table's date, so a filter on it skips the other days' tables. |
| **Job labels** (BigQuery) | — | Key=value pairs on a query job. The API labels its queries `component=api`, so their bytes can be summed in `INFORMATION_SCHEMA.JOBS`. |
| **Identity token** | — | A short-lived token signed by Google that says who the caller is (a JWT). `gcloud auth print-identity-token` prints one for the logged-in user. Cloud Run checks it before a request reaches the container. |
| **Invoker** (`run.routes.invoke`) | — | The permission to call a Cloud Run service. `roles/run.invoker` grants it on one service; the Owner and Editor roles include it. |
| **Revision** (Cloud Run) | — | A fixed snapshot of a service's image and settings. Each deploy creates one and sends the traffic to it; an older one can take the traffic back. |
| **Placeholder image** | — | Google's public "hello" container (`us-docker.pkg.dev/cloudrun/container/hello`). Terraform creates the Cloud Run service with it, before our first image exists. |
| **Service agent** | — | A service account that Google creates and manages when an API is switched on, so the service can act in the project: e.g. Cloud Run pulling images from Artifact Registry. Not to be confused with the project's own service accounts. |
| **Multi-stage build** | — | A Dockerfile with a build stage (tools, compilers) and a clean final stage; only the result is copied over, so the image stays small. |
| **Image digest** | — | `sha256:…`, the hash of an image's content. A tag can be moved to another image; a digest can't, so pinning by digest fixes exactly what is pulled. |
| **Cleanup policy** (Artifact Registry) | — | Rules that delete old image versions in the background. Here: keep the 3 newest and the one tagged `live` (the deployed image), delete the rest (D49). |
| **Staging bucket** (Cloud Build) | — | Where `gcloud builds submit` uploads the source before the build. Here our own `us-central1` bucket, not the default `<project>_cloudbuild` one. |

---

## 4. Tools

### GCP services

| Tool | What it is | Role in the project | MVP |
|---|---|---|---|
| **BigQuery** | Serverless data warehouse: SQL over large volumes, billed per byte scanned. | Holds raw, cleaned and KPI data. Reads the public GA4 dataset. | ✅ |
| **Cloud Storage (GCS)** | Object storage. | Stores the Terraform *state* and the sources staged for Cloud Build. | ✅ |
| **Cloud Run (service)** | Runs a container that answers HTTP requests; scales to zero when idle. | Hosts the FastAPI API (`mdp-api`), callable only with an identity token. | ✅ |
| **Cloud Run (job)** | Runs a container until the work is done, then stops. | The nightly pipeline (spend + dbt). | later |
| **Artifact Registry** | Docker image registry. | Stores the API image. | ✅ |
| **Cloud Resource Manager** | The API for projects, folders and their IAM policies. Terraform calls it to grant project-level roles. | Enabled so Terraform can grant `bigquery.jobUser` on the project. | ✅ |
| **Cloud Build** | Managed build service: builds a Docker image from the source in Google's cloud. | Builds the API image from `api/cloudbuild.yaml`, as the `mdp-build` service account, so no local Docker is needed (D30, D47). | ✅ |
| **Cloud Scheduler** | Managed cron. | Triggers the job every night. | later |
| **Vertex AI** | Google's AI platform; its *Model Garden* offers Google models (Gemini) and third-party ones (Claude). | LLM call for `/insights`. | v2 (D31) |
| **IAM / Service Accounts** | Identities and permissions. | One SA per component, least privilege. | ✅ |
| **Cloud Logging / Monitoring** | Logs, metrics, alerts. | API request logs and build logs; alerts later. | partial |
| **Billing budget** | Alert when spend crosses a threshold. | Cost protection. | ✅ |

### Development tools

| Tool | What it is | Role in the project | MVP |
|---|---|---|---|
| **gcloud** | Google Cloud CLI. | Login, manual commands, manual deploys. | ✅ |
| **Terraform** | HashiCorp's IaC tool: describe resources in `.tf` files, `plan` shows what will change, `apply` does it. The *state* remembers what it created. | Creates datasets, service accounts, permissions, Cloud Run, registry. | ✅ |
| **dbt** (data build tool) | Transformations as versioned SQL files, with dependencies between models and data tests. It doesn't move data: it generates and runs SQL inside BigQuery. | raw → staging → marts, tests on keys and values. | ✅ |
| **Python 3.12** | — | Spend generator and API. | ✅ |
| **uv** | Very fast Python package and environment manager (alternative to pip + venv). | Pinned dependencies. | ✅ |
| **FastAPI** | Python web framework; generates OpenAPI docs automatically. | The API. | ✅ |
| **Starlette** | The web toolkit FastAPI is built on: routing, requests and responses, middleware, the test client. Comes with FastAPI. | Underneath the API; its test client runs the API tests. | ✅ |
| **uvicorn** | ASGI server: listens on a port and hands requests to the app (like gunicorn for WSGI apps). | Runs the API locally, and later in the container. | ✅ |
| **httpx** | HTTP client library; Starlette's test client uses it to call the app in memory. Starlette now suggests `httpx2`; the project stays on `httpx` for now. | API tests. | ✅ |
| **Pydantic / pydantic-settings** | Data validation via type hints; *settings* reads configuration from environment variables. | API response models and configuration. | ✅ |
| **google-cloud-bigquery** | Python client library for BigQuery. | Parameterised queries from the API. | ✅ |
| **anthropic[vertex]** / **google-genai** | SDKs for calling Claude or Gemini on Vertex AI. | `LLMClient` implementations. | v2, one of them |
| **Docker** | Containers. | The API image (`api/Dockerfile`), built by Cloud Build; Docker isn't installed locally. | ✅ |
| **pytest** | Python testing. | Tests on hand-made and simulated mart rows; a simulated LLM in v2. | ✅ |
| **ruff** | Python linter and formatter. | Code style, in CI. | ✅ |
| **Dependabot / Renovate** | Bots that open pull requests to bump pinned versions: GitHub Actions SHAs, lock files, Docker digests. Dependabot is built into GitHub; Renovate is a separate app with more options. | Dependabot alerts flag known vulnerabilities in the pinned dependencies (D54); automatic update pull requests aren't enabled. | alerts |
| **GitHub Actions** | GitHub's CI/CD. | MVP: lint, tests, `dbt parse` and `terraform validate` on every pull request to `main` (`.github/workflows/ci.yml`, D52). Later: plan, apply, deploy. | partial |
