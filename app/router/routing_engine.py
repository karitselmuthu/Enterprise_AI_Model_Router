from pydantic import BaseModel

from app.config import RouterConfig
from app.models.contracts import ModelCategory
from app.router.classifier import RoutingRequest, Sensitivity, TaskType, classify
from app.router.policy_engine import RoutingPolicies


class RouteUnavailable(Exception):
    pass


class PolicyDenied(Exception):
    pass


class RoutingDecision(BaseModel):
    task_type: TaskType
    sensitivity: Sensitivity
    category: ModelCategory
    model_id: str
    provider: str
    fallback_used: bool
    reason: str


class RoutingEngine:
    def __init__(self, config: RouterConfig, policies: RoutingPolicies) -> None:
        self.config = config
        self.policies = policies

    def route(self, request: RoutingRequest) -> RoutingDecision:
        task_type = classify(request)
        primary = self.policies.task_categories[task_type]
        candidates = [primary, *self.policies.fallbacks[primary]]
        denied_by_policy = False
        for category in candidates:
            model = self.config.models[category]
            if not model.enabled:
                continue
            if request.sensitivity == Sensitivity.RESTRICTED and model.provider not in self.policies.restricted_providers:
                denied_by_policy = True
                continue
            return RoutingDecision(
                task_type=task_type,
                sensitivity=request.sensitivity,
                category=category,
                model_id=model.id,
                provider=model.provider,
                fallback_used=category != primary,
                reason="primary available" if category == primary else "primary unavailable or disallowed",
            )
        if denied_by_policy:
            raise PolicyDenied("No permitted model is available for this request")
        raise RouteUnavailable("No configured model is available for this task")
