from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest

from mdp_api.metrics import Totals
from mdp_api.periods import Period
from mdp_api.repository import InMemoryRepository
from mdp_api.repository.fake import ADD_TO_CART_RECORDED_FROM, DATA_RANGE, fake_marts
from tests.factories import channel_day, day, funnel_day

# --- InMemoryRepository ---------------------------------------------------------------------


def make_repository() -> InMemoryRepository:
    return InMemoryRepository(
        [
            channel_day("2020-12-02", "Paid Search", sessions=2),
            channel_day("2020-12-01", "Paid Search", sessions=1),
            channel_day("2020-12-01", "Direct", sessions=10),
            channel_day("2020-12-03", "Direct", sessions=30),
        ],
        [
            funnel_day(d, "visit", n)
            for d, n in (("2020-12-01", 10), ("2020-12-02", 20), ("2020-12-03", 30))
        ],
    )


def test_data_range_and_channels_come_from_the_rows() -> None:
    repository = make_repository()
    assert repository.data_range() == Period(day("2020-12-01"), day("2020-12-03"))
    assert repository.channels() == {"Direct": False, "Paid Search": True}


def test_rows_are_filtered_by_period_and_channel() -> None:
    repository = make_repository()
    two_days = Period(day("2020-12-01"), day("2020-12-02"))
    assert [r.sessions for r in repository.channel_daily(two_days)] == [10, 1, 2]
    assert [r.sessions for r in repository.channel_daily(two_days, "Paid Search")] == [1, 2]
    assert [r.sessions for r in repository.funnel_daily(two_days, "Direct")] == [10, 20]
    assert repository.funnel_daily(two_days, "Paid Search") == []


def test_data_range_covers_only_days_present_in_both_marts() -> None:
    repository = InMemoryRepository(
        [channel_day(d, sessions=1) for d in ("2020-12-01", "2020-12-02", "2020-12-03")],
        [funnel_day(d, "visit", 1) for d in ("2020-12-02", "2020-12-03", "2020-12-04")],
    )
    assert repository.data_range() == Period(day("2020-12-02"), day("2020-12-03"))


def test_marts_without_a_common_day_are_rejected() -> None:
    with pytest.raises(ValueError, match="share no day"):
        InMemoryRepository([channel_day("2020-12-01")], [funnel_day("2020-12-05", "visit", 1)])


def test_duplicate_channel_rows_are_rejected() -> None:
    """/kpi used to sum duplicates while /kpi/daily kept the last one."""
    with pytest.raises(ValueError, match=r"mart_channel_daily has duplicate rows for 1 keys"):
        InMemoryRepository(
            [
                channel_day("2020-12-01", "Direct", revenue="10"),
                channel_day("2020-12-01", "Direct", revenue="5"),
                channel_day("2020-12-01", "Email"),
            ]
        )


def test_duplicate_funnel_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match=r"mart_funnel_daily has duplicate rows for 1 keys"):
        InMemoryRepository(
            [channel_day("2020-12-01")],
            [funnel_day("2020-12-01", "visit", 3), funnel_day("2020-12-01", "visit", 4)],
        )


def test_the_same_day_and_step_on_two_channels_is_not_a_duplicate() -> None:
    InMemoryRepository(
        [channel_day("2020-12-01", "Direct"), channel_day("2020-12-01", "Email")],
        [
            funnel_day("2020-12-01", "visit", 3, "Direct"),
            funnel_day("2020-12-01", "visit", 4, "Email"),
        ],
    )


def test_empty_marts_are_rejected() -> None:
    with pytest.raises(ValueError, match="no rows"):
        InMemoryRepository([])


# --- Simulated marts ------------------------------------------------------------------------


def test_same_seed_same_rows() -> None:
    assert fake_marts(seed=7) == fake_marts(seed=7)
    assert fake_marts(seed=7) != fake_marts(seed=8)


def test_follows_the_mart_schema_zero_filled() -> None:
    channel_rows, funnel_rows = fake_marts()
    assert len(channel_rows) == 85 * 9 == 765
    assert len(funnel_rows) == 85 * 9 * 5 == 3825
    assert len({(r.date, r.channel) for r in channel_rows}) == 765
    assert len({(r.date, r.channel, r.step) for r in funnel_rows}) == 3825
    assert {r.date for r in channel_rows} == set(DATA_RANGE.dates())


def test_values_are_valid() -> None:
    channel_rows, _ = fake_marts()
    for r in channel_rows:
        assert min(r.sessions, r.orders, r.clicks, r.impressions) >= 0
        assert r.revenue >= 0 and r.spend >= 0
        assert r.revenue == r.revenue.quantize(Decimal("0.01"))  # cents
        if not r.is_paid:
            assert (r.clicks, r.impressions, r.spend) == (0, 0, 0)


def test_add_to_cart_is_not_recorded_before_26_november() -> None:
    _, funnel_rows = fake_marts()
    for r in funnel_rows:
        recorded = r.step != "add_to_cart" or r.date >= ADD_TO_CART_RECORDED_FROM
        assert r.is_tracked is recorded
        assert (r.sessions is None) is (not recorded)


def test_numbers_look_plausible() -> None:
    channel_rows, _ = fake_marts()
    paid = Totals.of(r for r in channel_rows if r.channel == "Paid Search")
    assert 0.35 < paid.roas < 0.65  # about 0.5 expected from the real generator (D21)

    revenue_per_day: defaultdict[date, Decimal] = defaultdict(Decimal)
    for r in channel_rows:
        revenue_per_day[r.date] += r.revenue
    ordinary_day = sorted(revenue_per_day.values())[len(revenue_per_day) // 2]
    assert revenue_per_day[date(2020, 11, 27)] > ordinary_day  # Black Friday peak
