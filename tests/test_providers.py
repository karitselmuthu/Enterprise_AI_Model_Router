import asyncio
import sys
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import ModelConfig
from app.main import create_app
from app.models.contracts import InferenceRequest, ModelCategory
from app.models.providers import LiteLLMProvider, OllamaProvider


def test_ollama_provider_request_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    client_options: list[dict] = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url: str, json: dict):
            calls.append({"url": url, "json": json})
            return httpx.Response(
                200,
                json={"response": "severity: high", "prompt_eval_count": 7, "eval_count": 3},
                request=httpx.Request("POST", url),
            )

    def make_client(**kwargs):
        client_options.append(kwargs)
        return FakeClient()

    monkeypatch.setattr("app.models.providers.httpx.AsyncClient", make_client)
    provider = OllamaProvider(
        ModelCategory.SLM,
        ModelConfig(id="qwen2.5:0.5b", provider="ollama", base_url="http://localhost:11434", timeout_seconds=90),
    )
    result = asyncio.run(provider.generate(InferenceRequest(category="SLM", prompt="Classify alert")))
    assert result.output == "severity: high"
    assert result.prompt_tokens == 7
    assert calls[0]["url"] == "http://localhost:11434/api/generate"
    assert calls[0]["json"]["stream"] is False
    assert client_options[0]["timeout"] > 90


def test_litellm_provider_uses_env_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    async def fake_completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="A concise answer"))],
            usage=SimpleNamespace(prompt_tokens=4, completion_tokens=5),
        )

    monkeypatch.setenv("TEST_LLM_KEY", "test-secret")
    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_completion))
    provider = LiteLLMProvider(
        ModelCategory.LRM,
        ModelConfig(
            id="openai/test", provider="litellm", api_key_env="TEST_LLM_KEY",
            reasoning_effort="medium", input_usd_per_million_tokens=1,
            output_usd_per_million_tokens=4, timeout_seconds=90,
        ),
    )
    result = asyncio.run(provider.generate(InferenceRequest(category="LRM", prompt="Analyze root cause")))
    assert result.output == "A concise answer"
    assert calls[0]["api_key"] == "test-secret"
    assert calls[0]["reasoning_effort"] == "medium"
    assert calls[0]["timeout"] > 90


def test_execute_uses_routing_with_mock_provider() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/execute", json={"prompt": "Classify the pod restart"})
    assert response.status_code == 200
    assert response.json()["decision"]["category"] == "SLM"
    assert response.json()["result"]["provider"] == "mock"


def test_invalid_image_is_rejected() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/execute",
            json={"prompt": "Read dashboard", "image_base64": "not base64", "image_mime_type": "image/png"},
        )
    assert response.status_code == 422


def test_restricted_direct_inference_blocks_cloud(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            "/v1/infer", json={"category": "LLM", "prompt": "private incident", "sensitivity": "restricted"}
        )
    assert response.status_code == 403
