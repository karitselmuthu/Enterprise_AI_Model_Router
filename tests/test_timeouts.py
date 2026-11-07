import asyncio
import json
import logging
from threading import Event

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import ModelConfig
from app.main import create_app
from app.models.contracts import InferenceResult


def configure_models(tmp_path, monkeypatch: pytest.MonkeyPatch, *, llm_provider: str = "mock") -> None:
    config = tmp_path / "models.yaml"
    llm = (
        "{id: cloud-llm, provider: litellm, api_key_env: TEST_LLM_KEY, "
        "input_usd_per_million_tokens: 1, output_usd_per_million_tokens: 1, timeout_seconds: 0.02}"
        if llm_provider == "litellm"
        else "{id: mock-llm, provider: mock, timeout_seconds: 0.1}"
    )
    config.write_text(
        "models:\n"
        "  SLM: {id: mock-slm, provider: mock, timeout_seconds: 0.02}\n"
        f"  LLM: {llm}\n"
        "  LRM: {id: mock-lrm, provider: mock, timeout_seconds: 0.02}\n"
        "  VLM: {id: mock-vlm, provider: mock, timeout_seconds: 0.02}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROUTER_MODELS_CONFIG", str(config))


def test_direct_timeout_returns_504_and_records_outcome(tmp_path, monkeypatch, caplog) -> None:
    configure_models(tmp_path, monkeypatch)
    cancelled = Event()

    class SlowProvider:
        async def generate(self, _request):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr("app.api.routes.make_provider", lambda *_: SlowProvider())
    with caplog.at_level(logging.INFO, logger="enterprise_router.audit"), TestClient(create_app()) as client:
        response = client.post("/v1/infer", json={"category": "SLM", "prompt": "Classify ticket"})
        metrics = client.get("/metrics").text

    assert response.status_code == 504
    assert cancelled.is_set()
    assert 'router_provider_attempts_total{category="SLM",outcome="timeout",provider="mock"}' in metrics
    events = [json.loads(record.message) for record in caplog.records if record.name == "enterprise_router.audit"]
    assert events[-1]["outcome"] == "timeout"
    assert events[-1]["request_id"] == response.headers["X-Request-ID"]


def test_routed_timeout_falls_back_to_responsive_model(tmp_path, monkeypatch, caplog) -> None:
    configure_models(tmp_path, monkeypatch)
    cancelled = Event()

    class Provider:
        def __init__(self, category, model_id):
            self.category = category
            self.model_id = model_id

        async def generate(self, _request):
            if self.category == "SLM":
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
            return InferenceResult(category=self.category, model_id=self.model_id, provider="mock", output="Accepted answer")

    monkeypatch.setattr("app.api.routes.make_provider", lambda category, model: Provider(category, model.id))
    with caplog.at_level(logging.INFO, logger="enterprise_router.audit"), TestClient(create_app()) as client:
        response = client.post("/v1/execute", json={"prompt": "Classify ticket"})

    assert response.status_code == 200
    assert response.json()["decision"]["category"] == "LLM"
    assert response.json()["attempts"] == 2
    assert cancelled.is_set()
    events = [json.loads(record.message) for record in caplog.records if record.name == "enterprise_router.audit"]
    assert [event["outcome"] for event in events[-2:]] == ["timeout", "accepted"]
    assert all(event["request_id"] == response.headers["X-Request-ID"] for event in events[-2:])


def test_all_candidates_time_out_with_controlled_504(tmp_path, monkeypatch) -> None:
    configure_models(tmp_path, monkeypatch)

    class SlowProvider:
        async def generate(self, _request):
            await asyncio.Event().wait()

    monkeypatch.setattr("app.api.routes.make_provider", lambda *_: SlowProvider())
    with TestClient(create_app()) as client:
        response = client.post("/v1/execute", json={"prompt": "Classify ticket"})
    assert response.status_code == 504


def test_fast_provider_still_succeeds(tmp_path, monkeypatch) -> None:
    configure_models(tmp_path, monkeypatch)

    class FastProvider:
        async def generate(self, request):
            return InferenceResult(category=request.category, model_id="mock-slm", provider="mock", output="Accepted answer")

    monkeypatch.setattr("app.api.routes.make_provider", lambda *_: FastProvider())
    with TestClient(create_app()) as client:
        response = client.post("/v1/infer", json={"category": "SLM", "prompt": "Classify ticket"})
    assert response.status_code == 200


def test_restricted_request_does_not_fall_back_to_cloud(tmp_path, monkeypatch) -> None:
    configure_models(tmp_path, monkeypatch, llm_provider="litellm")
    called_categories = []

    class SlowProvider:
        def __init__(self, category):
            self.category = category

        async def generate(self, _request):
            called_categories.append(self.category)
            await asyncio.Event().wait()

    monkeypatch.setattr("app.api.routes.make_provider", lambda category, _: SlowProvider(category))
    with TestClient(create_app()) as client:
        response = client.post("/v1/execute", json={"prompt": "Classify alice@example.com", "sensitivity": "restricted"})
    assert response.status_code == 504
    assert called_categories == ["SLM"]


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_invalid_timeout_configuration(value: float) -> None:
    with pytest.raises(ValidationError):
        ModelConfig(id="mock-slm", provider="mock", timeout_seconds=value)


def test_long_summary_routes_to_llm() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/route", json={"prompt": "Summarize " + "incident detail " * 40})
    assert response.status_code == 200
    assert response.json()["category"] == "LLM"
