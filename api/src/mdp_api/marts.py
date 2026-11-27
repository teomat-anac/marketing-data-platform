"""Rows of the two marts, as fixed by the mart schema (architecture.md §2, D22).

The marts store additive values only; every ratio is computed in `metrics`.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# The funnel steps of `mart_funnel_daily`, in order; `step_number` is the position + 1.
FUNNEL_STEPS = ("visit", "view_item", "add_to_cart", "begin_checkout", "purchase")


@dataclass(frozen=True, slots=True)
class ChannelDay:
    """One row of `mart_channel_daily`: one day × one channel."""

    date: date
    channel: str
    is_paid: bool
    sessions: int
    orders: int
    revenue: Decimal
    clicks: int
    impressions: int
    spend: Decimal


@dataclass(frozen=True, slots=True)
class FunnelDay:
    """One row of `mart_funnel_daily`: one day × one channel × one funnel step.

    `sessions` is None, and `is_tracked` False, on days the step wasn't recorded (D20).
    """

    date: date
    channel: str
    step: str
    step_number: int
    sessions: int | None
    is_tracked: bool
