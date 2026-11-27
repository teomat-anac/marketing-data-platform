# Marketing Data Platform on GCP

A marketing data platform on Google Cloud. It joins GA4 e-commerce data with ad spend, models them in BigQuery with dbt and serves channel KPIs through an API on Cloud Run. All infrastructure is managed with Terraform, and every pull request is checked in GitHub Actions.

**Questions it answers for a marketing manager:**
- How much did we spend per channel, and how much did each channel sell?
- Which channel pays back best (ROAS)?
- Where do users drop out of the purchase funnel?

## Architecture

```
 GA4 export (public dataset)            Ad spend (synthetic)
                │                               │
                ▼                               ▼
   BigQuery:  raw ──── dbt ────▶ staging ──── dbt ────▶ marts
                                                          │
                                                          ▼
                                            FastAPI on Cloud Run
                                         /kpi  /funnel  (/insights ──▶ LLM: v2)

   Terraform provisions the GCP resources; GitHub Actions runs CI.
```

- **Data:** Google's public GA4 sample (a real online shop, Nov 2020 – Jan 2021) and synthetic ad costs that follow its real paid traffic, so ROAS moves with real sales ([`data-sources.md`](docs/data-sources.md)).
- **Modelling:** dbt layers raw → staging → intermediate → marts, with a documented attribution rule (last non-direct click on sessions), deduplicated orders and channel rules kept as data ([`architecture.md`](docs/architecture.md) §2).
- **API:** FastAPI on Cloud Run, reachable only with a Google identity token; parameterised, byte-capped BigQuery queries ([`architecture.md`](docs/architecture.md) §4).
- **Cost:** the whole platform runs within the GCP Free Tier ([`costs.md`](docs/costs.md)).

## Results

Built from the real GA4 sample, 1 Nov 2020 – 24 Jan 2021 (85 days):

| | |
|---|---|
| Sessions | 333,787 across 9 channels |
| Orders | 5,030 unique orders (from 5,692 raw `purchase` events, with duplicates removed) |
| Revenue | $335,469, without tax |
| Paid Search | $13,334 of synthetic spend, ROAS 0.47 overall, 0.17–0.89 week by week |
| Season | best day Cyber Monday ($11,910); best week from 7 Dec ($59.2k); a dip over Christmas |
| Funnel | visit 333,787 → view item 70,833 → add to cart 13,488 → checkout 10,526 → purchase 4,538 |

**Quality:** 76 dbt data tests and 2 dbt unit tests guard keys, totals and the attribution and order rules; over 100 pytest tests cover the API and the cost generator. CI runs lint, tests, `dbt parse` and `terraform validate` as three required checks on every pull request.

## Try it in 2 minutes

The API runs locally on seeded simulated data with the same schema as the marts: no GCP account needed. Requires [uv](https://docs.astral.sh/uv/).

```sh
cd api
uv sync
MDP_DATA_BACKEND=fake uv run uvicorn mdp_api.main:create_app --factory
```

Then open http://localhost:8000/docs, or:

```sh
curl "localhost:8000/kpi?start=2020-12-08&end=2020-12-14&channel=Paid%20Search"
```

The same request on the deployed API, reading the real marts (abridged):

```json
{
  "period": {"start": "2020-12-08", "end": "2020-12-14", "days": 7},
  "previous_period": {"start": "2020-12-01", "end": "2020-12-07", "days": 7, "available": true, "reason": null},
  "channel": "Paid Search",
  "channels": [{
    "channel": "Paid Search",
    "is_paid": true,
    "kpis": {
      "orders":  {"value": 17,      "previous": 11,      "change": 6,      "change_pct": 0.5455},
      "revenue": {"value": 1522.0,  "previous": 841.0,   "change": 681.0,  "change_pct": 0.8098},
      "spend":   {"value": 1618.05, "previous": 1338.34, "change": 279.71, "change_pct": 0.209},
      "roas":    {"value": 0.94,    "previous": 0.63,    "change": 0.31,   "change_pct": 0.4921},
      "cpa":     {"value": 95.18,   "previous": 121.67,  "change": -26.49, "change_pct": -0.2177},
      "...": "sessions, clicks, impressions, conversion_rate, aov"
    }
  }],
  "total": {"...": "the same KPIs over all channels in scope"}
}
```

Other endpoints: `/kpi/daily` (one row per day and channel) and `/funnel` (sessions per step and step-to-step rates). More in [`api/README.md`](api/README.md).

## Run it in your own GCP project

The repo names no GCP project. Copy the `.example` files and set your project ID ([`terraform/README.md`](terraform/README.md), "Configure your project"), then export `MDP_GCP_PROJECT` for the pipeline ([`pipeline/README.md`](pipeline/README.md)).

## Documentation

| File | Contents |
|---|---|
| [`docs/requirements.md`](docs/requirements.md) | What the product must do: users, user stories, functional and non-functional requirements. |
| [`docs/architecture.md`](docs/architecture.md) | How it's built: components, data layers, data flow, API, infrastructure, CI, and the decision log. |
| [`docs/data-sources.md`](docs/data-sources.md) | The data (real GA4 sample, synthetic ad costs), its limits, and the exploration behind every data rule. |
| [`docs/costs.md`](docs/costs.md) | Running costs: Free Tier limits per service and the guardrails that keep usage within them. |
| [`docs/glossary.md`](docs/glossary.md) | Marketing metrics, analytics concepts and technical terms. |
| [`api/`](api/) | The KPI API: run, test, build and deploy. |
| [`pipeline/`](pipeline/) | The dbt models and the cost generator: run and test. |
| [`terraform/`](terraform/) | The GCP infrastructure: create, tear down and recover an environment. |
| [`analysis/exploration/`](analysis/exploration/) | The SQL queries behind the data exploration. |

## What's next

- **Nightly refresh:** the pipeline as a Cloud Run job, triggered by Cloud Scheduler.
- **Keyless deploys from CI:** Workload Identity Federation, `terraform plan` on pull requests, deploy on merge.
- **LLM commentary (v2):** an `/insights` endpoint that explains the week's numbers in plain language, using only figures from the data.
- **Monitoring and alerts:** pipeline failures and data anomalies.
- **Dashboard and weekly report** for non-technical users.

## Stack

GCP (BigQuery, Cloud Run, Artifact Registry, Cloud Build) · Terraform · dbt · Python 3.12 · FastAPI · Docker · GitHub Actions

Built with Claude Code as the coding agent, under guardrails that make every apply, deploy and IAM change ask first; design decisions are recorded in [`architecture.md`](docs/architecture.md) §6.

## License

[MIT](LICENSE)
