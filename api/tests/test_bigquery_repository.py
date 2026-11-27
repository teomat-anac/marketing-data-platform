"""BigQueryRepository on simulated BigQuery: a stand-in client answers its queries from rows
held in memory, filtering them by the query parameters as BigQuery would.

The real marts are checked by the opt-in live test (test_bigquery_live.py).
"""

import threading
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.cloud import bigquery

from mdp_api.main import create_app
from mdp_api.marts import ChannelDay, FunnelDay
from mdp_api.periods import Period
from mdp_api.repository import BigQueryRepository, InMemoryRepository
from mdp_api.repository import bigquery as bq
from mdp_api.repository.fake import fake_marts
from tests.factories import channel_day, day, funnel_day

DATASET = "proj.marts"
TABLES = {
    "channel_table": f"{DATASET}.mart_channel_daily",
    "funnel_table": f"{DATASET}.mart_funnel_daily",
}


@dataclass
class Call:
    sql: str
    job_config: bigquery.QueryJobConfig
    location: str
    waits: dict[str, Any]  # timeout, retry and job_retry passed to query() and result()

    @property
    def parameters(self) -> dict[str, Any]:
        return {p.name: p.value for p in self.job_config.query_parameters}


class SimulatedBigQuery:
    """Answers the four queries of BigQueryRepository from in-memory mart rows."""

    def __init__(self, channel_rows: Iterable[ChannelDay], funnel_rows: Iterable[FunnelDay]):
        self.channel_rows = [asdict(r) for r in channel_rows]
        self.funnel_rows = [asdict(r) for r in funnel_rows]
        self.calls: list[Call] = []

    def query(
        self, sql: str, *, job_config: bigquery.QueryJobConfig, location: str, **waits: Any
    ) -> Any:
        call = Call(sql, job_config, location, {f"query_{k}": v for k, v in waits.items()})
        self.calls.append(call)
        rows = self._answer(call)

        def result(**waits: Any) -> Iterable[dict[str, Any]]:
            call.waits.update({f"result_{k}": v for k, v in waits.items()})
            return iter(rows)

        return SimpleNamespace(result=result)  # a finished query job

    def _answer(self, call: Call) -> list[dict[str, Any]]:
        if call.sql == bq._DATA_RANGE_SQL.format(**TABLES):
            c = [r["date"] for r in self.channel_rows]
            f = [r["date"] for r in self.funnel_rows]
            return [
                {
                    "channel_first": min(c, default=None),
                    "channel_last": max(c, default=None),
                    "funnel_first": min(f, default=None),
                    "funnel_last": max(f, default=None),
                }
            ]
        if call.sql == bq._CHANNELS_SQL.format(**TABLES):
            paid: dict[str, bool] = {}
            for r in self.channel_rows:
                paid[r["channel"]] = paid.get(r["channel"], False) or r["is_paid"]
            return [{"channel": c, "is_paid": p} for c, p in paid.items()]  # unordered
        if call.sql == bq._CHANNEL_DAILY_SQL.format(**TABLES):
            return self._filter(self.channel_rows, call.parameters, ("date", "channel"))
        if call.sql == bq._FUNNEL_DAILY_SQL.format(**TABLES):
            return self._filter(
                self.funnel_rows, call.parameters, ("date", "channel", "step_number")
            )
        raise AssertionError(f"unexpected query: {call.sql}")

    @staticmethod
    def _filter(
        rows: list[dict[str, Any]], p: dict[str, Any], order: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        kept = [
            r
            for r in rows
            if p["start"] <= r["date"] <= p["end"]
            and (p["channel"] is None or r["channel"] == p["channel"])
        ]
        return sorted(kept, key=lambda r: tuple(r[k] for k in order))


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def repository(
    client: SimulatedBigQuery, *, cache_seconds: float = 600, clock: Clock | None = None
) -> BigQueryRepository:
    return BigQueryRepository(
        client,  # duck-typed: only `query` is used
        DATASET,
        location="US",
        max_bytes_billed=100_000_000,
        cache_seconds=cache_seconds,
        clock=clock or Clock(),
    )


def simulated_marts() -> SimulatedBigQuery:
    return SimulatedBigQuery(*fake_marts())


# --- Same answers as the in-memory repository --------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/kpi?start=2020-12-08&end=2020-12-14",
        "/kpi?start=2020-11-01&end=2021-01-24",
        "/kpi?start=2020-12-01&end=2020-12-31&channel=paid%20search",
        "/kpi/daily?start=2020-11-25&end=2020-11-30",
        "/kpi/daily?start=2021-01-01&end=2021-01-03&channel=Email",
        "/funnel?start=2020-11-01&end=2020-11-30",
        "/funnel?start=2020-12-01&end=2021-01-24&channel=Direct",
        "/kpi?start=2020-10-01&end=2020-11-02&channel=Nowhere",  # 422: dates and channel
    ],
)
def test_responses_match_the_in_memory_repository(url: str) -> None:
    in_memory = TestClient(create_app(repository=InMemoryRepository(*fake_marts())))
    on_bigquery = TestClient(create_app(repository=repository(simulated_marts())))
    expected, actual = in_memory.get(url), on_bigquery.get(url)
    assert actual.status_code == expected.status_code
    assert actual.json() == expected.json()


