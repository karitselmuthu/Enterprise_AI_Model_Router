from fastapi import APIRouter, HTTPException

from app.config import RouterConfig
from app.models.contracts import InferenceRequest, InferenceResult, ModelCategory
from app.models.mock import MockProvider
from app.router.classifier import RoutingRequest
from app.router.policy_engine import RoutingPolicies
from app.router.routing_engine import PolicyDenied, RouteUnavailable, RoutingDecision, RoutingEngine


def build_router(config: RouterConfig, policies: RoutingPolicies) -> APIRouter:
    router = APIRouter()
    engine = RoutingEngine(config, policies)
    providers = {
        category: MockProvider(category, model.id)
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
            {"category": category.value, "model_id": config.models[category].id, "provider": "mock"}
            for category in ModelCategory
        ]

    @router.post("/v1/infer", response_model=InferenceResult)
    async def infer(request: InferenceRequest) -> InferenceResult:
        return await providers[request.category].generate(request)

    @router.post("/v1/route", response_model=RoutingDecision)
    def route(request: RoutingRequest) -> RoutingDecision:
        try:
            return engine.route(request)
        except PolicyDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RouteUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return router
