import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import ModelConfig
from app.governance.guardrails import model_allowed
from app.models.contracts import InferenceResult
from app.router.classifier import Sensitivity
from app.router.policy_engine import load_policies


def test_detected_email_upgrades_sensitivity() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/route",
            json={"prompt": "Classify ticket from alice@example.com", "sensitivity": "public"},
        )
    assert response.status_code == 200
    assert response.json()["sensitivity"] == "restricted"


def test_detected_pii_blocks_direct_cloud_inference(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        "models:\n"
        "  SLM: {id: mock-slm, provider: mock}\n"
        "  LLM: {id: openai/test, provider: litellm, api_key_env: TEST_LLM_KEY, input_usd_per_million_tokens: 1, output_usd_per_million_tokens: 4}\n"
        "  LRM: {id: mock-lrm, provider: mock}\n"
        "  VLM: {id: mock-vlm, provider: mock}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROUTER_MODELS_CONFIG", str(path))
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/infer",
            json={"category": "LLM", "prompt": "Email alice@example.com", "sensitivity": "public"},
        )
    assert response.status_code == 403


def test_quality_failure_escalates_to_configured_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        def __init__(self, category, model_id):
            self.category = category
            self.model_id = model_id

        async def generate(self, _request):
            return InferenceResult(
                category=self.category, model_id=self.model_id, provider="ollama",
                output="I don't know" if self.category == "SLM" else "The answer is available.",
            )

    monkeypatch.setattr(
        "app.api.routes.make_provider",
        lambda category, model: FakeProvider(category, model.id),
    )
    with TestClient(create_app()) as client:
        response = client.post("/v1/execute", json={"prompt": "Classify a ticket"})
    assert response.status_code == 200
    assert response.json()["decision"]["category"] == "LLM"
    assert response.json()["attempts"] == 2
    assert response.json()["quality"]["accepted"] is True


def test_audit_event_excludes_prompt_and_output(caplog: pytest.LogCaptureFixture) -> None:
    secret_text = "incident alice@example.com"
    with caplog.at_level(logging.INFO, logger="enterprise_router.audit"):
        with TestClient(create_app()) as client:
            response = client.post("/v1/execute", json={"prompt": secret_text})
    assert response.status_code == 200
    records = [json.loads(record.message) for record in caplog.records if record.name == "enterprise_router.audit"]
    assert records and records[-1]["sensitivity"] == "restricted"
    assert all(secret_text not in json.dumps(record) for record in records)
    assert all("output" not in record for record in records)


def test_cloud_cost_ceiling_blocks_oversized_estimate() -> None:
    model = ModelConfig(
        id="openai/test", provider="litellm", api_key_env="TEST_LLM_KEY",
        input_usd_per_million_tokens=100, output_usd_per_million_tokens=100,
    )
    assert not model_allowed("Explain this incident", Sensitivity.PUBLIC, model, load_policies())


def test_restricted_data_rejects_remote_ollama_host() -> None:
    model = ModelConfig(id="remote-model", provider="ollama", base_url="https://remote.example.com")
    assert not model_allowed("private incident", Sensitivity.RESTRICTED, model, load_policies())
