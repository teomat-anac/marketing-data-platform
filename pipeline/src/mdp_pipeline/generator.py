"""The synthetic ad-cost generator (FR-2, D3, D21): plain Python, no BigQuery.

Costs follow real paid traffic: each day's clicks come from the sessions that ads brought
(`own_channel`, D16), so ROAS moves with real sales and isn't fixed in advance.

Every row draws its random factors from its own generator, seeded with the run's seed and
the row's day, channel and campaign. The same inputs always give the same rows (FR-5), and a
row doesn't change when other days or channels are added or removed.
"""

import hashlib
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from mdp_pipeline.settings import Campaign

CENT = Decimal("0.01")


@dataclass(frozen=True, order=True)
class PaidSessions:
    """Sessions that a paid channel's ads brought on one day (own channel, D16)."""

    date: date
    channel: str
    sessions: int


@dataclass(frozen=True)
class AdSpendRow:
    """One row of `raw.ad_spend`: one day × channel × campaign, like an ad-platform export."""

    date: date
    channel: str
    campaign: str
    impressions: int
    clicks: int
    spend: Decimal


def generate(
    paid_sessions: Iterable[PaidSessions], campaigns: Sequence[Campaign], seed: int
) -> list[AdSpendRow]:
    """Ad cost rows for the given days of paid sessions, sorted by day and channel."""
    by_channel = _campaigns_by_channel(campaigns)
    rows = []
    for day in sorted(paid_sessions):
        if day.sessions < 0:
            raise ValueError(f"Negative sessions on {day.date} for {day.channel}.")
        campaign = by_channel.get(day.channel)
        if campaign is None:
            raise ValueError(f"No campaign set up for the paid channel {day.channel!r}.")
        if day.sessions == 0:
            continue  # no visits, no clicks: an ad export has no row
        rows.append(_row(day, campaign, seed))
    if not rows:  # also when every day has 0 sessions: an empty table would hide the problem
        raise ValueError("No paid sessions: build int_ga4__sessions with dbt first.")
    return rows


def _row(day: PaidSessions, campaign: Campaign, seed: int) -> AdSpendRow:
    rng = random.Random(_row_seed(seed, day.date, day.channel, campaign.name))
    # Always drawn in this order, so each factor keeps its value for a given row.
    click_factor = rng.uniform(*campaign.click_factor)
    cpc_factor = rng.uniform(*campaign.cpc_factor)
    ctr_factor = rng.uniform(*campaign.ctr_factor)

    clicks = _round_half_up(day.sessions * click_factor)
    cpc = campaign.cpc * Decimal(repr(cpc_factor))
    spend = (clicks * cpc).quantize(CENT, rounding=ROUND_HALF_UP)
    impressions = _round_half_up(clicks / (campaign.ctr * ctr_factor))
    return AdSpendRow(
        date=day.date,
        channel=day.channel,
        campaign=campaign.name,
        impressions=impressions,
        clicks=clicks,
        spend=spend,
    )


def _row_seed(seed: int, day: date, channel: str, campaign: str) -> int:
    """A stable integer for one row. hashlib, not hash(): hash() changes between runs."""
    key = f"{seed}|{day.isoformat()}|{channel}|{campaign}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def _round_half_up(value: float) -> int:
    return int(Decimal(repr(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _campaigns_by_channel(campaigns: Sequence[Campaign]) -> dict[str, Campaign]:
    by_channel: dict[str, Campaign] = {}
    for campaign in campaigns:
        if campaign.channel in by_channel:
            raise ValueError(f"More than one campaign for {campaign.channel!r}: not supported.")
        by_channel[campaign.channel] = campaign
    return by_channel
