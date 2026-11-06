from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.parametrize(
    ("prompt", "expected_task", "expected_category"),
    [
        ("Classify a Kubernetes pod restart alert", "classification", "SLM"),
        ("Extract incident metadata", "extraction", "SLM"),
        ("Summarize a short log", "short_summary", "SLM"),
        ("Answer from the knowledge base", "knowledge", "LLM"),
        ("Analyze root cause of this outage", "reasoning", "LRM"),
    ],
)
def test_deterministic_routing(prompt: str, expected_task: str, expected_category: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/route", json={"prompt": prompt})
    assert response.status_code == 200
    assert response.json()["task_type"] == expected_task
    assert response.json()["category"] == expected_category
    assert response.json()["fallback_used"] is False


def test_image_signal_overrides_text_task() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/route",
            json={"prompt": "Classify this dashboard", "task_type": "classification", "contains_image": True},
        )
    assert response.status_code == 200
    assert response.json()["category"] == "VLM"


def test_disabled_primary_uses_configured_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        "models:\n"
        "  SLM: {id: mock-slm, provider: mock, enabled: false}\n"
        "  LLM: {id: mock-llm, provider: mock}\n"
        "  LRM: {id: mock-lrm, provider: mock}\n"
        "  VLM: {id: mock-vlm, provider: mock}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROUTER_MODELS_CONFIG", str(path))
    with TestClient(create_app()) as client:
        response = client.post("/v1/route", json={"prompt": "Classify a ticket"})
    assert response.status_code == 200
    assert response.json()["category"] == "LLM"
    assert response.json()["fallback_used"] is True


def test_unavailable_vision_does_not_fall_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        "models:\n"
        "  SLM: {id: mock-slm, provider: mock}\n"
        "  LLM: {id: mock-llm, provider: mock}\n"
        "  LRM: {id: mock-lrm, provider: mock}\n"
        "  VLM: {id: mock-vlm, provider: mock, enabled: false}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROUTER_MODELS_CONFIG", str(path))
    with TestClient(create_app()) as client:
        response = client.post("/v1/route", json={"prompt": "Read dashboard", "contains_image": True})
    assert response.status_code == 503


def test_invalid_route_request() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/route", json={"prompt": "   ", "sensitivity": "secret"})
    assert response.status_code == 422
