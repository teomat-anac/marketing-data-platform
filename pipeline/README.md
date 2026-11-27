# Data pipeline

The dbt models that turn the GA4 sample and the ad costs into the marts, and the synthetic ad-cost generator.
Design: [`docs/architecture.md`](../docs/architecture.md) §2–3 (layers, data flow) and D36–D43; data rules: [`docs/data-sources.md`](../docs/data-sources.md) §3 and §5.

```
pipeline/
  dbt/                 the dbt project (run dbt from this folder)
    models/staging/    stg_ga4__events, stg_ads__spend: views, no business rules
    models/intermediate/ int_ga4__orders, int_ga4__sessions: tables (D16, D17), with unit tests
    models/marts/      mart_channel_daily, mart_funnel_daily: the API's contract (D22)
    seeds/             channels, channel_rules, tracking_gaps: rules kept as data (D19, D20)
    tests/             cross-model checks: row counts, totals that must match
  src/mdp_pipeline/    the cost generator and the mdp-pipeline command
  tests/               pytest for the generator
```

## Before the first run
- `gcloud auth application-default login` (dbt and the generator use your ADC credentials).
- `export MDP_GCP_PROJECT=<project-id>`: the project to run in. Required by the generator and the dbt profile, even for `dbt parse`; the repo names no project.
- The datasets `raw`, `staging`, `intermediate` and `marts` exist: Terraform creates them ([`terraform/`](../terraform/)).
- `uv sync` here, then `cd dbt && uv run dbt deps` (installs `dbt_utils`, pinned in `package-lock.yml`).

## Run everything
```sh
cd pipeline
uv run mdp-pipeline
```
It runs the three steps in the order the data needs (architecture.md §3):
1. `dbt build` of the seeds, GA4 staging and the intermediate models, with their tests;
2. the generator: reads own-source paid sessions per day, replaces `raw.ad_spend`;
3. `dbt build` of the cost staging and the marts, with every remaining test.

It stops at the first failure. A full run scans the GA4 sample twice, about 3 GB (free up to 1 TiB a month).

## Run one part
```sh
uv run mdp-generate --dry-run   # generate and print the totals, write nothing
uv run mdp-generate             # replace raw.ad_spend
cd dbt
uv run dbt build                # every model and test; needs raw.ad_spend to exist (one run of the generator)
uv run dbt build --select mart_channel_daily   # one model and its tests
```
On an empty project, a plain `dbt build` fails at `stg_ads__spend` until the generator has written `raw.ad_spend` once: run `mdp-pipeline` first.

## Settings
| What | Where | Default |
|---|---|---|
| GCP project | `MDP_GCP_PROJECT` (read by the generator and the dbt profile), or `--project` | **required** |
| dbt project folder for `mdp-pipeline` | `--dbt-dir`, else `MDP_DBT_DIR` (e.g. in a container image) | `pipeline/dbt` in this checkout |
| Data range, self-referral domains, attribution window | dbt variables in `dbt/dbt_project.yml` | 2020-11-01 – 2021-01-24, `googlemerchandisestore.com`, 90 days |
| Channel rules, paid channels, tracking gaps | seeds in `dbt/seeds/` | D19, D20 |
| Generator campaigns, CPC, CTR, click factor, seed | `src/mdp_pipeline/settings.py` | D21, seed `20201101` |
| Byte cap per query | `dbt/profiles.yml` (3 GB), `settings.py` (100 MB) | — |

## Checks
The same checks CI runs on every pull request to `main` (`.github/workflows/ci.yml`); none needs GCP credentials. `dbt parse` still needs `MDP_GCP_PROJECT` set (CI uses a placeholder). `--locked` fails on a stale `uv.lock` instead of updating it, as CI does:
```sh
uv run --locked pytest
uv run --locked ruff check
uv run --locked ruff format --check
cd dbt
uv run --locked dbt deps
git diff --exit-code -- package-lock.yml                # fails if deps rewrote the lock: commit it
uv run --locked dbt parse --no-partial-parse --warn-error  # full parse, so no warning is skipped
```

## Good to know
- **No tests on `stg_ga4__events`:** it's a view on the GA4 sample, so every query on it scans about 1.6 GB. The tests sit on the intermediate tables.
- **Unit tests own their inputs:** they carry their own rule rows and settings, so a client can change the seeds and variables without breaking them. `mdp-pipeline` parses the project in full on every build (`--no-partial-parse`), so an edited seed file is always picked up.
- **Channel rules** are RE2 regular expressions matched ignoring case, as GA4 does (`CPC` is Paid Search). Write special characters as classes (`[.]`, `[(]`): backslashes break in BigQuery string literals.
- **`self_referral_domains`** must be a list (`["myshop.com"]`); `[]` means no self-referrals. A plain string stops the build with an error, because Jinja would loop over its letters.
- **Dates** in the variables can be written with or without quotes. **`attribution_lookback_days`** must be a whole number of days, 0 or more; anything else (`"9O"`, `"90 days"`, empty) stops the build rather than being read as 0.
- **"Identical rows"**: two generator runs give the same rows in every column except `loaded_at`, the write time. Check with a fingerprint (capped, like every query: `docs/costs.md` §1):
  ```sh
  bq query --maximum_bytes_billed=100000000 --use_legacy_sql=false --location=US '
  select count(*), bit_xor(farm_fingerprint(to_json_string(
    struct(date, channel, campaign, impressions, clicks, spend)))) from raw.ad_spend'
  ```
