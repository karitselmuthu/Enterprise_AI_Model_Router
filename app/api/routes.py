from fastapi import APIRouter, HTTPException

from app.config import RouterConfig
from app.models.contracts import InferenceRequest, InferenceResult, ModelCategory
from app.models.providers import ProviderFailure, make_provider
from app.router.classifier import ExecutionRequest, RoutingRequest, Sensitivity
from app.router.policy_engine import RoutingPolicies
from app.router.routing_engine import PolicyDenied, RouteUnavailable, RoutingDecision, RoutingEngine
from pydantic import BaseModel


class ExecutionResult(BaseModel):
    decision: RoutingDecision
    result: InferenceResult


def build_router(config: RouterConfig, policies: RoutingPolicies) -> APIRouter:
    router = APIRouter()
    engine = RoutingEngine(config, policies)
    providers = {
        category: make_provider(category, model)
        for category, model in config.models.items()
    }

    @router.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready")
    def ready() -> dict[str, str]:
        return {"status": "ready"}

    @router.get("/v1/models")
    def models() -> list[dict[str, str]]:
        return [
            {"category": category.value, "model_id": config.models[category].id, "provider": config.models[category].provider}
            for category in ModelCategory
        ]

    @router.post("/v1/infer", response_model=InferenceResult, response_model_exclude_none=True)
    async def infer(request: InferenceRequest) -> InferenceResult:
        model = config.models[request.category]
        if not model.enabled:
            raise HTTPException(status_code=503, detail="Selected model is unavailable")
        if request.sensitivity == Sensitivity.RESTRICTED and model.provider not in policies.restricted_providers:
            raise HTTPException(status_code=403, detail="Selected model is not permitted for restricted data")
        try:
            return await providers[request.category].generate(request)
        except ProviderFailure as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.post("/v1/route", response_model=RoutingDecision)
    def route(request: RoutingRequest) -> RoutingDecision:
        try:
            return engine.route(request)
        except PolicyDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RouteUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post("/v1/execute", response_model=ExecutionResult)
    async def execute(request: ExecutionRequest) -> ExecutionResult:
        decision = route(request)
        inference = InferenceRequest(
            category=decision.category,
            prompt=request.prompt,
            sensitivity=request.sensitivity,
            image_base64=request.image_base64,
            image_mime_type=request.image_mime_type,
        )
        try:
            result = await providers[decision.category].generate(inference)
        except ProviderFailure as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ExecutionResult(decision=decision, result=result)

    return router
