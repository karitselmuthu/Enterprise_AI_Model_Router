from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.routes import build_router
from app.config import load_config
from app.observability.metrics import HTTP_DURATION, HTTP_REQUESTS
from app.observability.tracing import configure_tracing
from app.router.policy_engine import load_policies


def create_app() -> FastAPI:
    config = load_config()
    policies = load_policies()
    application = FastAPI(title="Enterprise AI Model Router", version="0.1.0")
    application.include_router(build_router(config, policies))

    @application.middleware("http")
    async def record_http(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        start = perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        route_name = getattr(route, "path", "unknown")
        if route_name != "/metrics":
            HTTP_REQUESTS.labels(request.method, route_name, f"{response.status_code // 100}xx").inc()
            HTTP_DURATION.labels(request.method, route_name).observe(perf_counter() - start)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    configure_tracing(application)
    return application


app = create_app()
