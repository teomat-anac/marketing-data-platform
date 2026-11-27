"""Seeded simulated marts, for running the API locally before the real marts exist.

The shape follows the mart schema (architecture.md §2): 85 days × 9 channels, zero-filled,
with the `add_to_cart` tracking gap (D20). The volumes are loosely based on the exploration
figures (data-sources.md §5) and Paid Search costs follow the generator settings (D21), so
the numbers look plausible. They are not the real data: never use them to check results.
"""

import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mdp_api.marts import FUNNEL_STEPS, ChannelDay, FunnelDay
from mdp_api.periods import Period
from mdp_api.repository.memory import InMemoryRepository

DATA_RANGE = Period(date(2020, 11, 1), date(2021, 1, 24))  # D18
ADD_TO_CART_RECORDED_FROM = date(2020, 11, 26)  # D20
CENT = Decimal("0.01")
# Share of Paid Search sessions that ads brought themselves (own source), not credited by D16:
# 12,173 of 13,896 (data-sources.md §5). Clicks follow these sessions (D21).
PAID_OWN_SOURCE_SHARE = 0.876


@dataclass(frozen=True)
class ChannelProfile:
    name: str
    is_paid: bool
    sessions_per_day: float
    conversion_rate: float
    order_value: float


# Daily averages over the 85 days, rounded from data-sources.md §5 (final figures).
PROFILES = (
    ChannelProfile("Organic Search", False, 1715, 0.016, 66),
    ChannelProfile("Direct", False, 921, 0.0067, 68),
    ChannelProfile("Unassigned", False, 645, 0.010, 64),
    ChannelProfile("Referral", False, 465, 0.036, 68),
    ChannelProfile("Paid Search", True, 163, 0.006, 75),
    ChannelProfile("Affiliates", False, 14, 0.0017, 84),
    ChannelProfile("Organic Social", False, 2.6, 0.009, 27),
    ChannelProfile("Email", False, 1.6, 0.19, 78),
    ChannelProfile("Organic Video", False, 0.4, 0.028, 34),
)


def season(day: date) -> float:
    """Traffic multiplier: Black Friday week, the December peak, the Christmas dip, January."""
    if date(2020, 11, 27) <= day <= date(2020, 11, 30):  # Black Friday to Cyber Monday
        return 1.7
    if date(2020, 12, 1) <= day <= date(2020, 12, 18):
        return 1.3
    if date(2020, 12, 24) <= day <= date(2020, 12, 26):
        return 0.6
    if day >= date(2021, 1, 1):
        return 0.8
    return 1.0


def _count(rng: random.Random, expected: float) -> int:
    """A whole count with the given expected value: the fraction becomes a coin flip."""
    whole = int(expected)
    return whole + (rng.random() < expected - whole)


def _money(value: float) -> Decimal:
    return Decimal(f"{value:.2f}").quantize(CENT)


def fake_marts(seed: int = 42) -> tuple[list[ChannelDay], list[FunnelDay]]:
    """Both marts for the full data range. The same seed always gives the same rows."""
    rng = random.Random(seed)
    channel_rows: list[ChannelDay] = []
    funnel_rows: list[FunnelDay] = []
    for day in DATA_RANGE.dates():
        for p in PROFILES:
            sessions = _count(rng, p.sessions_per_day * season(day) * rng.uniform(0.85, 1.15))
            orders = min(
                sessions, _count(rng, sessions * p.conversion_rate * rng.uniform(0.7, 1.3))
            )
            revenue = _money(orders * p.order_value * rng.uniform(0.8, 1.2))
            clicks = impressions = 0
            spend = Decimal(0)
            if p.is_paid:  # generator settings, D21
                clicks = round(sessions * PAID_OWN_SOURCE_SHARE * rng.uniform(1.05, 1.15))
                impressions = round(clicks / (0.03 * rng.uniform(0.9, 1.1)))
                spend = _money(clicks * 1.00 * rng.uniform(0.85, 1.15))
            channel_rows.append(
                ChannelDay(
                    day, p.name, p.is_paid, sessions, orders, revenue, clicks, impressions, spend
                )
            )

            begin_checkout = max(orders, _count(rng, sessions * rng.uniform(0.06, 0.10)))
            add_to_cart = max(begin_checkout, _count(rng, sessions * rng.uniform(0.10, 0.15)))
            view_item = max(add_to_cart, _count(rng, sessions * rng.uniform(0.45, 0.60)))
            reached = (sessions, view_item, add_to_cart, begin_checkout, orders)
            for number, (step, count) in enumerate(
                zip(FUNNEL_STEPS, reached, strict=True), start=1
            ):
                tracked = step != "add_to_cart" or day >= ADD_TO_CART_RECORDED_FROM
                funnel_rows.append(
                    FunnelDay(day, p.name, step, number, count if tracked else None, tracked)
                )
    return channel_rows, funnel_rows


def fake_repository(seed: int = 42) -> InMemoryRepository:
    return InMemoryRepository(*fake_marts(seed))
