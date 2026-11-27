from collections import defaultdict
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from mdp_api.main import create_app
from mdp_api.repository import InMemoryRepository
from tests.factories import channel_day, funnel_day

WEEK_2 = {"start": "2020-12-08", "end": "2020-12-14"}


def by_channel(body: dict) -> dict[str, dict]:
    return {c["channel"]: c["kpis"] for c in body["channels"]}


# --- /kpi -----------------------------------------------------------------------------------


def test_kpi_per_channel_with_previous_period(client: TestClient) -> None:
    response = client.get("/kpi", params=WEEK_2)
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == {"start": "2020-12-08", "end": "2020-12-14", "days": 7}
    assert body["previous_period"] == {
        "start": "2020-12-01",
        "end": "2020-12-07",
        "days": 7,
        "available": True,
        "reason": None,
    }
    paid = by_channel(body)["Paid Search"]
    assert paid["sessions"] == {"value": 840, "previous": 700, "change": 140, "change_pct": 0.2}
    assert paid["revenue"] == {"value": 420.0, "previous": 350.0, "change": 70.0, "change_pct": 0.2}
    assert paid["spend"]["value"] == 350.0
    # ROAS 420 / 350 = 1.2 against 350 / 280 = 1.25
    assert paid["roas"] == {"value": 1.2, "previous": 1.25, "change": -0.05, "change_pct": -0.04}
    # CPA 350 / 14 = 25 against 280 / 7 = 40
    assert paid["cpa"] == {"value": 25.0, "previous": 40.0, "change": -15.0, "change_pct": -0.375}
    # Conversion rate 14 / 840 = 1.67% against 7 / 700 = 1%
    assert paid["conversion_rate"]["value"] == 0.0167
    assert paid["conversion_rate"]["previous"] == 0.01
    assert paid["aov"]["value"] == 30.0


def test_channels_without_spend_have_empty_roas_and_cpa(client: TestClient) -> None:
    direct = by_channel(client.get("/kpi", params=WEEK_2).json())["Direct"]
    assert direct["spend"]["value"] == 0
    for kpi in ("roas", "cpa"):
        assert direct[kpi] == {"value": None, "previous": None, "change": None, "change_pct": None}


def test_channels_are_sorted_by_revenue_and_flag_paid(client: TestClient) -> None:
    channels = client.get("/kpi", params=WEEK_2).json()["channels"]
    assert [(c["channel"], c["is_paid"]) for c in channels] == [
        ("Direct", False),
        ("Paid Search", True),
    ]


def test_total_adds_up_the_channels(client: TestClient) -> None:
    total = client.get("/kpi", params=WEEK_2).json()["total"]
    assert total["revenue"]["value"] == 420 + 1120
    assert total["revenue"]["previous"] == 350 + 1050
    assert total["sessions"]["value"] == 840 + 1400
    assert total["roas"]["value"] == 4.4  # blended: all revenue 1,540 ÷ all spend 350


def test_previous_period_outside_the_data_is_flagged_not_zero(client: TestClient) -> None:
    # 5-14 Dec: the previous 10 days start on 25 Nov, before the data
    body = client.get("/kpi", params={"start": "2020-12-05", "end": "2020-12-14"}).json()
    previous = body["previous_period"]
    assert previous["available"] is False
    assert previous["start"] == "2020-11-25"
    assert "first day of data (2020-12-01)" in previous["reason"]
    for kpis in [body["total"], *by_channel(body).values()]:
        for metric in kpis.values():
            assert metric["previous"] is metric["change"] is metric["change_pct"] is None
    # The current values are still there: Paid Search 3 x $50 + 7 x $60, Direct 3 x $150 + 7 x $160
    assert body["total"]["revenue"]["value"] == 570 + 1570


def test_channel_rows_add_up_to_the_total_even_without_zero_filling() -> None:
    # Email has rows only in the previous day: it must still be listed, with 0 now
    repository = InMemoryRepository(
        [
            channel_day("2020-12-01", "Direct", revenue="10"),
            channel_day("2020-12-01", "Email", revenue="5"),
            channel_day("2020-12-02", "Direct", revenue="20"),
        ]
    )
    body = (
        TestClient(create_app(repository=repository))
        .get("/kpi", params={"start": "2020-12-02", "end": "2020-12-02"})
        .json()
    )
    email = by_channel(body)["Email"]["revenue"]
    assert email == {"value": 0.0, "previous": 5.0, "change": -5.0, "change_pct": -1.0}
    assert body["total"]["revenue"]["previous"] == 15.0


