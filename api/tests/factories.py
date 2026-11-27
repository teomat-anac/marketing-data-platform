"""Small builders for hand-made mart rows, so each test shows only the values it checks."""

from datetime import date
from decimal import Decimal

from mdp_api.marts import FUNNEL_STEPS, ChannelDay, FunnelDay


def day(value: str) -> date:
    return date.fromisoformat(value)


def channel_day(
    on: str,
    channel: str = "Paid Search",
    *,
    sessions: int = 0,
    orders: int = 0,
    revenue: str = "0",
    clicks: int = 0,
    impressions: int = 0,
    spend: str = "0",
) -> ChannelDay:
    return ChannelDay(
        date=day(on),
        channel=channel,
        is_paid=channel == "Paid Search",
        sessions=sessions,
        orders=orders,
        revenue=Decimal(revenue),
        clicks=clicks,
        impressions=impressions,
        spend=Decimal(spend),
    )


def funnel_day(on: str, step: str, sessions: int | None, channel: str = "Direct") -> FunnelDay:
    """A funnel row; `sessions=None` means the step wasn't recorded that day."""
    return FunnelDay(
        date=day(on),
        channel=channel,
        step=step,
        step_number=FUNNEL_STEPS.index(step) + 1,
        sessions=sessions,
        is_tracked=sessions is not None,
    )
