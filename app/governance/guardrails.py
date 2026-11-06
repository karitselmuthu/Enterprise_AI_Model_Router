import math
import re
from urllib.parse import urlparse

from app.config import ModelConfig
from app.observability.metrics import observe_budget_rejection
from app.router.classifier import Sensitivity
from app.router.policy_engine import RoutingPolicies

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
US_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def effective_sensitivity(prompt: str, declared: Sensitivity | str) -> Sensitivity:
    if declared == Sensitivity.RESTRICTED or EMAIL.search(prompt) or US_SSN.search(prompt):
        return Sensitivity.RESTRICTED
    return Sensitivity(declared)


def estimated_max_cost_usd(prompt: str, model: ModelConfig) -> float:
    if model.provider != "litellm":
        return 0.0
    input_tokens = math.ceil(len(prompt) / 4)
    return (
        input_tokens * (model.input_usd_per_million_tokens or 0)
        + model.max_output_tokens * (model.output_usd_per_million_tokens or 0)
    ) / 1_000_000


def model_allowed(
    prompt: str, sensitivity: Sensitivity, model: ModelConfig, policies: RoutingPolicies
) -> bool:
    if model.provider == "litellm" and estimated_max_cost_usd(prompt, model) > policies.max_cloud_estimated_cost_usd:
        observe_budget_rejection(model.provider)
        return False
    if sensitivity != Sensitivity.RESTRICTED:
        return True
    if model.provider not in policies.restricted_providers or model.provider == "litellm":
        return False
    if model.provider == "ollama":
        return urlparse(model.base_url or "").hostname in LOCAL_HOSTS
    return True