def test_change_is_the_difference_of_the_shown_values() -> None:
    # ROAS 1.005 → shown 1.01, against 1.004 → shown 1.00: the change shown is 0.01
    repository = InMemoryRepository(
        [
            channel_day("2020-12-01", revenue="1.004", spend="1"),
            channel_day("2020-12-02", revenue="1.005", spend="1"),
        ]
    )
    body = (
        TestClient(create_app(repository=repository))
        .get("/kpi", params={"start": "2020-12-02", "end": "2020-12-02"})
        .json()
    )
    roas = by_channel(body)["Paid Search"]["roas"]
    assert (roas["value"], roas["previous"], roas["change"]) == (1.01, 1.0, 0.01)
    assert roas["change_pct"] == 0.01  # 0.01 / 1.00, as shown


def test_no_percentage_against_a_previous_value_shown_as_zero() -> None:
    # Conversion rate 1 / 30,000 = 0.00003 shows as 0.0: no +30,000% next to it
    repository = InMemoryRepository(
        [
            channel_day("2020-12-01", "Direct", sessions=30000, orders=1),
            channel_day("2020-12-02", "Direct", sessions=100, orders=10),
        ]
    )
    body = (
        TestClient(create_app(repository=repository))
        .get("/kpi", params={"start": "2020-12-02", "end": "2020-12-02"})
        .json()
    )
    rate = by_channel(body)["Direct"]["conversion_rate"]
    assert rate == {"value": 0.1, "previous": 0.0, "change": 0.1, "change_pct": None}


def test_every_channel_in_scope_is_listed_even_without_rows() -> None:
    repository = InMemoryRepository(
        [
            channel_day("2020-12-01", "Direct", revenue="10"),
            channel_day("2020-12-01", "Email", revenue="5"),
            channel_day("2020-12-03", "Direct", revenue="20"),
        ]
    )
    client = TestClient(create_app(repository=repository))
    one_day = {"start": "2020-12-03", "end": "2020-12-03"}
    assert {c["channel"] for c in client.get("/kpi", params=one_day).json()["channels"]} == {
        "Direct",
        "Email",
    }
    # /kpi/daily fills missing day × channel rows with zeros: 2 Dec has no row at all
    rows = client.get("/kpi/daily", params={"start": "2020-12-01", "end": "2020-12-03"}).json()
    pairs = [(r["date"], r["channel"], r["revenue"]) for r in rows["rows"]]
    assert pairs == [
        ("2020-12-01", "Direct", 10.0),
        ("2020-12-01", "Email", 5.0),
        ("2020-12-02", "Direct", 0.0),
        ("2020-12-02", "Email", 0.0),
        ("2020-12-03", "Direct", 20.0),
        ("2020-12-03", "Email", 0.0),
    ]


def test_channel_filter_any_case(client: TestClient) -> None:
    body = client.get("/kpi", params={**WEEK_2, "channel": " paid SEARCH "}).json()
    assert body["channel"] == "Paid Search"
    assert list(by_channel(body)) == ["Paid Search"]
    assert body["total"]["revenue"]["value"] == 420.0


