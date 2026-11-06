import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_and_model_catalog(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    models = client.get("/v1/models")
    assert models.status_code == 200
    assert models.json() == [
        {"category": category, "model_id": f"mock-{category.lower()}", "provider": "mock"}
        for category in ("SLM", "LLM", "LRM", "VLM")
    ]


@pytest.mark.parametrize("category", ["SLM", "LLM", "LRM", "VLM"])
def test_mock_inference(client: TestClient, category: str) -> None:
    response = client.post(
        "/v1/infer", json={"category": category, "prompt": "Classify a pod restart"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "category": category,
        "model_id": f"mock-{category.lower()}",
        "provider": "mock",
        "output": f"Mock {category} response for: Classify a pod restart",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"category": "UNKNOWN", "prompt": "test"},
        {"category": "SLM", "prompt": "   "},
        {"category": "SLM", "prompt": "test", "unexpected": True},
    ],
)
def test_invalid_inference_returns_422(client: TestClient, payload: dict) -> None:
    assert client.post("/v1/infer", json=payload).status_code == 422
