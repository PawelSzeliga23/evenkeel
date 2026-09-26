from fastapi import FastAPI

from app.config import Settings, get_settings
from app.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Portfolio API")
    app.include_router(health_router)
    return app


app = create_app()
