import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.contracts import ModelCategory

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "models.yaml"


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    provider: Literal["mock", "ollama", "litellm"]
    enabled: bool = True
    base_url: str | None = None
    api_key_env: str | None = None
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    max_output_tokens: int = Field(default=512, ge=1, le=8192)
    timeout_seconds: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    input_usd_per_million_tokens: float | None = Field(default=None, ge=0)
    output_usd_per_million_tokens: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "ModelConfig":
        if self.provider == "ollama" and not self.base_url:
            raise ValueError("ollama provider requires base_url")
        if self.provider == "litellm" and not self.api_key_env:
            raise ValueError("litellm provider requires api_key_env")
        if self.provider == "litellm" and (
            self.input_usd_per_million_tokens is None
            or self.output_usd_per_million_tokens is None
        ):
            raise ValueError("litellm provider requires configured token prices for budget checks")
        if self.base_url and not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be HTTP or HTTPS")
        return self


class RouterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: dict[ModelCategory, ModelConfig]

    @model_validator(mode="after")
    def require_all_categories(self) -> "RouterConfig":
        missing = set(ModelCategory) - set(self.models)
        if missing:
            raise ValueError(f"Missing model categories: {', '.join(sorted(missing))}")
        return self


def load_config(path: Path | None = None) -> RouterConfig:
    config_path = path or Path(os.getenv("ROUTER_MODELS_CONFIG", DEFAULT_CONFIG))
    with config_path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    return RouterConfig.model_validate(data)
