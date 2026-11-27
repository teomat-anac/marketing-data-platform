from decimal import Decimal

from mdp_api.marts import FUNNEL_STEPS
from mdp_api.metrics import KPIS, Change, Totals, compare, funnel
from mdp_api.periods import Period
from tests.factories import channel_day, day, funnel_day


def test_totals_sum_every_additive_column() -> None:
    totals = Totals.of(
        [
            channel_day(
                "2020-12-01",
                sessions=500,
                orders=30,
                revenue="3000.00",
                clicks=550,
                impressions=20000,
                spend="440.00",
            ),
            channel_day(
                "2020-12-02",
                sessions=100,
                orders=2,
                revenue="150.50",
                clicks=110,
                impressions=4000,
                spend="99.99",
            ),
        ]
    )
    assert totals == Totals(600, 32, Decimal("3150.50"), 660, 24000, Decimal("539.99"))


def test_glossary_example() -> None:
    # docs/glossary.md: 500 sessions, 30 orders, $3,000 revenue, $440 spend
    totals = Totals.of(
        [channel_day("2020-12-01", sessions=500, orders=30, revenue="3000", spend="440")]
    )
    assert round(totals.roas, 2) == Decimal("6.82")
    assert round(totals.cpa, 2) == Decimal("14.67")
    assert totals.conversion_rate == Decimal("0.06")
    assert totals.aov == Decimal("100")


def test_period_ratio_comes_from_totals_not_from_the_mean_of_daily_ratios() -> None:
    rows = [
        channel_day("2020-12-01", revenue="100", spend="100"),  # ROAS 1
        channel_day("2020-12-02", revenue="300", spend="50"),  # ROAS 6
    ]
    roas = Totals.of(rows).roas
    assert roas == Decimal(400) / Decimal(150)  # 2.67, not the mean 3.5


def test_no_spend_means_empty_roas_and_cpa_not_zero() -> None:
    organic = Totals.of(
        [channel_day("2020-12-01", "Organic Search", sessions=10, orders=1, revenue="50")]
    )
    assert organic.roas is None
    assert organic.cpa is None


def test_spend_without_orders() -> None:
    totals = Totals.of([channel_day("2020-12-01", sessions=10, spend="20")])
    assert totals.roas == 0  # money spent, nothing sold: a real zero
    assert totals.cpa is None  # no order to price
    assert totals.aov is None


def test_no_activity_gives_zeros_and_empty_ratios() -> None:
    totals = Totals.of([])
    assert (totals.sessions, totals.orders, totals.revenue, totals.spend) == (0, 0, 0, 0)
    assert totals.roas is totals.cpa is totals.conversion_rate is totals.aov is None


def test_change() -> None:
    change = Change(value=Decimal("5.1"), previous=Decimal("6.8"))
    assert change.change == Decimal("-1.7")
    assert change.change_pct == Decimal("-0.25")


def test_change_from_zero_has_no_percentage() -> None:
    change = Change(value=5, previous=0)
    assert change.change == 5
    assert change.change_pct is None


def test_change_with_an_empty_side_is_empty() -> None:
    assert Change(value=Decimal(2), previous=None).change is None
    assert Change(value=None, previous=Decimal(2)).change_pct is None


def test_compare_covers_every_kpi() -> None:
    current = Totals(sessions=110, orders=2, revenue=Decimal(200), spend=Decimal(100))
    previous = Totals(sessions=100, orders=2, revenue=Decimal(100), spend=Decimal(100))
    result = compare(current, previous)
    assert tuple(result) == KPIS
    assert result["sessions"].change == 10
    assert result["roas"].change_pct == Decimal(1)


def test_compare_without_previous_period() -> None:
    result = compare(Totals(sessions=1), None)
    assert all(c.previous is None and c.change is None for c in result.values())
    assert result["sessions"].value == 1


BOTH = ("Direct", "Paid Search")


