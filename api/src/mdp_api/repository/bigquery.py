"""The real marts, read from BigQuery.

Every query has parameters (no values pasted into SQL), a byte cap (docs/costs.md §1)
and job labels, so the API's queries can be found in `INFORMATION_SCHEMA.JOBS`. Rows are read
as they are; every KPI is computed in `metrics`, as with the in-memory repository (D24).

`data_range` and `channels` are cached for a few minutes per instance: they are needed by
every request, and each query is billed at least 10 MB per table it reads. With the cache, a
request costs one query, on one mart. The time limit lets a pipeline re-run show up without
a redeploy.
"""

import logging
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from google.cloud import bigquery

from mdp_api.marts import ChannelDay, FunnelDay
from mdp_api.periods import Period
from mdp_api.repository.base import reject_duplicates

CHANNEL_MART = "mart_channel_daily"
FUNNEL_MART = "mart_funnel_daily"
JOB_LABELS = {"app": "mdp", "component": "api"}
# A query normally takes a second or two. None of its waits is left open: BigQuery cancels a
# job that runs longer than this; each HTTP call to BigQuery waits at most this long; retries
# stop after it; and a failed job is not re-run. (The library's defaults are no HTTP timeout,
# 10 minutes of retries and 40 minutes of job retries.) A query that hits these limits fails;
# a request still running at Cloud Run's 60 s timeout gets a 504 (cloud_run.tf).
QUERY_TIMEOUT_SECONDS = 15
_RETRY = bigquery.DEFAULT_RETRY.with_timeout(QUERY_TIMEOUT_SECONDS)

log = logging.getLogger(__name__)

# First and last day of each mart; the data range is the days present in both.
_DATA_RANGE_SQL = """
select
  (select min(date) from `{channel_table}`) as channel_first,
  (select max(date) from `{channel_table}`) as channel_last,
  (select min(date) from `{funnel_table}`) as funnel_first,
  (select max(date) from `{funnel_table}`) as funnel_last
"""

_CHANNELS_SQL = """
select channel, logical_or(is_paid) as is_paid
from `{channel_table}`
group by channel
"""

# `date` is the partition column, so the date filter limits what is read.
_CHANNEL_DAILY_SQL = """
select date, channel, is_paid, sessions, orders, revenue, clicks, impressions, spend
from `{channel_table}`
where date between @start and @end
  and (@channel is null or channel = @channel)
order by date, channel
"""

_FUNNEL_DAILY_SQL = """
select date, channel, step, step_number, sessions, is_tracked
from `{funnel_table}`
where date between @start and @end
  and (@channel is null or channel = @channel)
order by date, channel, step_number
"""

Row = Mapping[str, Any]


class _Cached[T]:
    """A value loaded on first use and reloaded once it is older than `seconds`.

    Once a value is held, one caller at a time reloads it, outside the lock; the others don't
    wait for that query, they get the value already held. Before that (a new instance),
    callers arriving together each run the first load: a few extra queries, 10.5 MB each.

    If a reload fails, the old value is kept and served, and the next caller tries again; the
    error reaches the caller only when there is no value yet (the first load). So a slow or
    failing BigQuery delays one request, not every request queued behind it.
    """

    def __init__(self, load: Callable[[], T], seconds: float, clock: Callable[[], float]):
        self._load, self._seconds, self._clock = load, seconds, clock
        self._lock = threading.Lock()
        self._value: T | None = None
        self._loaded_at = 0.0
        self._reloading = False

    def get(self) -> T:
        with self._lock:
            held = self._value
            if held is not None and self._clock() - self._loaded_at < self._seconds:
                return held  # fresh
            if held is not None and self._reloading:
                return held  # another request is reloading it
            self._reloading = True
        loaded: T | None = None
        try:
            loaded = self._load()
        except Exception:
            if held is None:
                raise
            log.warning("Reloading a cached value failed; serving the previous one", exc_info=True)
            return held
        finally:
            with self._lock:
                self._reloading = False
                if loaded is not None:
                    self._value, self._loaded_at = loaded, self._clock()
        return loaded


