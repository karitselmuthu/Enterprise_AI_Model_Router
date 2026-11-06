import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from app.models.contracts import ModelCategory
from app.router.classifier import TaskType


DEFAULT_POLICIES = Path(__file__).resolve().parent.parent.parent / "configs" / "routing_policies.yaml"


class RoutingPolicies(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_categories: dict[TaskType, ModelCategory]
    fallbacks: dict[ModelCategory, list[ModelCategory]]
    restricted_providers: set[str]

    @model_validator(mode="after")
    def require_complete_policy(self) -> "RoutingPolicies":
        if set(self.task_categories) != set(TaskType):
            raise ValueError("task_categories must define every task type")
        if set(self.fallbacks) != set(ModelCategory):
            raise ValueError("fallbacks must define every model category")
        for primary, alternatives in self.fallbacks.items():
            if primary in alternatives or len(set(alternatives)) != len(alternatives):
                raise ValueError(f"invalid fallback list for {primary}")
        return self


def load_policies(path: Path | None = None) -> RoutingPolicies:
    policy_path = path or Path(os.getenv("ROUTER_POLICIES_CONFIG", DEFAULT_POLICIES))
    with policy_path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    return RoutingPolicies.model_validate(data)