def test_data_range_and_channels() -> None:
    repo = repository(simulated_marts())
    assert repo.data_range() == Period(date(2020, 11, 1), date(2021, 1, 24))
    channels = repo.channels()
    assert list(channels) == sorted(channels)  # sorted by name
    assert [c for c, paid in channels.items() if paid] == ["Paid Search"]


def test_data_range_covers_only_days_present_in_both_marts() -> None:
    client = SimulatedBigQuery(
        [channel_day(d) for d in ("2020-12-01", "2020-12-02", "2020-12-03")],
        [funnel_day(d, "visit", 1) for d in ("2020-12-02", "2020-12-03", "2020-12-04")],
    )
    assert repository(client).data_range() == Period(day("2020-12-02"), day("2020-12-03"))


@pytest.mark.parametrize(
    ("channel_rows", "funnel_rows", "error"),
    [
        ([], [funnel_day("2020-12-01", "visit", 1)], "mart_channel_daily has no rows"),
        ([channel_day("2020-12-01")], [], "mart_funnel_daily has no rows"),
        ([channel_day("2020-12-01")], [funnel_day("2020-12-05", "visit", 1)], "share no day"),
    ],
)
def test_unusable_marts_are_rejected(
    channel_rows: list[ChannelDay], funnel_rows: list[FunnelDay], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        repository(SimulatedBigQuery(channel_rows, funnel_rows)).data_range()


def test_duplicate_rows_are_rejected() -> None:
    """D43: each mart key appears once; a duplicate fails instead of being added up."""
    client = SimulatedBigQuery(
        [channel_day("2020-12-01", "Direct", revenue="10"), channel_day("2020-12-01", "Direct")],
        [funnel_day("2020-12-01", "visit", 3), funnel_day("2020-12-01", "visit", 4)],
    )
    one_day = Period(day("2020-12-01"), day("2020-12-01"))
    with pytest.raises(ValueError, match="mart_channel_daily has duplicate rows for 1 keys"):
        repository(client).channel_daily(one_day)
    with pytest.raises(ValueError, match="mart_funnel_daily has duplicate rows for 1 keys"):
        repository(client).funnel_daily(one_day)


# --- How it queries --------------------------------------------------------------------------


def test_every_query_is_capped_labelled_timed_and_run_in_us() -> None:
    client = simulated_marts()
    api = TestClient(create_app(repository=repository(client)))
    for url in ("/kpi", "/kpi/daily", "/funnel"):
        assert api.get(f"{url}?start=2020-12-01&end=2020-12-07").status_code == 200
    assert len(client.calls) == 2 + 3  # data range and channels once, then one per request
    for call in client.calls:
        assert call.job_config.maximum_bytes_billed == 100_000_000
        assert call.job_config.labels == {"app": "mdp", "component": "api"}
        assert call.location == "US"
        # No wait is left open: BigQuery cancels the job after 15 s, every HTTP
        # call has a 15 s timeout, retries stop after 15 s and a failed job is not re-run.
        assert int(call.job_config.job_timeout_ms) == 15_000  # the API sends it as a string
        waits = call.waits
        assert (waits["query_timeout"], waits["result_timeout"]) == (15, 15)
        assert waits["query_retry"] is waits["result_retry"]
        assert waits["query_retry"]._timeout == 15  # instead of the library's 600 s
        assert waits["query_job_retry"] is None  # instead of 2,400 s of job retries


def test_values_are_passed_as_parameters_not_pasted_into_sql() -> None:
    client = simulated_marts()
    repo = repository(client)
    december = Period(day("2020-12-01"), day("2020-12-31"))
    repo.channel_daily(december, "Paid Search")
    repo.funnel_daily(december)
    by_channel, funnel = client.calls
    assert by_channel.parameters == {
        "start": day("2020-12-01"),
        "end": day("2020-12-31"),
        "channel": "Paid Search",
    }
    assert funnel.parameters["channel"] is None  # NULL: all channels
    for call in client.calls:
        assert "2020-12" not in call.sql and "Paid Search" not in call.sql


def test_data_range_and_channels_are_cached_for_a_while() -> None:
    client, clock = simulated_marts(), Clock()
    repo = repository(client, cache_seconds=600, clock=clock)

    def reads() -> int:
        repo.data_range()
        repo.channels()
        return len(client.calls)

    assert reads() == 2
    clock.now = 599
    assert reads() == 2  # still cached
    clock.now = 600
    assert reads() == 4  # read again: a pipeline re-run shows up without a redeploy


def test_the_cached_channel_list_cannot_be_changed_by_a_caller() -> None:
    repo = repository(simulated_marts())
    repo.channels()["Nowhere"] = False
    assert "Nowhere" not in repo.channels()


# --- The cache when BigQuery is slow or failing ------------------------------


class Loads:
    """A load function for `_Cached` that returns 1, 2, 3… or raises, as told."""

    def __init__(self) -> None:
        self.count = 0
        self.fail = False
        self.started = threading.Event()
        self.release: threading.Event | None = None  # when set, a load waits for it

    def __call__(self) -> int:
        self.count += 1
        self.started.set()
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.fail:
            raise RuntimeError("BigQuery is down")
        return self.count


def test_a_failed_reload_keeps_serving_the_previous_value() -> None:
    load, clock = Loads(), Clock()
    cached = bq._Cached(load, 600, clock)
    assert cached.get() == 1
    clock.now, load.fail = 600, True
    assert cached.get() == 1  # stale, but served: the error is logged, not raised
    assert cached.get() == 1
    assert load.count == 3  # each caller tried again, one at a time
    load.fail = False
    assert cached.get() == 4  # BigQuery is back
    clock.now = 1199
    assert cached.get() == 4  # and fresh for another 10 minutes


def test_the_first_load_fails_loudly() -> None:
    load = Loads()
    load.fail = True
    cached = bq._Cached(load, 600, Clock())
    with pytest.raises(RuntimeError, match="BigQuery is down"):
        cached.get()
    load.fail = False
    assert cached.get() == 2  # the failure isn't remembered


def test_callers_dont_wait_for_another_callers_reload() -> None:
    load, clock = Loads(), Clock()
    cached = bq._Cached(load, 600, clock)
    assert cached.get() == 1
    clock.now = 600
    load.started.clear()
    load.release = threading.Event()  # the reload hangs until released
    reloading = threading.Thread(target=cached.get)
    reloading.start()
    assert load.started.wait(timeout=5)
    assert cached.get() == 1  # served at once, while the reload is still running
    assert load.count == 2  # no second reload was started
    load.release.set()
    reloading.join(timeout=5)
    assert cached.get() == 2
