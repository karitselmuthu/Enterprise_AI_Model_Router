from fastapi import APIRouter

from app.config import RouterConfig
from app.models.contracts import InferenceRequest, InferenceResult, ModelCategory
from app.models.mock import MockProvider


def build_router(config: RouterConfig) -> APIRouter:
    router = APIRouter()
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

    return router
