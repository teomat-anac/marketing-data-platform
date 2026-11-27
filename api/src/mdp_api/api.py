"""HTTP endpoints. Each one validates the request, then delegates to `service`."""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError

from mdp_api import service
from mdp_api.marts import ChannelDay, FunnelDay
from mdp_api.periods import Period
from mdp_api.repository import MartRepository
from mdp_api.schemas import DailyResponse, FunnelResponse, KpiResponse

router = APIRouter()


class RequestView:
    """The repository as one request sees it: the data range and the channel list are read
    once. The BigQuery repository refreshes its cached copies every few minutes; without this,
    a refresh in the middle of a request could make the checks and the response disagree
    (a channel accepted by `select`, then missing from the list the response is built from).
    """

    def __init__(self, repository: MartRepository) -> None:
        self._repository = repository
        self._data_range: Period | None = None
        self._channels: dict[str, bool] | None = None

    def data_range(self) -> Period:
        if self._data_range is None:
            self._data_range = self._repository.data_range()
        return self._data_range

    def channels(self) -> dict[str, bool]:
        if self._channels is None:
            self._channels = self._repository.channels()
        return dict(self._channels)

    def channel_daily(self, period: Period, channel: str | None = None) -> list[ChannelDay]:
        return self._repository.channel_daily(period, channel)

    def funnel_daily(self, period: Period, channel: str | None = None) -> list[FunnelDay]:
        return self._repository.funnel_daily(period, channel)


def get_repository(request: Request) -> MartRepository:
    """FastAPI calls this once per request (dependencies are cached), so `select` and the
    endpoint share one view.
    """
    return RequestView(request.app.state.repository)


Repository = Annotated[MartRepository, Depends(get_repository)]


@dataclass(frozen=True)
class Selection:
    """A validated request: a period inside the data and, optionally, one known channel."""

    period: Period
    channel: str | None


def _error(field: str, value: Any, message: str) -> dict[str, Any]:
    """One error in the same shape as FastAPI's own validation errors."""
    return {"type": "value_error", "loc": ("query", field), "msg": message, "input": value}


def select(
    repository: Repository,
    start: Annotated[date, Query(description="First day, included (YYYY-MM-DD).")],
    end: Annotated[date, Query(description="Last day, included (YYYY-MM-DD).")],
    channel: Annotated[
        str | None,
        Query(description="One channel, e.g. `Paid Search` (any case). All channels if omitted."),
    ] = None,
) -> Selection:
    """Checks the request against the data (FR-15). Problems with the dates and the channel are
    reported together, as 422. A malformed date is rejected by FastAPI before these checks.
    """
    errors = []
    data = repository.data_range()
    available = f"data is available from {data.start} to {data.end}"
    if start > end:
        errors.append(_error("end", end, f"end ({end}) is before start ({start})"))
    if start not in data:
        errors.append(_error("start", start, f"start ({start}) is outside the data: {available}"))
    if end not in data:
        errors.append(_error("end", end, f"end ({end}) is outside the data: {available}"))

    known = {name.casefold(): name for name in repository.channels()}
    channel = (channel or "").strip() or None  # empty `channel=` means all channels
    if channel is not None and channel.casefold() not in known:
        valid = ", ".join(repository.channels())
        errors.append(_error("channel", channel, f"unknown channel; valid channels: {valid}"))

    if errors:
        raise RequestValidationError(errors)
    return Selection(Period(start, end), known[channel.casefold()] if channel else None)


Selected = Annotated[Selection, Depends(select)]


@router.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness check. It doesn't touch the data, so it costs nothing to call."""
    return {"status": "ok"}


@router.get("/kpi", tags=["kpi"], summary="KPIs per channel, compared with the previous period")
def kpi(selection: Selected, repository: Repository) -> KpiResponse:
    """Sessions, orders, revenue, spend, ROAS, CPA, conversion rate and AOV per channel and in
    total, for the period (US-1). Each KPI comes with the previous period of the same length:
    its value, the change and the % change (US-4).
    """
    return service.kpi_report(repository, selection.period, selection.channel)


@router.get("/kpi/daily", tags=["kpi"], summary="The same KPIs day by day")
def kpi_daily(selection: Selected, repository: Repository) -> DailyResponse:
    """One row per day and channel, with zeros on days without activity (US-2)."""
    return service.daily_report(repository, selection.period, selection.channel)


@router.get("/funnel", tags=["funnel"], summary="Sessions reaching each step towards a purchase")
def funnel(selection: Selected, repository: Repository) -> FunnelResponse:
    """Open funnel, visit → view product → add to cart → begin checkout → purchase (US-3).
    A step that wasn't recorded on some day of the period is shown as not recorded, never as 0.
    """
    return service.funnel_report(repository, selection.period, selection.channel)
