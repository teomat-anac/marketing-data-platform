"""Settings and the choice of data backend at startup."""

import os
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from mdp_api import main
from mdp_api.repository import BigQueryRepository, InMemoryRepository
from mdp_api.settings import Settings


@pytest.fixture(autouse=True)
def no_mdp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test sets exactly the variables it needs: none come from the shell."""
    for name in [n for n in os.environ if n.upper().startswith("MDP_")]:
        monkeypatch.delenv(name)


def test_data_backend_is_required() -> None:
    """A deploy that forgets the variable must not serve simulated data."""
    with pytest.raises(ValidationError, match="data_backend"):
        Settings()


def test_settings_come_from_mdp_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MDP_DATA_BACKEND", "bigquery")
    monkeypatch.setenv("MDP_BQ_PROJECT", "some-project")
    settings = Settings()
    assert (settings.data_backend, settings.bq_project) == ("bigquery", "some-project")
    assert (settings.bq_dataset, settings.bq_location) == ("marts", "US")


def test_bigquery_needs_a_project() -> None:
    with pytest.raises(ValidationError, match="MDP_BQ_PROJECT is required"):
        Settings(data_backend="bigquery")


@pytest.mark.parametrize("field", ["bq_max_bytes_billed", "bq_cache_seconds"])
def test_bigquery_limits_cannot_be_negative(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(data_backend="bigquery", bq_project="p", **{field: -1})


def test_unknown_data_backend_fails_at_startup() -> None:
    settings = Settings.model_construct(data_backend="nowhere", fake_seed=1)
    with pytest.raises(ValueError, match="unknown data backend"):
        main.create_app(settings)


def test_fake_backend_serves_the_simulated_marts() -> None:
    repository = main.build_repository(Settings(data_backend="fake"))
    assert isinstance(repository, InMemoryRepository)


def test_bigquery_backend_reads_the_configured_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}
    queries: list[str] = []

    class Client:  # stands in for bigquery.Client, which would look for credentials
        def __init__(self, **kwargs: Any) -> None:
            created.update(kwargs)

        def query(self, sql: str, **kwargs: Any) -> Any:
            queries.append(sql)
            return SimpleNamespace(result=lambda **kwargs: [])

    monkeypatch.setattr(main.bigquery, "Client", Client)
    settings = Settings(data_backend="bigquery", bq_project="p", bq_dataset="d")
    repository = main.build_repository(settings)
    assert isinstance(repository, BigQueryRepository)
    assert created == {"project": "p", "location": "US"}
    assert repository.channels() == {}
    assert "from `p.d.mart_channel_daily`" in queries[0]
