"""Application factory.

Run locally: MDP_DATA_BACKEND=fake uv run uvicorn mdp_api.main:create_app --factory --reload
"""

from fastapi import FastAPI
from google.cloud import bigquery

from mdp_api.api import router
from mdp_api.repository import MartRepository
from mdp_api.repository.bigquery import BigQueryRepository
from mdp_api.repository.fake import fake_repository
from mdp_api.settings import Settings

DESCRIPTION = """
KPIs per channel, daily trends and the purchase funnel, read from the marts.

- Dates are days, both ends included. Money is USD.
- Money and ROAS have 2 decimals; rates and % changes are fractions with 4 decimals
  (0.015 = 1.5%).
- A ratio that can't be computed (e.g. ROAS without spend) is `null`, never 0.
- Invalid dates or channels get a 422 response that says what's wrong.
"""


def build_repository(settings: Settings) -> MartRepository:
    match settings.data_backend:
        case "fake":
            return fake_repository(settings.fake_seed)
        case "bigquery":
            # Credentials come from ADC: the service account on Cloud Run, the user's locally.
            client = bigquery.Client(project=settings.bq_project, location=settings.bq_location)
            return BigQueryRepository(
                client,
                f"{settings.bq_project}.{settings.bq_dataset}",
                location=settings.bq_location,
                max_bytes_billed=settings.bq_max_bytes_billed,
                cache_seconds=settings.bq_cache_seconds,
            )
        case other:
            raise ValueError(f"unknown data backend: {other}")


def create_app(
    settings: Settings | None = None, repository: MartRepository | None = None
) -> FastAPI:
    """Builds the app. Tests pass their own `repository`; otherwise `settings` choose it."""
    app = FastAPI(
        title="Marketing Data Platform: KPI API", version="0.1.0", description=DESCRIPTION
    )
    if repository is None:
        repository = build_repository(settings or Settings())  # reads MDP_* from the env
    app.state.repository = repository
    app.include_router(router)
    return app
