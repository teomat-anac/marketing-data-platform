"""The interface between the API and wherever the marts live."""

from collections import Counter
from collections.abc import Hashable
from typing import Protocol

from mdp_api.marts import ChannelDay, FunnelDay
from mdp_api.periods import Period


class MartRepository(Protocol):
    """Reads mart rows. It filters but never calculates: every KPI is computed in `metrics`.

    Implementations: `InMemoryRepository` (simulated data and tests) and `BigQueryRepository`
    (the real marts), which caches `data_range` and `channels` because each query is billed.

    Each mart key appears once: (date, channel) in `mart_channel_daily`, (date, channel, step)
    in `mart_funnel_daily`. dbt tests this on the marts; an implementation that finds a
    duplicate raises an error rather than add the rows up or keep one of them
    (`reject_duplicates`).
    """

    def data_range(self) -> Period:
        """First and last day present in both marts."""
        ...

    def channels(self) -> dict[str, bool]:
        """Every channel in the marts, sorted by name, with whether it is paid (`is_paid`)."""
        ...

    def channel_daily(self, period: Period, channel: str | None = None) -> list[ChannelDay]:
        """Rows of `mart_channel_daily` in `period`, for one channel or all of them."""
        ...

    def funnel_daily(self, period: Period, channel: str | None = None) -> list[FunnelDay]:
        """Rows of `mart_funnel_daily` in `period`, for one channel or all of them."""
        ...


def reject_duplicates(mart: str, keys: list[Hashable]) -> None:
    """One row per key (see MartRepository): a duplicate would be summed by /kpi but not by
    /kpi/daily or /funnel, so the numbers would disagree. Fail instead.
    """
    duplicates = sorted(str(k) for k, n in Counter(keys).items() if n > 1)
    if duplicates:
        shown = ", ".join(duplicates[:3]) + (" …" if len(duplicates) > 3 else "")
        raise ValueError(f"{mart} has duplicate rows for {len(duplicates)} keys: {shown}")