def test_period_totals_equal_the_sum_of_the_days(fake_client: TestClient) -> None:
    period = {"start": "2020-11-20", "end": "2020-12-10"}
    kpis = by_channel(fake_client.get("/kpi", params=period).json())
    daily = fake_client.get("/kpi/daily", params=period).json()["rows"]
    summed: defaultdict[str, defaultdict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for row in daily:
        for kpi in ("sessions", "orders", "revenue", "spend", "clicks", "impressions"):
            summed[row["channel"]][kpi] += Decimal(str(row[kpi]))
    assert summed.keys() == kpis.keys()
    for channel, sums in summed.items():
        for kpi, value in sums.items():
            assert Decimal(str(kpis[channel][kpi]["value"])) == value, (channel, kpi)


# --- /kpi/daily -----------------------------------------------------------------------------


def test_daily_has_a_row_for_every_day_and_channel(fake_client: TestClient) -> None:
    week = {"start": "2020-12-01", "end": "2020-12-07"}
    rows = fake_client.get("/kpi/daily", params=week).json()["rows"]
    assert len(rows) == 7 * 9
    assert [(r["date"], r["channel"]) for r in rows] == sorted(
        (r["date"], r["channel"]) for r in rows
    )
    paid = fake_client.get("/kpi/daily", params={**week, "channel": "Paid Search"}).json()["rows"]
    assert len(paid) == 7 and all(r["spend"] > 0 for r in paid)


def test_daily_zero_activity_shows_zeros_and_empty_ratios(fake_client: TestClient) -> None:
    rows = fake_client.get(
        "/kpi/daily",
        params={"start": "2020-11-01", "end": "2021-01-24", "channel": "Organic Video"},
    ).json()["rows"]
    quiet = [r for r in rows if r["sessions"] == 0]
    assert quiet, "the simulated data has days without Organic Video sessions"
    assert quiet[0]["orders"] == 0 and quiet[0]["revenue"] == 0
    assert quiet[0]["conversion_rate"] is None and quiet[0]["roas"] is None


def test_daily_values(client: TestClient) -> None:
    rows = client.get(
        "/kpi/daily", params={"start": "2020-12-08", "end": "2020-12-08", "channel": "Paid Search"}
    ).json()["rows"]
    assert rows == [
        {
            "date": "2020-12-08",
            "channel": "Paid Search",
            "is_paid": True,
            "sessions": 120,
            "orders": 2,
            "revenue": 60.0,
            "spend": 50.0,
            "clicks": 130,
            "impressions": 4000,
            "roas": 1.2,
            "cpa": 25.0,
            "conversion_rate": 0.0167,
            "aov": 30.0,
        }
    ]


# --- /funnel --------------------------------------------------------------------------------


def test_funnel(client: TestClient) -> None:
    body = client.get("/funnel", params={**WEEK_2, "channel": "Direct"}).json()
    assert body["channel"] == "Direct"
    steps = [(s["step"], s["sessions"], s["rate_from_previous"]) for s in body["steps"]]
    assert steps == [
        ("visit", 700, None),
        ("view_item", 350, 0.5),
        ("add_to_cart", 140, 0.4),
        ("begin_checkout", 70, 0.5),
        ("purchase", 14, 0.2),
    ]


def test_funnel_step_not_recorded_is_never_zero(client: TestClient) -> None:
    # 5-10 Dec: add_to_cart missing on 5, 6 and 7 Dec
    steps = client.get("/funnel", params={"start": "2020-12-05", "end": "2020-12-10"}).json()
    add_to_cart = steps["steps"][2]
    assert add_to_cart == {
        "step": "add_to_cart",
        "step_number": 3,
        "is_tracked": False,
        "sessions": None,
        "untracked_days": 3,
        "rate_from_previous": None,
    }
    assert steps["steps"][3]["rate_from_previous"] is None
    assert steps["steps"][4]["rate_from_previous"] == 0.2


# --- Validation (FR-15) ---------------------------------------------------------------------


def errors(response) -> list[tuple[str, str]]:
    assert response.status_code == 422
    return [(e["loc"][-1], e["msg"]) for e in response.json()["detail"]]


def test_start_after_end(client: TestClient) -> None:
    response = client.get("/kpi", params={"start": "2020-12-10", "end": "2020-12-09"})
    assert errors(response) == [("end", "end (2020-12-09) is before start (2020-12-10)")]


def test_dates_outside_the_data(client: TestClient) -> None:
    response = client.get("/funnel", params={"start": "2020-11-30", "end": "2020-12-15"})
    available = "data is available from 2020-12-01 to 2020-12-14"
    assert errors(response) == [
        ("start", f"start (2020-11-30) is outside the data: {available}"),
        ("end", f"end (2020-12-15) is outside the data: {available}"),
    ]


def test_unknown_channel_lists_the_valid_ones(client: TestClient) -> None:
    response = client.get("/kpi/daily", params={**WEEK_2, "channel": "Paid"})
    assert errors(response) == [("channel", "unknown channel; valid channels: Direct, Paid Search")]


def test_malformed_and_missing_dates(client: TestClient) -> None:
    bad_day = client.get("/kpi", params={"start": "2020-12-32", "end": "2020-12-14"})
    assert [loc for loc, _ in errors(bad_day)] == ["start"]
    assert [loc for loc, _ in errors(client.get("/kpi"))] == ["start", "end"]


def test_an_empty_channel_means_all_channels(client: TestClient) -> None:
    body = client.get("/kpi", params={**WEEK_2, "channel": " "}).json()
    assert body["channel"] is None
    assert len(body["channels"]) == 2


def test_a_single_day_is_a_valid_period(client: TestClient) -> None:
    response = client.get("/kpi", params={"start": "2020-12-14", "end": "2020-12-14"})
    assert response.status_code == 200
    assert response.json()["previous_period"]["start"] == "2020-12-13"


class ChannelListChangesAfterOneRead(InMemoryRepository):
    """A repository whose cached channel list is refreshed between two reads, as the BigQuery
    one can be when its cache expires during a request: Email has left the marts.
    """

    reads = 0

    def channels(self) -> dict[str, bool]:
        self.reads += 1
        channels = super().channels()
        return channels if self.reads == 1 else {"Direct": False}


@pytest.mark.parametrize("url", ["/kpi", "/kpi/daily", "/funnel"])
def test_one_request_reads_the_channel_list_once(url: str) -> None:
    """A refresh between `select` and the response gave a 500 (KeyError)."""
    repository = ChannelListChangesAfterOneRead(
        [channel_day("2020-12-01", "Direct"), channel_day("2020-12-01", "Email")],
        [funnel_day("2020-12-01", "visit", 1, c) for c in ("Direct", "Email")],
    )
    client = TestClient(create_app(repository=repository))
    params = {"start": "2020-12-01", "end": "2020-12-01", "channel": "Email"}
    assert client.get(url, params=params).status_code == 200
    assert repository.reads == 1
