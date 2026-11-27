"""Settings of the pipeline: where it runs, and the cost generator's rules (D21).

The generator's numbers come from public benchmarks, not from a target ROAS
(data-sources.md §5, "Decision: generator settings").
"""

import os
from dataclasses import dataclass
from decimal import Decimal

# The GCP project, required: the dbt profile reads the same variable. The repo names no
# project, so a run can't land in one by accident.
PROJECT_ENV = "MDP_GCP_PROJECT"

# BigQuery location of every dataset: the GA4 sample is in US (D7).
LOCATION = "US"

# Where the generator reads paid sessions from (built by dbt) and writes ad costs to.
SESSIONS_TABLE = "intermediate.int_ga4__sessions"
AD_SPEND_TABLE = "raw.ad_spend"

# Byte cap of the generator's query (docs/costs.md §1). It reads two columns of
# int_ga4__sessions, a few MB; BigQuery bills at least 10 MB per query.
MAX_BYTES_BILLED = 100_000_000

# Fixed seed: the same sessions always give the same costs (FR-5).
DEFAULT_SEED = 20201101


@dataclass(frozen=True)
class Campaign:
    """One ad campaign and the ranges its daily values are drawn from (D21).

    Each day: clicks = own-source sessions × a factor in `click_factor` (some clicks never
    become a visit); CPC = `cpc` × a factor in `cpc_factor`; CTR = `ctr` × a factor in
    `ctr_factor`; spend = clicks × CPC; impressions = clicks ÷ CTR.
    """

    channel: str
    name: str
    cpc: Decimal = Decimal("1.00")
    ctr: float = 0.03
    click_factor: tuple[float, float] = (1.05, 1.15)
    cpc_factor: tuple[float, float] = (0.85, 1.15)
    ctr_factor: tuple[float, float] = (0.9, 1.1)


# One campaign per paid channel (D21). Paid Search is the only paid channel in the data
# (D15); GA4 hides the real campaign names, so this one is made up.
CAMPAIGNS = (Campaign(channel="Paid Search", name="Search - Generic"),)


def project() -> str | None:
    return os.environ.get(PROJECT_ENV) or None
