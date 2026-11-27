"""The cost generator's rules (D21) on hand-made sessions; no BigQuery."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from mdp_pipeline.bigquery_io import to_json_row
from mdp_pipeline.generator import AdSpendRow, PaidSessions, generate
from mdp_pipeline.settings import CAMPAIGNS, DEFAULT_SEED, Campaign

PAID = "Paid Search"
START = date(2020, 11, 1)


def sessions(days: int = 30, per_day: int = 140, channel: str = PAID) -> list[PaidSessions]:
    return [PaidSessions(START + timedelta(days=i), channel, per_day + i) for i in range(days)]


def test_same_input_and_seed_give_identical_rows():
    assert generate(sessions(), CAMPAIGNS, 7) == generate(sessions(), CAMPAIGNS, 7)


def test_input_order_does_not_matter():
    days = sessions()
    assert generate(list(reversed(days)), CAMPAIGNS, 7) == generate(days, CAMPAIGNS, 7)


def test_another_seed_gives_other_values():
    assert generate(sessions(), CAMPAIGNS, 7) != generate(sessions(), CAMPAIGNS, 8)


def test_a_row_does_not_change_when_the_range_changes():
    """Each row has its own random draws: adding days doesn't shift the others (FR-5)."""
    short = generate(sessions(days=10), CAMPAIGNS, DEFAULT_SEED)
    long = generate(sessions(days=30), CAMPAIGNS, DEFAULT_SEED)
    assert long[:10] == short


def test_values_stay_within_the_d21_ranges():
    for day, row in zip(
        sessions(days=200), generate(sessions(days=200), CAMPAIGNS, 1), strict=True
    ):
        assert row.channel == PAID and row.campaign == "Search - Generic"
        # clicks = sessions × 1.05 to 1.15, rounded
        assert round(day.sessions * 1.05) <= row.clicks <= round(day.sessions * 1.15)
        # CPC = $1.00 × 0.85 to 1.15 (spend is rounded to cents)
        cpc = row.spend / row.clicks
        assert Decimal("0.849") <= cpc <= Decimal("1.151")
        # CTR = 3% × 0.9 to 1.1 (impressions are rounded)
        assert 0.0269 <= row.clicks / row.impressions <= 0.0331


def test_spend_is_in_cents():
    for row in generate(sessions(), CAMPAIGNS, 3):
        assert row.spend == row.spend.quantize(Decimal("0.01"))
        assert row.spend.as_tuple().exponent == -2


def test_the_daily_factors_spread_over_their_ranges():
    """The factors vary from day to day across the D21 ranges, rather than staying put."""
    days = sessions(days=100, per_day=1000)
    rows = generate(days, CAMPAIGNS, 3)
    click_factors = [r.clicks / d.sessions for d, r in zip(days, rows, strict=True)]
    cpcs = [r.spend / r.clicks for r in rows]
    assert min(click_factors) < 1.07 and max(click_factors) > 1.13
    assert min(cpcs) < Decimal("0.90") and max(cpcs) > Decimal("1.10")


def test_a_day_without_sessions_has_no_row():
    days = [PaidSessions(START, PAID, 0), PaidSessions(START + timedelta(days=1), PAID, 100)]
    rows = generate(days, CAMPAIGNS, 1)
    assert [r.date for r in rows] == [START + timedelta(days=1)]


def test_no_sessions_at_all_is_an_error():
    with pytest.raises(ValueError, match="No paid sessions"):
        generate([], CAMPAIGNS, 1)


def test_only_days_without_sessions_is_an_error():
    with pytest.raises(ValueError, match="No paid sessions"):
        generate([PaidSessions(START, PAID, 0)], CAMPAIGNS, 1)


def test_a_channel_without_a_campaign_is_an_error():
    with pytest.raises(ValueError, match="No campaign set up"):
        generate(sessions(channel="Display"), CAMPAIGNS, 1)


def test_negative_sessions_are_an_error():
    with pytest.raises(ValueError, match="Negative sessions"):
        generate([PaidSessions(START, PAID, -1)], CAMPAIGNS, 1)


def test_two_campaigns_for_one_channel_are_rejected():
    campaigns = (Campaign(PAID, "A"), Campaign(PAID, "B"))
    with pytest.raises(ValueError, match="More than one campaign"):
        generate(sessions(), campaigns, 1)


def test_the_campaign_settings_are_used():
    cheap = (Campaign(PAID, "Cheap", cpc=Decimal("0.10"), cpc_factor=(1.0, 1.0)),)
    rows = generate(sessions(days=5), cheap, 1)
    assert all(r.spend == (r.clicks * Decimal("0.10")).quantize(Decimal("0.01")) for r in rows)


def test_json_row_keeps_money_exact():
    row = AdSpendRow(START, PAID, "Search - Generic", 4321, 130, Decimal("128.07"))
    loaded_at = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
    assert to_json_row(row, loaded_at) == {
        "date": "2020-11-01",
        "channel": PAID,
        "campaign": "Search - Generic",
        "impressions": 4321,
        "clicks": 130,
        "spend": "128.07",
        "loaded_at": "2026-11-25T12:00:00+00:00",
    }
