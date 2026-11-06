import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.contracts import ModelCategory


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "models.yaml"


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    provider: str = Field(pattern="^mock$")
    enabled: bool = True


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
