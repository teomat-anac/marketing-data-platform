"""Response models: the JSON contract of the API, also shown on the /docs page.

Number format: money and ROAS are rounded to 2 decimals, rates and % changes are fractions
with 4 decimals (0.015 = 1.5%). A ratio that can't be computed is null, never 0.
"""

from datetime import date

from pydantic import BaseModel, Field

type Value = int | float | None


class PeriodOut(BaseModel):
    start: date
    end: date
    days: int


class PreviousPeriodOut(PeriodOut):
    available: bool = Field(description="False when the period isn't entirely inside the data.")
    reason: str | None = Field(description="Why the comparison is missing, when it is.")


class Metric(BaseModel):
    """One KPI with its previous-period comparison (US-4)."""

    value: Value
    previous: Value = Field(description="Null when the previous period isn't available.")
    change: Value = Field(description="value - previous, as shown (both rounded).")
    change_pct: float | None = Field(
        description="change ÷ previous, as shown, as a fraction (0.25 = +25%). "
        "Null when the previous value is 0 or null."
    )


class KpiMetrics(BaseModel):
    sessions: Metric
    orders: Metric = Field(description="Unique orders (D17).")
    revenue: Metric = Field(description="USD, without tax and before refunds.")
    spend: Metric = Field(description="Ad cost in USD; 0 for channels that aren't paid.")
    clicks: Metric
    impressions: Metric
    roas: Metric = Field(description="Revenue ÷ spend. Null without spend.")
    cpa: Metric = Field(description="Spend ÷ orders. Null without spend or without orders.")
    conversion_rate: Metric = Field(description="Orders ÷ sessions, as a fraction.")
    aov: Metric = Field(description="Average order value: revenue ÷ orders.")


class ChannelKpis(BaseModel):
    channel: str
    is_paid: bool
    kpis: KpiMetrics


class KpiResponse(BaseModel):
    period: PeriodOut
    previous_period: PreviousPeriodOut
    channel: str | None = Field(description="The channel filter; null for all channels.")
    channels: list[ChannelKpis] = Field(description="One entry per channel, by revenue.")
    total: KpiMetrics = Field(
        description="All the channels above together. Its ROAS and CPA are blended: "
        "all revenue (or orders) against all ad spend."
    )


class DailyRow(BaseModel):
    date: date
    channel: str
    is_paid: bool
    sessions: int
    orders: int
    revenue: float
    spend: float
    clicks: int
    impressions: int
    roas: float | None
    cpa: float | None
    conversion_rate: float | None
    aov: float | None


class DailyResponse(BaseModel):
    period: PeriodOut
    channel: str | None = Field(description="The channel filter; null for all channels.")
    rows: list[DailyRow] = Field(description="One row per day and channel, zeros included.")


class FunnelStepOut(BaseModel):
    step: str
    step_number: int
    is_tracked: bool = Field(description="False when the step wasn't recorded on some day.")
    sessions: int | None = Field(
        description="Sessions that reached the step (open funnel). Null when not recorded."
    )
    untracked_days: int = Field(description="Days of the period without a record of the step.")
    rate_from_previous: float | None = Field(
        description="Sessions ÷ sessions of the previous step. Null for the first step, "
        "and next to a step that wasn't recorded."
    )


class FunnelResponse(BaseModel):
    period: PeriodOut
    channel: str | None = Field(description="The channel filter; null for all channels.")
    steps: list[FunnelStepOut]
