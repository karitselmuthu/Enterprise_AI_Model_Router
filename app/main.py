from fastapi import FastAPI

from app.api.routes import build_router
from app.config import load_config
from app.router.policy_engine import load_policies


def create_app() -> FastAPI:
    config = load_config()
    policies = load_policies()
    application = FastAPI(title="Enterprise AI Model Router", version="0.1.0")
    application.include_router(build_router(config, policies))
    return application


app = create_app()