def test_funnel_sums_days_and_channels_and_computes_step_rates() -> None:
    reached = {
        "visit": 500,
        "view_item": 250,
        "add_to_cart": 50,
        "begin_checkout": 20,
        "purchase": 5,
    }  # per day and channel
    rows = [
        funnel_day(on, step, sessions, channel)
        for on in ("2020-12-01", "2020-12-02")
        for channel in BOTH
        for step, sessions in reached.items()
    ]
    two_days = Period(day("2020-12-01"), day("2020-12-02"))
    steps = funnel(reversed(rows), two_days, BOTH)  # input order doesn't matter
    assert [(s.step, s.sessions) for s in steps] == [
        ("visit", 2000),
        ("view_item", 1000),
        ("add_to_cart", 200),
        ("begin_checkout", 80),
        ("purchase", 20),
    ]
    assert [s.rate_from_previous for s in steps] == [
        None,
        Decimal("0.5"),
        Decimal("0.2"),
        Decimal("0.4"),
        Decimal("0.25"),
    ]
    assert all(s.is_tracked for s in steps)


def full_day(on: str, channel: str = "Direct", skip: str | None = None) -> list:
    """Rows for every step of one day and channel (10 sessions each), except `skip`."""
    return [
        funnel_day(on, step, 10, channel)
        for step in ("visit", "view_item", "add_to_cart", "begin_checkout", "purchase")
        if step != skip
    ]


def test_a_step_not_recorded_on_some_days_is_not_recorded_for_the_period() -> None:
    days = ("2020-11-24", "2020-11-25", "2020-11-26")
    rows = [r for on in days for r in full_day(on, skip="add_to_cart")]
    rows += [
        funnel_day("2020-11-24", "add_to_cart", None),
        funnel_day("2020-11-25", "add_to_cart", None),
        funnel_day("2020-11-26", "add_to_cart", 30),
    ]
    period = Period(day("2020-11-24"), day("2020-11-26"))
    _, view_item, add_to_cart, begin_checkout, _ = funnel(rows, period, ["Direct"])
    assert add_to_cart.sessions is None  # never 0
    assert not add_to_cart.is_tracked
    assert add_to_cart.untracked_days == 2
    assert add_to_cart.rate_from_previous is None  # rate into the step
    assert begin_checkout.sessions == 30
    assert begin_checkout.rate_from_previous is None  # rate out of the step
    assert view_item.is_tracked


def test_days_without_rows_count_as_not_recorded() -> None:
    rows = [r for on in ("2020-12-01", "2020-12-02") for r in full_day(on, skip="add_to_cart")]
    rows += full_day("2020-12-03")  # add_to_cart has a row only on 3 Dec
    steps = {
        s.step: s for s in funnel(rows, Period(day("2020-12-01"), day("2020-12-03")), ["Direct"])
    }
    assert steps["add_to_cart"].sessions is None
    assert steps["add_to_cart"].untracked_days == 2
    assert steps["begin_checkout"].rate_from_previous is None


def test_a_channel_without_a_row_makes_the_day_not_recorded() -> None:
    # Paid Search has no add_to_cart row on 1 Dec: summing Direct alone would give a
    # begin_checkout rate far above 100%
    rows = full_day("2020-12-01", "Direct") + full_day(
        "2020-12-01", "Paid Search", skip="add_to_cart"
    )
    steps = {s.step: s for s in funnel(rows, Period(day("2020-12-01"), day("2020-12-01")), BOTH)}
    assert steps["add_to_cart"].sessions is None
    assert steps["add_to_cart"].untracked_days == 1
    assert steps["begin_checkout"].rate_from_previous is None
    assert steps["view_item"].sessions == 20


def test_a_step_without_any_row_is_still_listed_as_not_recorded() -> None:
    period = Period(day("2020-12-01"), day("2020-12-01"))
    rows = [funnel_day("2020-12-01", s, 10) for s in ("visit", "view_item", "purchase")]
    steps = funnel(rows, period, ["Direct"])
    assert [s.step for s in steps] == [
        "visit",
        "view_item",
        "add_to_cart",
        "begin_checkout",
        "purchase",
    ]
    assert [s.is_tracked for s in steps] == [True, True, False, False, True]
    assert steps[4].rate_from_previous is None  # never purchase ÷ view_item


def test_funnel_accepts_channels_as_a_generator() -> None:
    rows = [
        funnel_day(on, step, 10, channel)
        for on in ("2020-12-01", "2020-12-02")
        for channel in BOTH
        for step in FUNNEL_STEPS
    ]
    two_days = Period(day("2020-12-01"), day("2020-12-02"))
    from_tuple = funnel(rows, two_days, BOTH)
    from_generator = funnel(rows, two_days, (channel for channel in BOTH))
    assert from_generator == from_tuple
    assert from_generator[0].sessions == 40
