import pytest

from mdp_api.periods import Period
from tests.factories import day


def test_both_ends_are_included() -> None:
    assert Period(day("2020-12-01"), day("2020-12-07")).days == 7
    assert Period(day("2020-12-01"), day("2020-12-01")).days == 1


def test_start_after_end_is_rejected() -> None:
    with pytest.raises(ValueError, match="after"):
        Period(day("2020-12-02"), day("2020-12-01"))


def test_previous_period_has_the_same_length_and_ends_the_day_before() -> None:
    week = Period(day("2020-12-01"), day("2020-12-07"))
    assert week.previous() == Period(day("2020-11-24"), day("2020-11-30"))
    single = Period(day("2021-01-01"), day("2021-01-01"))
    assert single.previous() == Period(day("2020-12-31"), day("2020-12-31"))


def test_contains() -> None:
    data = Period(day("2020-11-01"), day("2021-01-24"))
    assert data.contains(Period(day("2020-11-01"), day("2021-01-24")))
    assert not data.contains(Period(day("2020-10-31"), day("2020-11-07")))
    assert day("2020-11-01") in data
    assert day("2021-01-25") not in data


def test_dates() -> None:
    period = Period(day("2020-12-30"), day("2021-01-02"))
    assert [d.isoformat() for d in period.dates()] == [
        "2020-12-30",
        "2020-12-31",
        "2021-01-01",
        "2021-01-02",
    ]
