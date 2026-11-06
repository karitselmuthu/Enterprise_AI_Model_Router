import os

import httpx

from app.config import ModelConfig
from app.models.contracts import (
    InferenceRequest,
    InferenceResult,
    ModelCategory,
    ModelProvider,
)
from app.models.mock import MockProvider


class ProviderFailure(Exception):
    pass


class OllamaProvider:
    def __init__(self, category: ModelCategory, config: ModelConfig) -> None:
        self.category = category
        self.config = config

    async def generate(self, request: InferenceRequest) -> InferenceResult:
        payload: dict[str, object] = {
            "model": self.config.id,
            "prompt": request.prompt,
            "stream": False,
            "options": {"num_predict": self.config.max_output_tokens},
        }
        if request.image_base64:
            payload["images"] = [request.image_base64]
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(f"{self.config.base_url.rstrip('/')}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
            output = data["response"]
            if not isinstance(output, str) or not output.strip():
                raise ValueError("empty provider response")
            return InferenceResult(
                category=self.category,
                model_id=self.config.id,
                provider="ollama",
                output=output,
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderFailure("Ollama request failed") from exc


class LiteLLMProvider:
    def __init__(self, category: ModelCategory, config: ModelConfig) -> None:
        self.category = category
        self.config = config

    async def generate(self, request: InferenceRequest) -> InferenceResult:
        key = os.getenv(self.config.api_key_env or "")
        if not key:
            raise ProviderFailure("Cloud provider credential is not configured")
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        try:
            from litellm import acompletion
        except ImportError as exc:
            raise ProviderFailure("LiteLLM is not installed") from exc
        content: str | list[dict[str, object]] = request.prompt
        if request.image_base64:
            content = [
                {"type": "text", "text": request.prompt},
                {"type": "image_url", "image_url": {"url": f"data:{request.image_mime_type};base64,{request.image_base64}"}},
            ]
        options: dict[str, object] = {}
        if self.config.reasoning_effort:
            options["reasoning_effort"] = self.config.reasoning_effort
        try:
            response = await acompletion(
                model=self.config.id,
                messages=[{"role": "user", "content": content}],
                api_key=key,
                timeout=60,
                max_tokens=self.config.max_output_tokens,
                **options,
            )
            output = response.choices[0].message.content
            if not isinstance(output, str) or not output.strip():
                raise ValueError("empty provider response")
            usage = response.usage
            return InferenceResult(
                category=self.category,
                model_id=self.config.id,
                provider="litellm",
                output=output,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
            )
        except Exception as exc:
            raise ProviderFailure("Cloud model request failed") from exc


def make_provider(category: ModelCategory, config: ModelConfig) -> ModelProvider:
    if config.provider == "mock":
        return MockProvider(category, config.id)
    if config.provider == "ollama":
        return OllamaProvider(category, config)
    return LiteLLMProvider(category, config)
