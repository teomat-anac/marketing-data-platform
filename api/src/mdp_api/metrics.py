"""KPI calculations (FR-7): pure functions on mart rows, with exact decimals and no rounding.

- Ratios for a period are computed from the period's totals, never by averaging daily ratios.
- A ratio whose denominator is 0 is None ("empty"), never 0: e.g. ROAS and CPA without spend.
- Rounding for display happens only when the response is built (`service`).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from mdp_api.marts import FUNNEL_STEPS, ChannelDay, FunnelDay
from mdp_api.periods import Period

ZERO = Decimal(0)

type Number = int | Decimal

# The KPIs reported per channel and period, in response order.
KPIS = (
    "sessions",
    "orders",
    "revenue",
    "spend",
    "clicks",
    "impressions",
    "roas",
    "cpa",
    "conversion_rate",
    "aov",
)


@dataclass(frozen=True, slots=True)
class Totals:
    """Sums of the additive mart columns over any set of rows: days, channels or both."""

    sessions: int = 0
    orders: int = 0
    revenue: Decimal = ZERO
    clicks: int = 0
    impressions: int = 0
    spend: Decimal = ZERO

    @classmethod
    def of(cls, rows: Iterable[ChannelDay]) -> Totals:
        sessions = orders = clicks = impressions = 0
        revenue = spend = ZERO
        for row in rows:
            sessions += row.sessions
            orders += row.orders
            revenue += row.revenue
            clicks += row.clicks
            impressions += row.impressions
            spend += row.spend
        return cls(sessions, orders, revenue, clicks, impressions, spend)

    @property
    def roas(self) -> Decimal | None:
        """Revenue ÷ spend. Empty without spend."""
        return self.revenue / self.spend if self.spend else None

    @property
    def cpa(self) -> Decimal | None:
        """Spend ÷ orders. Empty without spend, and without orders (no acquisition to price)."""
        return self.spend / self.orders if self.spend and self.orders else None

    @property
    def conversion_rate(self) -> Decimal | None:
        """Orders ÷ sessions, as a fraction."""
        return Decimal(self.orders) / self.sessions if self.sessions else None

    @property
    def aov(self) -> Decimal | None:
        """Average order value: revenue ÷ orders."""
        return self.revenue / self.orders if self.orders else None


@dataclass(frozen=True, slots=True)
class Change:
    """One KPI in the current period next to the previous period (US-4)."""

    value: Number | None
    previous: Number | None

    @property
    def change(self) -> Number | None:
        if self.value is None or self.previous is None:
            return None
        return self.value - self.previous

    @property
    def change_pct(self) -> Decimal | None:
        """Change as a fraction of the previous value. Empty when the previous value is 0."""
        change = self.change
        if change is None or not self.previous:
            return None
        return Decimal(change) / Decimal(self.previous)


def compare(current: Totals, previous: Totals | None) -> dict[str, Change]:
    """Every KPI of `current` next to `previous`; `previous` is None when it isn't available."""
    return {
        kpi: Change(getattr(current, kpi), getattr(previous, kpi) if previous else None)
        for kpi in KPIS
    }


@dataclass(frozen=True, slots=True)
class FunnelStep:
    step: str
    step_number: int
    sessions: int | None
    """Sessions that reached the step; None when the step wasn't recorded on some day."""
    untracked_days: int
    """Days of the period on which the step wasn't recorded."""
    rate_from_previous: Decimal | None
    """Sessions of this step ÷ sessions of the previous step; None for the first step."""

    @property
    def is_tracked(self) -> bool:
        return self.untracked_days == 0


def funnel(rows: Iterable[FunnelDay], period: Period, channels: Iterable[str]) -> list[FunnelStep]:
    """Open funnel for `period` and `channels` (D12): per step, the sessions that reached it.

    Sessions are summed over the days and channels in scope. A step not recorded on at least
    one day of the period is "not recorded" for the whole period (D20): summing only the
    recorded days would set part of the period against all of it in the conversion rates. For
    the same reason the rates into and out of that step are None. Every (day, channel) pair
    must have a recorded row: a missing row counts as not recorded, never as 0.
    """
    channels = tuple(channels)  # read once per day below, so a generator must not run dry
    expected = {(day, channel) for day in period.dates() for channel in channels}
    by_step: defaultdict[str, dict[tuple[date, str], FunnelDay]] = defaultdict(dict)
    for row in rows:
        if (row.date, row.channel) in expected:
            by_step[row.step][(row.date, row.channel)] = row

    steps: list[FunnelStep] = []
    previous_sessions: int | None = None
    for step_number, step in enumerate(FUNNEL_STEPS, start=1):
        step_rows = by_step[step]
        recorded = {
            pair for pair, r in step_rows.items() if r.is_tracked and r.sessions is not None
        }
        untracked_days = {day for day, _ in expected - recorded}
        sessions = None if untracked_days else sum(r.sessions or 0 for r in step_rows.values())
        rate = (
            Decimal(sessions) / previous_sessions
            if sessions is not None and previous_sessions
            else None
        )
        steps.append(FunnelStep(step, step_number, sessions, len(untracked_days), rate))
        previous_sessions = sessions
    return steps
