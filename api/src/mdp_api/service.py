"""Builds each response: reads mart rows, runs the calculations, rounds for display.

Kept apart from the HTTP layer so that other callers (e.g. the `/insights` commentary,
v2, D31) get exactly the same numbers.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from mdp_api import metrics
from mdp_api.marts import ChannelDay
from mdp_api.metrics import KPIS, Number, Totals
from mdp_api.periods import Period
from mdp_api.repository import MartRepository
from mdp_api.schemas import (
    ChannelKpis,
    DailyResponse,
    DailyRow,
    FunnelResponse,
    FunnelStepOut,
    KpiMetrics,
    KpiResponse,
    Metric,
    PeriodOut,
    PreviousPeriodOut,
    Value,
)

# Decimal places shown per KPI; counts (sessions, orders, clicks, impressions) stay integers.
PLACES = {"revenue": 2, "spend": 2, "cpa": 2, "aov": 2, "roas": 2, "conversion_rate": 4}
PCT_PLACES = 4


def _quantize(value: Number | None, places: int | None) -> Number | None:
    """Rounds half up to `places` decimals; `places=None` means a count (an integer)."""
    if value is None:
        return None
    if places is None:
        return int(value)
    rounded = Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return abs(rounded) if rounded == 0 else rounded  # a tiny drop shows 0, not -0.0


def _json(value: Number | None) -> Value:
    return float(value) if isinstance(value, Decimal) else value


def _round(value: Number | None, places: int | None) -> Value:
    return _json(_quantize(value, places))


def _period_out(period: Period) -> PeriodOut:
    return PeriodOut(start=period.start, end=period.end, days=period.days)


def _kpi_metrics(current: Totals, previous: Totals | None) -> KpiMetrics:
    """Every KPI next to the previous period. The change and the % change are computed from
    the values as shown (rounded), so the response always adds up: no +30,000% next to a
    previous value shown as 0.
    """
    fields = {}
    for kpi, change in metrics.compare(current, previous).items():
        places = PLACES.get(kpi)
        shown_value = _quantize(change.value, places)
        shown_previous = _quantize(change.previous, places)
        shown_change = shown_pct = None
        if shown_value is not None and shown_previous is not None:
            shown_change = shown_value - shown_previous
            if shown_previous:
                shown_pct = Decimal(shown_change) / Decimal(shown_previous)
        fields[kpi] = Metric(
            value=_json(shown_value),
            previous=_json(shown_previous),
            change=_json(shown_change),
            change_pct=_round(shown_pct, PCT_PLACES),
        )
    return KpiMetrics(**fields)


def _scope(repository: MartRepository, channel: str | None) -> dict[str, bool]:
    """The channels a request covers, with their `is_paid` flag."""
    channels = repository.channels()
    return {channel: channels[channel]} if channel else channels


def kpi_report(repository: MartRepository, period: Period, channel: str | None) -> KpiResponse:
    """KPIs per channel and in total for `period`, next to the previous period (US-1, US-4)."""
    previous = period.previous()
    data_range = repository.data_range()
    has_previous = data_range.contains(previous)

    # One read covers both periods: with BigQuery that's one query instead of two.
    read_from = previous.start if has_previous else period.start
    rows = repository.channel_daily(Period(read_from, period.end), channel)
    current_rows: defaultdict[str, list[ChannelDay]] = defaultdict(list)
    previous_rows: defaultdict[str, list[ChannelDay]] = defaultdict(list)
    for row in rows:
        (current_rows if row.date in period else previous_rows)[row.channel].append(row)

    def previous_totals(channel_rows: list[ChannelDay]) -> Totals | None:
        return Totals.of(channel_rows) if has_previous else None

    # Every channel in scope is listed, even one without rows (a mart that isn't zero-filled),
    # so the channels always add up to the total; a side without rows counts as zero.
    scope = _scope(repository, channel)
    current_by_channel = {name: Totals.of(current_rows[name]) for name in scope}
    ordered = sorted(scope, key=lambda name: (-current_by_channel[name].revenue, name))
    channels = [
        ChannelKpis(
            channel=name,
            is_paid=scope[name],
            kpis=_kpi_metrics(current_by_channel[name], previous_totals(previous_rows[name])),
        )
        for name in ordered
    ]
    all_previous = [r for rows in previous_rows.values() for r in rows]
    total = _kpi_metrics(
        Totals.of(r for rows in current_rows.values() for r in rows), previous_totals(all_previous)
    )

    reason = None
    if not has_previous:
        reason = (
            f"The previous period starts before the first day of data ({data_range.start}), "
            "so there is nothing to compare with."
        )
    return KpiResponse(
        period=_period_out(period),
        previous_period=PreviousPeriodOut(
            **_period_out(previous).model_dump(), available=has_previous, reason=reason
        ),
        channel=channel,
        channels=channels,
        total=total,
    )


def daily_report(repository: MartRepository, period: Period, channel: str | None) -> DailyResponse:
    """The KPIs day by day and channel by channel (US-2). Every day × channel in scope has a
    row: one missing from the mart is filled with zeros, so series never have gaps.
    """
    scope = _scope(repository, channel)
    by_key = {(r.date, r.channel): r for r in repository.channel_daily(period, channel)}
    rows = []
    for day in period.dates():
        for name, is_paid in scope.items():
            mart_row = by_key.get((day, name))
            totals = Totals.of([mart_row]) if mart_row else Totals()
            rows.append(
                DailyRow(
                    date=day,
                    channel=name,
                    is_paid=is_paid,
                    **{kpi: _round(getattr(totals, kpi), PLACES.get(kpi)) for kpi in KPIS},
                )
            )
    return DailyResponse(period=_period_out(period), channel=channel, rows=rows)


def funnel_report(
    repository: MartRepository, period: Period, channel: str | None
) -> FunnelResponse:
    """Sessions reaching each funnel step, with step-to-step rates (US-3)."""
    steps = [
        FunnelStepOut(
            step=s.step,
            step_number=s.step_number,
            is_tracked=s.is_tracked,
            sessions=s.sessions,
            untracked_days=s.untracked_days,
            rate_from_previous=_round(s.rate_from_previous, PCT_PLACES),
        )
        for s in metrics.funnel(
            repository.funnel_daily(period, channel), period, _scope(repository, channel)
        )
    ]
    return FunnelResponse(period=_period_out(period), channel=channel, steps=steps)
