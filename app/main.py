from fastapi import FastAPI

from app.api.routes import build_router
from app.config import load_config


def create_app() -> FastAPI:
    config = load_config()
    application = FastAPI(title="Enterprise AI Model Router", version="0.1.0")
    application.include_router(build_router(config))
    return application


app = create_app()