class BigQueryRepository:
    """Reads the two marts of one BigQuery dataset (`project.dataset`)."""

    def __init__(
        self,
        client: bigquery.Client,
        dataset: str,
        *,
        location: str,
        max_bytes_billed: int,
        cache_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._location = location
        self._max_bytes_billed = max_bytes_billed
        self._tables = {
            "channel_table": f"{dataset}.{CHANNEL_MART}",
            "funnel_table": f"{dataset}.{FUNNEL_MART}",
        }
        self._data_range = _Cached(self._read_data_range, cache_seconds, clock)
        self._channels = _Cached(self._read_channels, cache_seconds, clock)

    def data_range(self) -> Period:
        return self._data_range.get()

    def channels(self) -> dict[str, bool]:
        return dict(self._channels.get())

    def channel_daily(self, period: Period, channel: str | None = None) -> list[ChannelDay]:
        rows = [
            ChannelDay(
                date=r["date"],
                channel=r["channel"],
                is_paid=r["is_paid"],
                sessions=r["sessions"],
                orders=r["orders"],
                revenue=r["revenue"],
                clicks=r["clicks"],
                impressions=r["impressions"],
                spend=r["spend"],
            )
            for r in self._query(_CHANNEL_DAILY_SQL, _filters(period, channel))
        ]
        reject_duplicates(CHANNEL_MART, [(r.date, r.channel) for r in rows])
        return rows

    def funnel_daily(self, period: Period, channel: str | None = None) -> list[FunnelDay]:
        rows = [
            FunnelDay(
                date=r["date"],
                channel=r["channel"],
                step=r["step"],
                step_number=r["step_number"],
                sessions=r["sessions"],
                is_tracked=r["is_tracked"],
            )
            for r in self._query(_FUNNEL_DAILY_SQL, _filters(period, channel))
        ]
        reject_duplicates(FUNNEL_MART, [(r.date, r.channel, r.step) for r in rows])
        return rows

    def _read_data_range(self) -> Period:
        (r,) = self._query(_DATA_RANGE_SQL)
        for mart, first in ((CHANNEL_MART, "channel_first"), (FUNNEL_MART, "funnel_first")):
            if r[first] is None:
                raise ValueError(f"{mart} has no rows")
        start = max(r["channel_first"], r["funnel_first"])
        end = min(r["channel_last"], r["funnel_last"])
        if start > end:
            raise ValueError(f"{CHANNEL_MART} and {FUNNEL_MART} share no day")
        return Period(start, end)

    def _read_channels(self) -> dict[str, bool]:
        return dict(sorted((r["channel"], r["is_paid"]) for r in self._query(_CHANNELS_SQL)))

    def _query(
        self, sql: str, parameters: Sequence[bigquery.ScalarQueryParameter] = ()
    ) -> list[Row]:
        job_config = bigquery.QueryJobConfig(
            query_parameters=list(parameters),
            maximum_bytes_billed=self._max_bytes_billed,
            labels=JOB_LABELS,
            job_timeout_ms=QUERY_TIMEOUT_SECONDS * 1000,
        )
        job = self._client.query(
            sql.format(**self._tables),
            job_config=job_config,
            location=self._location,
            timeout=QUERY_TIMEOUT_SECONDS,
            retry=_RETRY,
            job_retry=None,
        )
        return list(job.result(timeout=QUERY_TIMEOUT_SECONDS, retry=_RETRY))


def _filters(period: Period, channel: str | None) -> list[bigquery.ScalarQueryParameter]:
    return [
        bigquery.ScalarQueryParameter("start", "DATE", period.start),
        bigquery.ScalarQueryParameter("end", "DATE", period.end),
        bigquery.ScalarQueryParameter("channel", "STRING", channel),  # None: all channels
    ]
