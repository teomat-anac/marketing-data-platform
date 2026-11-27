from fastapi.testclient import TestClient

from mdp_api.main import create_app
from mdp_api.settings import Settings


def test_health() -> None:
    client = TestClient(create_app(Settings(data_backend="fake")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
