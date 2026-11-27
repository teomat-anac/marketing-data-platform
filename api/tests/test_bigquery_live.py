"""The API on the real marts in BigQuery. Opt-in: it needs credentials and is billed.

Run by hand, after a pipeline run or a change to the BigQuery repository:

    MDP_BQ_PROJECT=<project-id> uv run pytest -m bigquery

About five queries of 10-20 MB each, every one under the byte cap. The expected figures are
the results in data-sources.md §5; update them if the pipeline's rules change.
"""

import pytest
from fastapi.testclient import TestClient

from mdp_api.main import create_app
from mdp_api.settings import Settings

pytestmark = pytest.mark.bigquery

FULL_RANGE = "start=2020-11-01&end=2021-01-24"


@pytest.fixture(scope="module")
def api() -> TestClient:
    settings = Settings(data_backend="bigquery")  # project and dataset from MDP_BQ_*
    return TestClient(create_app(settings))


def test_kpi_totals_match_the_marts(api: TestClient) -> None:
    response = api.get(f"/kpi?{FULL_RANGE}")
    assert response.status_code == 200, response.text
    body = response.json()
    total = {name: metric["value"] for name, metric in body["total"].items()}
    assert total["sessions"] == 333_787
    assert total["orders"] == 5_030
    assert total["revenue"] == 335_469
    assert total["spend"] == 13_333.97
    assert (total["clicks"], total["impressions"]) == (13_427, 445_565)
    assert len(body["channels"]) == 9
    assert [c["channel"] for c in body["channels"] if c["is_paid"]] == ["Paid Search"]
    assert body["previous_period"]["available"] is False  # nothing before 1 Nov 2020


def test_funnel_matches_the_marts(api: TestClient) -> None:
    response = api.get(f"/funnel?{FULL_RANGE}")
    assert response.status_code == 200, response.text
    steps = {s["step"]: s for s in response.json()["steps"]}
    assert {name: s["sessions"] for name, s in steps.items()} == {
        "visit": 333_787,
        "view_item": 70_833,
        "add_to_cart": None,  # not recorded 1-25 Nov 2020 (D20)
        "begin_checkout": 10_526,
        "purchase": 4_538,
    }
    assert steps["add_to_cart"]["untracked_days"] == 25


def test_dates_outside_the_data_are_rejected(api: TestClient) -> None:
    response = api.get("/kpi?start=2020-10-31&end=2020-11-30")
    assert response.status_code == 422
    assert "data is available from 2020-11-01 to 2021-01-24" in response.text
