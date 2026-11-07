import asyncio
from time import perf_counter

from fastapi import APIRouter, HTTPException, Request
from opentelemetry import trace
from pydantic import BaseModel

from app.config import RouterConfig
from app.evaluation.quality import QualityResult, assess_quality
from app.governance.audit import record_attempt
from app.governance.guardrails import effective_sensitivity, model_allowed
from app.models.contracts import InferenceRequest, InferenceResult, ModelCategory
from app.models.providers import ProviderFailure, make_provider
from app.observability.metrics import observe_provider, observe_route
from app.router.classifier import ExecutionRequest, RoutingRequest
from app.router.policy_engine import RoutingPolicies
from app.router.routing_engine import (
    PolicyDenied,
    RouteUnavailable,
    RoutingDecision,
    RoutingEngine,
)


class ExecutionResult(BaseModel):
    decision: RoutingDecision
    result: InferenceResult
    quality: QualityResult
    attempts: int


tracer = trace.get_tracer("enterprise_router.provider")


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
    async def infer(request: InferenceRequest, http_request: Request) -> InferenceResult:
        model = config.models[request.category]
        if not model.enabled:
            raise HTTPException(status_code=503, detail="Selected model is unavailable")
        sensitivity = effective_sensitivity(request.prompt, request.sensitivity)
        if not model_allowed(request.prompt, sensitivity, model, policies):
            raise HTTPException(status_code=403, detail="Selected model is not permitted by privacy or budget policy")
        audit_fields = {
            "category": request.category.value,
            "model_id": model.id,
            "provider": model.provider,
            "sensitivity": sensitivity.value,
            "request_id": http_request.state.request_id,
            "entry_point": "direct_infer",
        }
        start = perf_counter()
        try:
            with tracer.start_as_current_span("provider.generate") as span:
                span.set_attribute("model.category", request.category.value)
                span.set_attribute("model.provider", model.provider)
                result = await asyncio.wait_for(
                    providers[request.category].generate(request), timeout=model.timeout_seconds
                )
        except TimeoutError as exc:
            observe_provider(request.category.value, model.provider, "timeout", perf_counter() - start)
            record_attempt(**audit_fields, outcome="timeout")
            raise HTTPException(status_code=504, detail="Selected model timed out") from exc
        except ProviderFailure as exc:
            observe_provider(request.category.value, model.provider, "provider_failure", perf_counter() - start)
            record_attempt(**audit_fields, outcome="provider_failure")
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        quality = assess_quality(result)
        observe_provider(
            request.category.value, model.provider,
            "accepted" if quality.accepted else "quality_failure", perf_counter() - start,
        )
        record_attempt(**audit_fields, outcome="accepted" if quality.accepted else "quality_failure", result=result)
        if not quality.accepted:
            raise HTTPException(status_code=502, detail="Provider output did not pass quality checks")
        return result

    @router.post("/v1/route", response_model=RoutingDecision)
    def route(request: RoutingRequest) -> RoutingDecision:
        try:
            decision = engine.route(request)
            observe_route(decision.category.value, decision.provider, decision.fallback_used)
            return decision
        except PolicyDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RouteUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @router.post("/v1/execute", response_model=ExecutionResult)
    async def execute(request: ExecutionRequest, http_request: Request) -> ExecutionResult:
        first = route(request)
        candidates = [first, *engine.escalation_candidates(request, first)]
        timeout_count = 0
        for attempt, decision in enumerate(candidates, start=1):
            inference = InferenceRequest(
                category=decision.category,
                prompt=request.prompt,
                sensitivity=decision.sensitivity,
                image_base64=request.image_base64,
                image_mime_type=request.image_mime_type,
            )
            audit_fields = {
                "category": decision.category.value,
                "model_id": decision.model_id,
                "provider": decision.provider,
                "sensitivity": decision.sensitivity.value,
                "task_type": decision.task_type.value,
                "fallback_used": decision.fallback_used,
                "request_id": http_request.state.request_id,
                "entry_point": "routed_execute",
            }
            start = perf_counter()
            try:
                with tracer.start_as_current_span("provider.generate") as span:
                    span.set_attribute("model.category", decision.category.value)
                    span.set_attribute("model.provider", decision.provider)
                    result = await asyncio.wait_for(
                        providers[decision.category].generate(inference),
                        timeout=config.models[decision.category].timeout_seconds,
                    )
            except TimeoutError:
                observe_provider(decision.category.value, decision.provider, "timeout", perf_counter() - start)
                record_attempt(**audit_fields, outcome="timeout")
                timeout_count += 1
                continue
            except ProviderFailure:
                observe_provider(decision.category.value, decision.provider, "provider_failure", perf_counter() - start)
                record_attempt(**audit_fields, outcome="provider_failure")
                continue
            quality = assess_quality(result)
            observe_provider(
                decision.category.value, decision.provider,
                "accepted" if quality.accepted else "quality_failure", perf_counter() - start,
            )
            record_attempt(
                **audit_fields, outcome="accepted" if quality.accepted else "quality_failure", result=result
            )
            if quality.accepted:
                return ExecutionResult(decision=decision, result=result, quality=quality, attempts=attempt)
        if timeout_count == len(candidates):
            raise HTTPException(status_code=504, detail="All eligible models timed out")
        raise HTTPException(status_code=502, detail="No provider returned an acceptable result")

    return router
