"""Date periods: the requested range and the previous period of the same length (US-4)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class Period:
    """A range of whole days. Both ends are included."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(f"start {self.start} is after end {self.end}")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> Period:
        """The period of the same length that ends the day before this one starts."""
        end = self.start - timedelta(days=1)
        return Period(end - timedelta(days=self.days - 1), end)

    def contains(self, other: Period) -> bool:
        """True when `other` lies entirely inside this period."""
        return self.start <= other.start and other.end <= self.end

    def __contains__(self, day: date) -> bool:
        return self.start <= day <= self.end

    def dates(self) -> Iterator[date]:
        for offset in range(self.days):
            yield self.start + timedelta(days=offset)
