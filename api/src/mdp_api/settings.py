"""Settings, read from environment variables with the `MDP_` prefix."""

from typing import Literal, Self

from pydantic import NonNegativeInt, PositiveInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MDP_")

    # Where the marts are read from: "bigquery" for the real marts, "fake" for seeded
    # simulated data (local runs). Required, with no default: a deploy that forgets it
    # must fail at startup, not serve believable simulated numbers.
    data_backend: Literal["fake", "bigquery"]

    # --- fake ---
    # Seed of the simulated data: the same seed always gives the same rows.
    fake_seed: int = 42

    # --- bigquery ---
    # Project that holds the marts dataset; queries run (and are billed) in it too.
    bq_project: str | None = None
    bq_dataset: str = "marts"
    # Location of the datasets: US, where the GA4 sample is (D7).
    bq_location: str = "US"
    # Byte cap on every query (docs/costs.md §1). A mart is well under 1 MB, but BigQuery
    # bills at least 10 MB per table a query reads.
    bq_max_bytes_billed: PositiveInt = 100_000_000
    # How long the data range and the channel list are kept before they are read again.
    bq_cache_seconds: NonNegativeInt = 600

    @model_validator(mode="after")
    def _bigquery_needs_a_project(self) -> Self:
        if self.data_backend == "bigquery" and not self.bq_project:
            raise ValueError("MDP_BQ_PROJECT is required when MDP_DATA_BACKEND is bigquery")
        return self
