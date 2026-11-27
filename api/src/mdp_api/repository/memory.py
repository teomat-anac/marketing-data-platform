"""Marts held in memory: the simulated data for local runs, and hand-made rows in tests."""

from collections.abc import Iterable

from mdp_api.marts import ChannelDay, FunnelDay
from mdp_api.periods import Period
from mdp_api.repository.base import reject_duplicates


class InMemoryRepository:
    def __init__(
        self, channel_rows: Iterable[ChannelDay], funnel_rows: Iterable[FunnelDay] = ()
    ) -> None:
        self._channel_rows = sorted(channel_rows, key=lambda r: (r.date, r.channel))
        self._funnel_rows = sorted(funnel_rows, key=lambda r: (r.date, r.channel, r.step_number))
        reject_duplicates("mart_channel_daily", [(r.date, r.channel) for r in self._channel_rows])
        reject_duplicates(
            "mart_funnel_daily", [(r.date, r.channel, r.step) for r in self._funnel_rows]
        )
        if not self._channel_rows:
            raise ValueError("mart_channel_daily has no rows")
        start, end = self._channel_rows[0].date, self._channel_rows[-1].date
        if self._funnel_rows:  # only days present in both marts
            start = max(start, min(r.date for r in self._funnel_rows))
            end = min(end, max(r.date for r in self._funnel_rows))
            if start > end:
                raise ValueError("mart_channel_daily and mart_funnel_daily share no day")
        self._data_range = Period(start, end)
        paid: dict[str, bool] = {}
        for r in self._channel_rows:
            paid[r.channel] = paid.get(r.channel, False) or r.is_paid
        self._channels = dict(sorted(paid.items()))

    def data_range(self) -> Period:
        return self._data_range

    def channels(self) -> dict[str, bool]:
        return dict(self._channels)

    def channel_daily(self, period: Period, channel: str | None = None) -> list[ChannelDay]:
        return [
            r
            for r in self._channel_rows
            if r.date in period and (channel is None or r.channel == channel)
        ]

    def funnel_daily(self, period: Period, channel: str | None = None) -> list[FunnelDay]:
        return [
            r
            for r in self._funnel_rows
            if r.date in period and (channel is None or r.channel == channel)
        ]
