from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from mdp_api.main import create_app
from mdp_api.repository import InMemoryRepository
from mdp_api.repository.fake import fake_repository
from tests.factories import channel_day, day, funnel_day


def two_weeks() -> InMemoryRepository:
    """Hand-made marts, 1-14 Dec 2020, with values chosen so the KPIs are easy to check.

    Per day, week 1 (1-7 Dec) → week 2 (8-14 Dec):
      Paid Search: 100 → 120 sessions, 1 → 2 orders, $50 → $60 revenue, $40 → $50 spend
      Direct:      200 → 200 sessions, 2 → 2 orders, $150 → $160 revenue, no spend
    """
    channel_rows, funnel_rows = [], []
    for offset in range(14):
        on = (day("2020-12-01") + timedelta(days=offset)).isoformat()
        week2 = offset >= 7
        channel_rows += [
            channel_day(
                on,
                "Paid Search",
                sessions=120 if week2 else 100,
                orders=2 if week2 else 1,
                revenue="60" if week2 else "50",
                clicks=130 if week2 else 110,
                impressions=4000 if week2 else 3000,
                spend="50" if week2 else "40",
            ),
            channel_day(on, "Direct", sessions=200, orders=2, revenue="160" if week2 else "150"),
        ]
        for channel in ("Paid Search", "Direct"):
            funnel_rows += [
                funnel_day(on, "visit", 100, channel),
                funnel_day(on, "view_item", 50, channel),
                funnel_day(on, "add_to_cart", 20 if week2 else None, channel),  # gap in week 1
                funnel_day(on, "begin_checkout", 10, channel),
                funnel_day(on, "purchase", 2, channel),
            ]
    return InMemoryRepository(channel_rows, funnel_rows)


@pytest.fixture
def client() -> TestClient:
    """The API on the hand-made marts above."""
    return TestClient(create_app(repository=two_weeks()))


@pytest.fixture(scope="session")
def fake_client() -> TestClient:
    """The API on the full simulated marts, as served locally."""
    return TestClient(create_app(repository=fake_repository()))
